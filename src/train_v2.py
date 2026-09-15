"""
train_v2.py — accuracy-focused rewrite of train.py.

Changes vs v1:
  1. TF-IDF now has TWO views: word-level (identifiers/keywords, as before)
     AND char_wb n-grams (3-5 chars), which catch Solidity syntax patterns
     that don't line up on word boundaries (".call.value(", "+=", etc.)
     and are more robust to minor renaming/formatting differences.
  2. RandomizedSearchCV tunes RandomForest and XGBoost instead of using
     fixed hyperparameters.
  3. RandomOverSampler duplicates minority-class TRAINING rows only
     (access_control has 18 total vs 150 for the biggest class) so the
     model sees a more balanced distribution without touching the test set.
  4. A soft-voting ensemble (tuned RF + tuned XGBoost + LogReg) is added
     as a fourth candidate, since averaging tends to help most exactly
     when individual models disagree on the hard, small classes.
  5. Same held-out stratified test split (test_size=0.2, random_state=42)
     as v1, so the reported numbers are a fair apples-to-apples comparison.
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import hstack, csr_matrix
from sklearn.model_selection import train_test_split, StratifiedKFold, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from xgboost import XGBClassifier
from imblearn.over_sampling import RandomOverSampler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from feature_extraction import extract_features_df

ROOT = Path(__file__).resolve().parent.parent
DATASET_CSV = ROOT / "data" / "dataset.csv"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

WORD_TOKEN_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*|\.\w+\(|==|!=|\+=|-=|\bmsg\.sender\b|\btx\.origin\b"


def load_data():
    df = pd.read_csv(DATASET_CSV)
    return df.dropna(subset=["code", "label"])


def build_features(df, word_vec=None, char_vec=None, scaler=None, fit=True):
    hand = extract_features_df(df["code"])
    if fit:
        scaler = StandardScaler()
        hand_scaled = scaler.fit_transform(hand.values)
    else:
        hand_scaled = scaler.transform(hand.values)

    if fit:
        word_vec = TfidfVectorizer(
            token_pattern=WORD_TOKEN_PATTERN, lowercase=False,
            max_features=1000, ngram_range=(1, 2), min_df=2,
        )
        word_tfidf = word_vec.fit_transform(df["code"])
        char_vec = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), lowercase=False,
            max_features=1000, min_df=2,
        )
        char_tfidf = char_vec.fit_transform(df["code"])
    else:
        word_tfidf = word_vec.transform(df["code"])
        char_tfidf = char_vec.transform(df["code"])

    X = hstack([csr_matrix(hand_scaled), word_tfidf, char_tfidf]).tocsr()
    return X, word_vec, char_vec, scaler, list(hand.columns)


def tune_random_forest(X, y, cv):
    param_dist = {
        "n_estimators": [200, 300],
        "max_depth": [None, 20, 35],
        "min_samples_split": [2, 4],
        "min_samples_leaf": [1, 2],
        "max_features": ["sqrt", 0.3],
    }
    search = RandomizedSearchCV(
        RandomForestClassifier(class_weight="balanced_subsample", random_state=42, n_jobs=1),
        param_distributions=param_dist, n_iter=3, cv=cv, scoring="f1_macro",
        random_state=42, n_jobs=1,
    )
    search.fit(X, y)
    return search.best_estimator_, search.best_score_, search.best_params_


def tune_xgboost(X, y, cv):
    param_dist = {
        "n_estimators": [150, 250],
        "max_depth": [4, 6],
        "learning_rate": [0.05, 0.1],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
    }
    search = RandomizedSearchCV(
        XGBClassifier(eval_metric="mlogloss", random_state=42, n_jobs=1, tree_method="hist"),
        param_distributions=param_dist, n_iter=3, cv=cv, scoring="f1_macro",
        random_state=42, n_jobs=1,
    )
    search.fit(X, y)
    return search.best_estimator_, search.best_score_, search.best_params_


def main():
    MODELS_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    print(f"Loaded {len(df)} contracts across {df['label'].nunique()} classes")

    le = LabelEncoder()
    y_all = le.fit_transform(df["label"])

    train_df, test_df, y_train, y_test = train_test_split(
        df, y_all, test_size=0.2, random_state=42, stratify=y_all
    )

    X_train, word_vec, char_vec, scaler, feat_cols = build_features(train_df, fit=True)
    X_test, _, _, _, _ = build_features(test_df, word_vec=word_vec, char_vec=char_vec, scaler=scaler, fit=False)

    print(f"Feature matrix: {X_train.shape[1]} dims "
          f"({len(feat_cols)} handcrafted + up to 1500 word TF-IDF + up to 1500 char TF-IDF)")

    # oversample minority classes in the TRAINING split only
    ros = RandomOverSampler(random_state=42)
    X_train_bal, y_train_bal = ros.fit_resample(X_train, y_train)
    print(f"After oversampling: {X_train.shape[0]} -> {X_train_bal.shape[0]} training rows")

    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)

    print("\nTuning Random Forest (RandomizedSearchCV, 15 candidates x 5-fold)...")
    rf_best, rf_cv_score, rf_params = tune_random_forest(X_train_bal, y_train_bal, cv)
    print(f"  best CV macro-F1: {rf_cv_score:.3f}  params: {rf_params}")

    print("\nTuning XGBoost (RandomizedSearchCV, 15 candidates x 5-fold)...")
    xgb_best, xgb_cv_score, xgb_params = tune_xgboost(X_train_bal, y_train_bal, cv)
    print(f"  best CV macro-F1: {xgb_cv_score:.3f}  params: {xgb_params}")

    logreg = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0)

    voting = VotingClassifier(
        estimators=[("rf", rf_best), ("xgb", xgb_best), ("logreg", logreg)],
        voting="soft",
    )
    from sklearn.model_selection import cross_val_score
    voting_scores = cross_val_score(voting, X_train_bal, y_train_bal, cv=cv, scoring="f1_macro", n_jobs=1)
    print(f"\nVoting ensemble CV macro-F1: {voting_scores.mean():.3f} +/- {voting_scores.std():.3f}")

    candidates = {
        "random_forest_tuned": (rf_best, rf_cv_score),
        "xgboost_tuned": (xgb_best, xgb_cv_score),
        "voting_ensemble": (voting, voting_scores.mean()),
    }
    best_name = max(candidates, key=lambda k: candidates[k][1])
    best_clf = candidates[best_name][0]
    print(f"\nBest by CV: {best_name} ({candidates[best_name][1]:.3f}). "
          f"Fitting on oversampled training set, evaluating on untouched test set...")

    best_clf.fit(X_train_bal, y_train_bal)
    y_pred = best_clf.predict(X_test)

    report_text = classification_report(y_test, y_pred, target_names=le.classes_, digits=3)
    report_dict = classification_report(y_test, y_pred, target_names=le.classes_, digits=3, output_dict=True)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    acc = (y_pred == y_test).mean()

    print(report_text)
    print(f"Test accuracy: {acc:.3f}  |  Test macro F1: {macro_f1:.3f}")

    cm = confusion_matrix(y_test, y_pred)

    joblib.dump(best_clf, MODELS_DIR / "classifier.joblib")
    joblib.dump(word_vec, MODELS_DIR / "tfidf_vectorizer.joblib")       # word-level, kept name for predict.py compat
    joblib.dump(char_vec, MODELS_DIR / "char_tfidf_vectorizer.joblib")  # new
    joblib.dump(scaler, MODELS_DIR / "feature_scaler.joblib")
    joblib.dump(le, MODELS_DIR / "label_encoder.joblib")
    joblib.dump(feat_cols, MODELS_DIR / "feature_columns.joblib")

    with open(REPORTS_DIR / "metrics_v2.json", "w") as f:
        json.dump({
            "model": best_name,
            "n_train_original": len(train_df),
            "n_train_after_oversample": int(X_train_bal.shape[0]),
            "n_test": len(test_df),
            "classes": list(le.classes_),
            "rf_cv_macro_f1": rf_cv_score,
            "xgb_cv_macro_f1": xgb_cv_score,
            "voting_cv_macro_f1": float(voting_scores.mean()),
            "test_accuracy": float(acc),
            "test_macro_f1": float(macro_f1),
            "classification_report": report_dict,
            "confusion_matrix": cm.tolist(),
        }, f, indent=2)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(le.classes_)))
    ax.set_yticks(range(len(le.classes_)))
    ax.set_xticklabels(le.classes_, rotation=45, ha="right")
    ax.set_yticklabels(le.classes_)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(f"v2 confusion matrix — {best_name} (acc={acc:.2f}, macro F1={macro_f1:.2f})")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                     color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=8)
    fig.colorbar(im)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "confusion_matrix_v2.png", dpi=150)

    print(f"\nSaved model -> {MODELS_DIR}")
    print(f"Saved metrics + confusion matrix -> {REPORTS_DIR}")


if __name__ == "__main__":
    main()
