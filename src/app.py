"""
Streamlit demo for the Solidity vulnerability classifier.

Run locally with:
    pip install -r requirements.txt
    streamlit run src/app.py

Set ANTHROPIC_API_KEY in your environment to enable the LLM remediation
cascade (optional — the classifier works without it).
"""

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict import VulnClassifier

st.set_page_config(page_title="Solidity Vulnerability Classifier", page_icon="🛡️", layout="wide")

EXAMPLE_CONTRACT = '''pragma solidity ^0.4.24;

contract Vulnerable {
    mapping(address => uint256) public balances;

    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);
        (bool success, ) = msg.sender.call.value(amount)("");
        require(success);
        balances[msg.sender] -= amount;
    }
}
'''


@st.cache_resource
def load_classifier():
    return VulnClassifier()


def main():
    st.title("🛡️ Solidity Smart Contract Vulnerability Classifier")
    st.caption(
        "Multi-class classifier (RandomForest over static-analysis features + TF-IDF) "
        "trained on SmartBugs-curated + SolidiFI-benchmark, with an optional Claude "
        "remediation cascade."
    )

    try:
        clf = load_classifier()
    except FileNotFoundError:
        st.error("No trained model found in `models/`. Run `python src/train.py` first.")
        return

    col_input, col_meta = st.columns([3, 1])
    with col_input:
        uploaded = st.file_uploader("Upload a .sol file", type=["sol"])
        default_code = uploaded.read().decode("utf-8", errors="replace") if uploaded else EXAMPLE_CONTRACT
        code = st.text_area("...or paste Solidity source", value=default_code, height=320)

    with col_meta:
        st.markdown("**Trained classes**")
        for c in clf.label_encoder.classes_:
            st.markdown(f"- {c}")
        use_llm = st.checkbox("Use Claude remediation cascade", value=False)
        if use_llm and not os.environ.get("ANTHROPIC_API_KEY"):
            st.warning("Set ANTHROPIC_API_KEY in your environment to use this.")

    if st.button("Classify", type="primary"):
        if not code.strip():
            st.warning("Paste or upload some Solidity code first.")
            return

        probs = clf.predict_proba(code)
        ranked = sorted(probs.items(), key=lambda kv: -kv[1])
        top_label, top_prob = ranked[0]

        st.subheader(f"Prediction: `{top_label}`  ({top_prob:.0%} confidence)")
        st.bar_chart({label: p for label, p in ranked})

        if use_llm and os.environ.get("ANTHROPIC_API_KEY"):
            from llm_cascade import remediate
            with st.spinner("Asking Claude for a remediation writeup..."):
                try:
                    result = remediate(code, probs)
                    tier_label = {
                        "confident": "✅ High confidence — remediation for the predicted class",
                        "ambiguous": "⚖️ Ambiguous — Claude adjudicated between top-2 candidates",
                        "low_confidence": "🔍 Low confidence — Claude assessed the code directly",
                    }[result.tier]
                    st.info(tier_label)
                    st.markdown(result.narrative)
                except Exception as e:
                    st.error(f"LLM cascade failed: {e}")


if __name__ == "__main__":
    main()
