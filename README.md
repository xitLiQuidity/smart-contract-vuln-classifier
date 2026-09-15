# Solidity Smart Contract Vulnerability Classifier

Multi-class classifier that labels a Solidity contract with its most likely
vulnerability type, plus an optional Claude-powered remediation cascade and
a Streamlit demo.

## Results

| | v1 | v2 | v3 | v4 (current) |
|---|---|---|---|---|
| Dataset | 468 | 468 | 478 | **534** (+56 synthetic `access_control`) |
| `access_control` examples | 18 | 18 | 20 | **76** |
| Model | Random Forest | XGBoost, tuned | Voting ensemble | Voting ensemble (same tuned hyperparams as v3) |
| Features | handcrafted + word TF-IDF | + char TF-IDF | same as v2 | + 2 access-control-specific heuristics |
| Test accuracy | 93.6% | 93.6% | 93.8% | **97.2%** |
| Test macro F1 | 0.926 | 0.936 | 0.937 | **0.980** |
| `access_control` F1 | 0.857 | 0.857 | 0.857 | **0.966** |

v4 is what's currently saved in `models/`.

**What changed, specifically for `access_control`:**

1. **Synthetic data** (`src/synthetic_access_control.py`) — public sources maxed out at
   20 real examples, so this generates 56 more from 7 template patterns covering the
   actual documented failure modes: missing owner check, public owner-setter, a
   modifier defined but never attached to a function, the classic
   wrong-constructor-name bug (Rubixi/Parity-style), unprotected `selfdestruct`,
   unprotected re-callable `initialize()`, and a check applied to only one branch of
   an if/else. Each template is instantiated 8x with randomized names/pragmas so the
   model can't just memorize one exact string.
2. **Two new handcrafted features** (`feature_extraction.py`):
   `unprotected_sensitive_fn_ratio` (of functions named like `setOwner`/`withdraw`/
   `mint`/`selfdestruct`/etc., what fraction have no `require(msg.sender==...)` or
   `onlyX` check anywhere in their body) and `modifier_defined_but_unapplied` (an
   `onlyX` modifier exists but is never attached to any function).

**Honest caveat:** the held-out test set only has 3 *real* (non-synthetic)
`access_control` examples after this split — 2 of those 3 were classified correctly.
That's too small a sample to claim confidently-solved generalization; the 76 synthetic
examples inflate both the training set and, proportionally, the test set. The synthetic
patterns are real documented vulnerability classes (not invented), and the new features
are pattern-based rather than memorized strings, so this should generalize to genuinely
new contracts sharing these patterns — but "97.2% accuracy" is measured on a test set
that's now roughly 1/4 synthetic for this class, which is worth keeping in mind rather
than taking the headline number at face value.

Per-class test performance and the confusion matrix are in `reports/metrics_v4.json` and
`reports/confusion_matrix_v4.png` (earlier versions' reports kept alongside).

## Classes

`reentrancy`, `arithmetic`, `access_control`, `unchecked_low_level_calls`,
`time_manipulation`, `front_running`, `tx_origin`

(`bad_randomness`, `other`, `short_addresses` were dropped from the raw
SmartBugs taxonomy — each had under 10 examples with no way to augment them.)

## Architecture

```
data/dataset_builder.py -> merges public + synthetic labeled data into data/dataset.csv
src/synthetic_access_control.py -> generates synthetic access_control training examples
src/feature_extraction.py -> ~32 handcrafted static features (regex-based, no solc needed)
src/train.py                -> v1: handcrafted + word TF-IDF -> RF vs XGBoost vs LogReg -> saves best
src/train_v2.py              -> v2/v3/v4 pipeline: + char TF-IDF, hyperparameter search,
                                 minority oversampling, voting/stacking ensemble comparison
src/predict.py               -> loads saved model, predicts on new .sol source
src/llm_cascade.py           -> optional second stage: Claude explains + remediates
src/app.py                   -> Streamlit UI over predict.py + llm_cascade.py
demo.html                    -> standalone interactive browser demo (calls Claude directly)
```

No Solidity compiler is used. All features are textual/regex heuristics
(external-call patterns, arithmetic context, access-control idioms,
timestamp/tx.origin usage, and a simple "external call before state write"
ordering check for reentrancy) combined with a TF-IDF over Solidity-aware
tokens. This trades some precision against AST/symbolic-execution tools
(Slither, Mythril) for zero compiler/toolchain dependency.

## Setup

```bash
pip install -r requirements.txt

# 1. Rebuild the dataset from the two public sources (already run once; only
#    needed if you re-clone the raw repos into data/)
python src/dataset_builder.py

# 2. Train + evaluate + save the model (v2 is what's currently in models/)
python src/train_v2.py     # slower (~5 min): hyperparameter search + oversampling
python src/train.py        # faster baseline, if you just want v1 back

# 3. Classify a single file from the command line
python src/predict.py path/to/contract.sol

# 4. Launch the interactive demo
export ANTHROPIC_API_KEY=sk-...   # optional, enables the remediation cascade
streamlit run src/app.py
```

## LLM cascade

`llm_cascade.py` only calls Claude when it adds value over the raw ML
output:

- **Confident** (top probability ≥ 0.75) → one-shot remediation writeup for
  the predicted class.
- **Ambiguous** (top-2 probabilities within 0.15) → Claude adjudicates
  between the two candidate classes using the actual code.
- **Low confidence** (top probability < 0.40) → Claude reads the code
  directly instead of trusting the ML label.

This keeps API calls off the hot path when the classifier is already
confident, and reserves the more expensive judgment call for cases where a
plain label isn't good enough.

## Known limitations

- Regex/TF-IDF features, not a real AST — can be fooled by unusual
  formatting or renamed identifiers in ways a compiler-based tool wouldn't.
- `access_control` and `tx_origin` classes are small (18–50 examples);
  expect noisier predictions there than for `reentrancy` or
  `unchecked_low_level_calls` (80–150 examples).
- Trained only on injected/benchmark bugs (SolidiFI) plus a small curated
  real-world set (SmartBugs) — a large, diverse mainnet corpus would
  generalize better.
