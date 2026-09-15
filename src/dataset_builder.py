"""
Builds a unified labeled dataset of Solidity contracts from two public sources:

1. SmartBugs-curated  (github.com/smartbugs/smartbugs-curated)
   - 143 real-world contracts, manually labeled by researchers, DASP taxonomy.
2. SolidiFI-benchmark (github.com/DependableSystemsLab/SolidiFI-benchmark)
   - 350 contracts with tool-injected bugs, 50 per category, 7 categories.

Both are mapped onto one 7-class taxonomy and written out as a single CSV:
    data/dataset.csv   columns: [path, source, label, code]
"""

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SMARTBUGS_DIR = ROOT / "data" / "smartbugs-curated" / "dataset"
SOLIDIFI_DIR = ROOT / "data" / "solidifi" / "buggy_contracts"
OUT_CSV = ROOT / "data" / "dataset.csv"

# Unified 7-class taxonomy and how each source's folders map onto it.
SMARTBUGS_LABEL_MAP = {
    "reentrancy": "reentrancy",
    "arithmetic": "arithmetic",
    "access_control": "access_control",
    "unchecked_low_level_calls": "unchecked_low_level_calls",
    "time_manipulation": "time_manipulation",
    "front_running": "front_running",
    # dropped: "bad_randomness" (only 8 samples, no SolidiFI counterpart),
    #          "other" (catch-all, only 3 samples),
    #          "short_addresses" (only 1 sample, effectively deprecated vuln class)
}

SOLIDIFI_LABEL_MAP = {
    "Re-entrancy": "reentrancy",
    "Overflow-Underflow": "arithmetic",
    "Unchecked-Send": "unchecked_low_level_calls",
    "Unhandled-Exceptions": "unchecked_low_level_calls",
    "Timestamp-Dependency": "time_manipulation",
    "TOD": "front_running",
    "tx.origin": "tx_origin",
    # access_control has no SolidiFI equivalent folder
}

NOT_SO_SMART_DIR_NAME = "not-so-smart"
NOT_SO_SMART_LABEL_MAP = {
    "unprotected_function": "access_control",
    "integer_overflow": "arithmetic",
    "reentrancy": "reentrancy",
    "unchecked_external_call": "unchecked_low_level_calls",
    "race_condition": "front_running",
}


def read_code(path: Path) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return path.read_bytes().decode("utf-8", errors="replace")


def collect_smartbugs(rows: list):
    if not SMARTBUGS_DIR.exists():
        return
    for folder, label in SMARTBUGS_LABEL_MAP.items():
        for sol_file in (SMARTBUGS_DIR / folder).glob("*.sol"):
            code = read_code(sol_file)
            rows.append({
                "path": str(sol_file.relative_to(ROOT)),
                "source": "smartbugs",
                "label": label,
                "code": code,
            })


def collect_solidifi(rows: list):
    if not SOLIDIFI_DIR.exists():
        return
    for folder, label in SOLIDIFI_LABEL_MAP.items():
        for sol_file in (SOLIDIFI_DIR / folder).glob("*.sol"):
            code = read_code(sol_file)
            rows.append({
                "path": str(sol_file.relative_to(ROOT)),
                "source": "solidifi",
                "label": label,
                "code": code,
            })


def collect_not_so_smart(rows: list):
    base = ROOT / "data" / NOT_SO_SMART_DIR_NAME
    if not base.exists():
        return
    for folder, label in NOT_SO_SMART_LABEL_MAP.items():
        folder_path = base / folder
        if not folder_path.exists():
            continue
        for sol_file in folder_path.rglob("*.sol"):
            code = read_code(sol_file)
            rows.append({
                "path": str(sol_file.relative_to(ROOT)),
                "source": "not-so-smart",
                "label": label,
                "code": code,
            })


def collect_synthetic(rows: list):
    synth_dir = ROOT / "data" / "synthetic" / "access_control"
    if not synth_dir.exists():
        return
    for sol_file in synth_dir.glob("*.sol"):
        code = read_code(sol_file)
        rows.append({
            "path": str(sol_file.relative_to(ROOT)),
            "source": "synthetic",
            "label": "access_control",
            "code": code,
        })


def dedupe(rows: list) -> list:
    """Drop exact-duplicate contract source (SolidiFI reuses ~50 base contracts
    across categories, but the injected bug differs, so dupes here are true dupes)."""
    seen = set()
    out = []
    for r in rows:
        h = hashlib.sha256(r["code"].encode("utf-8", errors="replace")).hexdigest()
        key = (h, r["label"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main():
    rows = []
    collect_smartbugs(rows)
    collect_solidifi(rows)
    collect_not_so_smart(rows)
    collect_synthetic(rows)
    rows = dedupe(rows)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "source", "label", "code"])
        writer.writeheader()
        writer.writerows(rows)

    from collections import Counter
    counts = Counter(r["label"] for r in rows)
    print(f"Wrote {len(rows)} contracts to {OUT_CSV}")
    for label, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {label:28s} {n}")


if __name__ == "__main__":
    main()
