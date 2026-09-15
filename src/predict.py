"""Load the trained pipeline and predict on new Solidity source code."""

import sys
from pathlib import Path

import joblib
from scipy.sparse import hstack, csr_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from feature_extraction import extract_features

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"


class VulnClassifier:
    def __init__(self, models_dir: Path = MODELS_DIR):
        self.clf = joblib.load(models_dir / "classifier.joblib")
        self.vectorizer = joblib.load(models_dir / "tfidf_vectorizer.joblib")
        self.scaler = joblib.load(models_dir / "feature_scaler.joblib")
        self.label_encoder = joblib.load(models_dir / "label_encoder.joblib")
        self.feature_columns = joblib.load(models_dir / "feature_columns.joblib")
        char_vec_path = models_dir / "char_tfidf_vectorizer.joblib"
        self.char_vectorizer = joblib.load(char_vec_path) if char_vec_path.exists() else None

    def _vectorize(self, code: str):
        hand = extract_features(code)
        hand_row = [[hand[c] for c in self.feature_columns]]
        hand_scaled = self.scaler.transform(hand_row)
        parts = [csr_matrix(hand_scaled), self.vectorizer.transform([code])]
        if self.char_vectorizer is not None:
            parts.append(self.char_vectorizer.transform([code]))
        return hstack(parts).tocsr()

    def predict_proba(self, code: str) -> dict:
        X = self._vectorize(code)
        probs = self.clf.predict_proba(X)[0]
        return dict(zip(self.label_encoder.classes_, (float(p) for p in probs)))

    def predict(self, code: str) -> str:
        probs = self.predict_proba(code)
        return max(probs, key=probs.get)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Classify a Solidity file's vulnerability type")
    parser.add_argument("file", help="path to a .sol file")
    args = parser.parse_args()

    code = Path(args.file).read_text(encoding="utf-8", errors="replace")
    clf = VulnClassifier()
    probs = clf.predict_proba(code)
    for label, p in sorted(probs.items(), key=lambda kv: -kv[1]):
        print(f"{label:28s} {p:.3f}")
