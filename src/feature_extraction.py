"""
Lightweight static feature extraction for Solidity source code.

No compiler/AST is used (solc isn't reachable in this environment), so every
feature is derived from regex / textual heuristics over the raw source. This
mirrors the class of features used in several published smart-contract
vulnerability-classification papers before they escalate to symbolic
execution: call patterns, arithmetic context, access-control idioms, time/
randomness dependence, and a simple "external call before state write"
ordering heuristic for reentrancy.
"""

import re
import pandas as pd

# --- regex patterns, compiled once ---------------------------------------

RE_EXTERNAL_CALL = re.compile(r"\.call\s*(\.value\s*\(|\{)|\.call\s*\(")
RE_DELEGATECALL = re.compile(r"\.delegatecall\s*\(")
RE_SEND = re.compile(r"\.send\s*\(")
RE_TRANSFER = re.compile(r"\.transfer\s*\(")
RE_SELFDESTRUCT = re.compile(r"\b(selfdestruct|suicide)\s*\(")

RE_REQUIRE = re.compile(r"\brequire\s*\(")
RE_ASSERT = re.compile(r"\bassert\s*\(")
RE_REVERT = re.compile(r"\brevert\s*\(")
RE_IF_NOT_CALL_RESULT = re.compile(r"if\s*\(\s*!\s*\w")  # if(!success) style checks

RE_TX_ORIGIN = re.compile(r"\btx\.origin\b")
RE_MSG_SENDER_EQ = re.compile(r"msg\.sender\s*==")
RE_ONLY_OWNER = re.compile(r"\bonlyOwner\b|\bonlyAdmin\b")
RE_MODIFIER_DEF = re.compile(r"\bmodifier\s+\w+")

RE_TIMESTAMP = re.compile(r"\bblock\.timestamp\b|\bnow\b")
RE_BLOCKNUM = re.compile(r"\bblock\.number\b|\bblockhash\s*\(")
RE_DIFFICULTY = re.compile(r"\bblock\.difficulty\b")

RE_SAFEMATH = re.compile(r"SafeMath")
RE_UNCHECKED_BLOCK = re.compile(r"\bunchecked\s*\{")
RE_ARITH_OP = re.compile(r"(?<![+\-*/=!<>])[+\-*/](?![+\-*/=])")
RE_PRAGMA = re.compile(r"pragma\s+solidity\s+([^\s;]+)")

RE_FUNCTION_DEF = re.compile(r"\bfunction\s+\w*\s*\(")
RE_PUBLIC_EXTERNAL_FN = re.compile(r"\bfunction\s+\w*\s*\([^)]*\)\s*(public|external)")
RE_PAYABLE = re.compile(r"\bpayable\b")
RE_LOOP = re.compile(r"\b(for|while)\s*\(")
RE_STATE_VAR = re.compile(
    r"^\s*(uint\d*|int\d*|address|bool|string|bytes\d*|mapping)\b[^;{=]*;", re.MULTILINE
)
RE_COMMENT = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)

SENSITIVE_FN_NAME = re.compile(
    r"function\s+(set\w*owner\w*|set\w*admin\w*|transferownership|withdraw\w*|sweep\w*|"
    r"mint\w*|burn\w*|pause\w*|unpause\w*|kill\w*|selfdestruct\w*|initialize\w*|init|"
    r"upgrade\w*|setcontroller\w*|setmanager\w*|setgovernor\w*)\s*\(",
    re.IGNORECASE,
)
RE_ACCESS_CHECK_IN_BODY = re.compile(
    r"require\s*\(\s*msg\.sender|onlyowner|onlyadmin|onlycontroller|onlymanager|onlygovernor|"
    r"msg\.sender\s*==|isowner|isadmin\[msg\.sender\]",
    re.IGNORECASE,
)
RE_MODIFIER_NAME_DEF = re.compile(r"\bmodifier\s+(\w+)\s*\(")


def _pragma_version(code: str) -> float:
    m = RE_PRAGMA.search(code)
    if not m:
        return 0.0
    ver = re.search(r"(\d+)\.(\d+)", m.group(1))
    if not ver:
        return 0.0
    major, minor = int(ver.group(1)), int(ver.group(2))
    return major + minor / 100.0


def _call_before_state_write_ratio(code: str) -> float:
    """Rough reentrancy ordering heuristic: for each function body, does an
    external call (.call/.send/.transfer) appear textually before a state
    variable assignment (`identifier = ` / `identifier -= ` etc.) later in
    the same function? Returns the fraction of functions with a call where
    this risky ordering is found."""
    functions = re.split(r"\bfunction\s+", code)[1:]
    if not functions:
        return 0.0
    risky = 0
    with_call = 0
    assign_re = re.compile(r"\b\w+\s*(\+=|-=|=)\s*[^=]")
    call_re = re.compile(r"\.call\s*(\.value\s*\(|\{|\()|\.send\s*\(|\.transfer\s*\(")
    for fn in functions:
        body = fn[:800]  # cap for speed/safety
        call_match = call_re.search(body)
        if not call_match:
            continue
        with_call += 1
        assign_match = assign_re.search(body, call_match.end())
        if assign_match:
            risky += 1
    return risky / with_call if with_call else 0.0


