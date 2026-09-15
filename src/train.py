"""
Trains and compares three classifiers (Logistic Regression baseline,
Random Forest, XGBoost) on a combined feature set:
  - handcrafted static-analysis features (feature_extraction.py)
  - TF-IDF over Solidity-aware tokens

Saves the best model (by macro F1 on a held-out stratified test split) plus
the fitted vectorizer/scaler/label-encoder to models/, and writes a
metrics report + confusion matrix image.
"""

import json
import re
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import hstack, csr_matrix
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))
from feature_extraction import extract_features_df

ROOT = Path(__file__).resolve().parent.parent
DATASET_CSV = ROOT / "data" / "dataset.csv"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

TOKEN_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*|\.\w+\(|==|!=|\+=|-=|\bmsg\.sender\b|\btx\.origin\b"


def load_data():
    df = pd.read_csv(DATASET_CSV)
    df = df.dropna(subset=["code", "label"])
    return df


def build_features(df: pd.DataFrame, vectorizer: TfidfVectorizer = None, scaler: StandardScaler = None, fit=True):
    hand = extract_features_df(df["code"])
    if fit:
        scaler = StandardScaler()
        hand_scaled = scaler.fit_transform(hand.values)
    else:
        hand_scaled = scaler.transform(hand.values)

    if fit:
        vectorizer = TfidfVectorizer(
            token_pattern=TOKEN_PATTERN,
            lowercase=False,
            max_features=1500,
            ngram_range=(1, 2),
            min_df=2,
        )
        tfidf = vectorizer.fit_transform(df["code"])
    else:
        tfidf = vectorizer.transform(df["code"])

    X = hstack([csr_matrix(hand_scaled), tfidf]).tocsr()
    return X, vectorizer, scaler, list(hand.columns)


def main():
    MODELS_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    print(f"Loaded {len(df)} contracts across {df['label'].nunique()} classes")

    le = LabelEncoder()
    y = le.fit_transform(df["label"])

    X_train_df, X_test_df, y_train, y_test = train_test_split(
        df, y, test_size=0.2, random_state=42, stratify=y
    )

    X_train, vectorizer, scaler, feat_cols = build_features(X_train_df, fit=True)
    X_test, _, _, _ = build_features(X_test_df, vectorizer=vectorizer, scaler=scaler, fit=False)

    candidates = {
        "logreg": LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0),
        "random_forest": RandomForestClassifier(
            n_estimators=400, max_depth=None, class_weight="balanced_subsample",
            random_state=42, n_jobs=-1,
        ),
        "xgboost": XGBClassifier(
            n_estimators=400, max_depth=6, learning_rate=0.08,
            subsample=0.9, colsample_bytree=0.9, eval_metric="mlogloss",
            random_state=42, n_jobs=-1,
        ),
    }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    results = {}
    for name, clf in candidates.items():
        scores = cross_val_score(clf, X_train, y_train, cv=cv, scoring="f1_macro", n_jobs=1)
        results[name] = {"cv_f1_macro_mean": float(scores.mean()), "cv_f1_macro_std": float(scores.std())}
        print(f"{name:15s} CV macro-F1: {scores.mean():.3f} +/- {scores.std():.3f}")

    best_name = max(results, key=lambda k: results[k]["cv_f1_macro_mean"])
    print(f"\nBest by CV: {best_name}. Fitting on full training set and evaluating on held-out test set...")

    best_clf = candidates[best_name]
    best_clf.fit(X_train, y_train)
    y_pred = best_clf.predict(X_test)

    report = classification_report(y_test, y_pred, target_names=le.classes_, digits=3, output_dict=True)
    report_text = classification_report(y_test, y_pred, target_names=le.classes_, digits=3)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    acc = (y_pred == y_test).mean()

    print(report_text)
    print(f"Test accuracy: {acc:.3f}  |  Test macro F1: {macro_f1:.3f}")

    cm = confusion_matrix(y_test, y_pred)

    # --- save everything ---
    joblib.dump(best_clf, MODELS_DIR / "classifier.joblib")
    joblib.dump(vectorizer, MODELS_DIR / "tfidf_vectorizer.joblib")
    joblib.dump(scaler, MODELS_DIR / "feature_scaler.joblib")
    joblib.dump(le, MODELS_DIR / "label_encoder.joblib")
    joblib.dump(feat_cols, MODELS_DIR / "feature_columns.joblib")

    with open(REPORTS_DIR / "metrics.json", "w") as f:
        json.dump({
            "model": best_name,
            "n_train": len(X_train_df),
            "n_test": len(X_test_df),
            "n_classes": len(le.classes_),
            "classes": list(le.classes_),
            "cv_results": results,
            "test_accuracy": float(acc),
            "test_macro_f1": float(macro_f1),
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
        }, f, indent=2)

    # confusion matrix plot
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
    ax.set_title(f"Confusion matrix — {best_name} (test acc={acc:.2f}, macro F1={macro_f1:.2f})")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                     color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=8)
    fig.colorbar(im)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "confusion_matrix.png", dpi=150)
    print(f"\nSaved model -> {MODELS_DIR}")
    print(f"Saved metrics + confusion matrix -> {REPORTS_DIR}")


if __name__ == "__main__":
    main()
