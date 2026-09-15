"""
LLM cascade for remediation guidance.

The ML classifier (RandomForest/XGBoost over static features + TF-IDF) is
fast and cheap but only outputs a label + probabilities — it can't explain
*why* the code is vulnerable or *how* to fix it, and it has no fallback when
it's genuinely unsure between two classes. This module adds a second stage
that calls Claude only when it adds value:

  - HIGH confidence (top prob >= CONFIDENT_THRESHOLD):
      one-shot remediation writeup for the predicted class.
  - AMBIGUOUS (top-1 and top-2 probs within AMBIGUITY_MARGIN):
      ask Claude to adjudicate between the top-2 candidate classes using the
      actual code, and give remediation for whichever it judges correct.
  - LOW confidence (top prob < LOW_CONFIDENCE_THRESHOLD):
      ask Claude for an open-ended vulnerability read of the contract
      instead of trusting the ML label at all.

Requires the ANTHROPIC_API_KEY environment variable to be set. This module
is intentionally decoupled from train.py/predict.py so the classifier works
standalone (no API key, no network) and the cascade is opt-in.
"""

import os
from dataclasses import dataclass, field

import anthropic

MODEL = os.environ.get("VULN_LLM_MODEL", "claude-sonnet-5")

CONFIDENT_THRESHOLD = 0.75
LOW_CONFIDENCE_THRESHOLD = 0.40
AMBIGUITY_MARGIN = 0.15

VULN_DESCRIPTIONS = {
    "reentrancy": "an external call is made before the contract's own state is updated, "
                  "letting a malicious callee re-enter and drain funds",
    "arithmetic": "an arithmetic operation can overflow or underflow, corrupting balances "
                  "or counters",
    "access_control": "a sensitive function is missing (or has an incorrect) permission check",
    "unchecked_low_level_calls": "the return value of a low-level call/send is not checked, "
                                  "so a failed transfer is silently ignored",
    "time_manipulation": "contract logic depends on block.timestamp/now, which miners can "
                          "nudge within a small range",
    "front_running": "the outcome of a transaction can be changed by an attacker observing "
                      "and reordering pending transactions",
    "tx_origin": "tx.origin is used for authorization, which a malicious intermediate "
                 "contract can spoof",
}


@dataclass
class CascadeResult:
    tier: str                      # "confident" | "ambiguous" | "low_confidence"
    ml_label: str
    ml_confidence: float
    narrative: str
    considered_labels: list = field(default_factory=list)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env


def _call_claude(system: str, user: str, max_tokens: int = 700) -> str:
    client = _client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def remediate(code: str, label_probs: dict) -> CascadeResult:
    """label_probs: {class_name: probability}, from the ML classifier."""
    ranked = sorted(label_probs.items(), key=lambda kv: kv[1], reverse=True)
    top_label, top_prob = ranked[0]
    second_label, second_prob = ranked[1] if len(ranked) > 1 else (None, 0.0)

    snippet = code if len(code) < 6000 else code[:6000] + "\n// ... truncated ..."

    if top_prob < LOW_CONFIDENCE_THRESHOLD:
        system = (
            "You are a smart-contract security auditor. The automated classifier below "
            "this stage is not confident enough to trust. Read the Solidity code yourself "
            "and give your own best assessment."
        )
        user = (
            f"Automated classifier's uncertain guess: {top_label} ({top_prob:.0%}).\n\n"
            f"Solidity code:\n```solidity\n{snippet}\n```\n\n"
            "In under 200 words: state the most likely vulnerability (it may or may not "
            "match the guess above), point to the specific lines/patterns, and give a "
            "concrete fix."
        )
        narrative = _call_claude(system, user)
        return CascadeResult("low_confidence", top_label, top_prob, narrative, [top_label])

    if second_label and (top_prob - second_prob) < AMBIGUITY_MARGIN:
        system = (
            "You are a smart-contract security auditor adjudicating between two candidate "
            "vulnerability classes for the same contract."
        )
        user = (
            f"Candidate A: {top_label} ({VULN_DESCRIPTIONS.get(top_label, '')}) — {top_prob:.0%}\n"
            f"Candidate B: {second_label} ({VULN_DESCRIPTIONS.get(second_label, '')}) — {second_prob:.0%}\n\n"
            f"Solidity code:\n```solidity\n{snippet}\n```\n\n"
            "In under 200 words: say which candidate (or both, or neither) actually applies "
            "here, citing the specific code, then give a concrete remediation."
        )
        narrative = _call_claude(system, user)
        return CascadeResult("ambiguous", top_label, top_prob, narrative, [top_label, second_label])

    # confident case — single-class remediation writeup
    system = (
        "You are a smart-contract security auditor writing a short, specific remediation "
        "note for a developer."
    )
    user = (
        f"The contract below was classified as: {top_label} "
        f"({VULN_DESCRIPTIONS.get(top_label, '')}), confidence {top_prob:.0%}.\n\n"
        f"Solidity code:\n```solidity\n{snippet}\n```\n\n"
        "In under 150 words: point to the specific line(s)/pattern responsible, then give "
        "a concrete code-level fix (e.g. checks-effects-interactions, SafeMath/0.8 checked "
        "math, a real access modifier, etc.)."
    )
    narrative = _call_claude(system, user)
    return CascadeResult("confident", top_label, top_prob, narrative, [top_label])