def _unprotected_sensitive_fn_ratio(code: str) -> float:
    """Access-control heuristic: of the functions whose NAME suggests a sensitive
    action (setOwner, withdraw, mint, selfdestruct, initialize, ...), what fraction
    have no access-check pattern anywhere in their body?"""
    functions = re.split(r"\bfunction\s+", code)[1:]
    if not functions:
        return 0.0
    sensitive = 0
    unprotected = 0
    for fn in functions:
        header_and_body = "function " + fn[:600]
        if not SENSITIVE_FN_NAME.search(header_and_body[:80]):
            # only test the function name/signature area, not the whole body,
            # to avoid matching the word "withdraw" appearing in a comment later
            if not SENSITIVE_FN_NAME.search("function " + fn.split("{")[0]):
                continue
        sensitive += 1
        if not RE_ACCESS_CHECK_IN_BODY.search(fn[:600]):
            unprotected += 1
    return (unprotected / sensitive) if sensitive else 0.0


def _modifier_defined_but_unapplied(code: str) -> int:
    """1 if an access-style modifier (onlyX) is defined but never attached to any
    function signature elsewhere in the file."""
    defined = [m for m in RE_MODIFIER_NAME_DEF.findall(code) if m.lower().startswith("only")]
    if not defined:
        return 0
    for name in defined:
        # look for the modifier name used on a function signature line, i.e. after
        # a `)` and before the opening `{`, not the `modifier NAME(` definition itself
        pattern = re.compile(
            r"function\s+\w*\s*\([^)]*\)\s*[^{;]*\b" + re.escape(name) + r"\b"
        )
        if pattern.search(code):
            return 0  # at least one onlyX modifier IS applied somewhere
    return 1  # every onlyX modifier defined is applied nowhere


def extract_features(code: str) -> dict:
    loc = code.count("\n") + 1
    code_nc = RE_COMMENT.sub(" ", code)  # strip comments for cleaner counts
    length = max(len(code_nc), 1)

    n_functions = len(RE_FUNCTION_DEF.findall(code_nc))

    feats = {
        "loc": loc,
        "n_external_call": len(RE_EXTERNAL_CALL.findall(code_nc)),
        "n_delegatecall": len(RE_DELEGATECALL.findall(code_nc)),
        "n_send": len(RE_SEND.findall(code_nc)),
        "n_transfer": len(RE_TRANSFER.findall(code_nc)),
        "n_selfdestruct": len(RE_SELFDESTRUCT.findall(code_nc)),
        "n_require": len(RE_REQUIRE.findall(code_nc)),
        "n_assert": len(RE_ASSERT.findall(code_nc)),
        "n_revert": len(RE_REVERT.findall(code_nc)),
        "n_if_not_check": len(RE_IF_NOT_CALL_RESULT.findall(code_nc)),
        "n_tx_origin": len(RE_TX_ORIGIN.findall(code_nc)),
        "n_msg_sender_eq": len(RE_MSG_SENDER_EQ.findall(code_nc)),
        "n_only_owner": len(RE_ONLY_OWNER.findall(code_nc)),
        "n_modifier_def": len(RE_MODIFIER_DEF.findall(code_nc)),
        "n_timestamp": len(RE_TIMESTAMP.findall(code_nc)),
        "n_blocknum": len(RE_BLOCKNUM.findall(code_nc)),
        "n_difficulty": len(RE_DIFFICULTY.findall(code_nc)),
        "has_safemath": int(bool(RE_SAFEMATH.search(code_nc))),
        "has_unchecked_block": int(bool(RE_UNCHECKED_BLOCK.search(code_nc))),
        "n_arith_ops": len(RE_ARITH_OP.findall(code_nc)),
        "pragma_version": _pragma_version(code),
        "n_functions": n_functions,
        "n_public_external_fn": len(RE_PUBLIC_EXTERNAL_FN.findall(code_nc)),
        "n_payable": len(RE_PAYABLE.findall(code_nc)),
        "n_loops": len(RE_LOOP.findall(code_nc)),
        "n_state_vars": len(RE_STATE_VAR.findall(code_nc)),
        "call_before_state_write_ratio": _call_before_state_write_ratio(code_nc),
        "comment_ratio": len(RE_COMMENT.findall(code)) / max(loc, 1),
        "unprotected_sensitive_fn_ratio": _unprotected_sensitive_fn_ratio(code_nc),
        "modifier_defined_but_unapplied": _modifier_defined_but_unapplied(code_nc),
    }

    # normalize a few count features by code length / function count to reduce
    # the model simply learning "longer contract -> more of everything"
    per_kloc = 1000.0 / length
    for key in [
        "n_external_call", "n_require", "n_timestamp", "n_arith_ops",
        "n_tx_origin", "n_modifier_def",
    ]:
        feats[f"{key}_per_kloc"] = feats[key] * per_kloc

    feats["fn_per_kloc"] = n_functions * per_kloc

    return feats


def extract_features_df(codes: pd.Series) -> pd.DataFrame:
    return pd.DataFrame([extract_features(c) for c in codes])
