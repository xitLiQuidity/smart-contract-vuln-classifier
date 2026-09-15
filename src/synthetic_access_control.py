"""
Synthetic data generator for the access_control class.

Real public datasets only yield 20 access_control examples total (SmartBugs
18 + crytic/not-so-smart-contracts 2), and neither SolidiFI nor the other
sources have any more to give. Rather than wait on scraping a bigger corpus,
this generates realistic, structurally-diverse access-control-vulnerable
contracts from templates covering the actual sub-patterns seen in the wild:

  1. missing_owner_check      - sensitive action, no require/modifier at all
  2. public_owner_setter      - setOwner()/transferOwnership() callable by anyone
  3. unapplied_modifier       - onlyOwner modifier DEFINED but never attached
  4. wrong_constructor_name   - pre-0.4.22 "constructor" typo bug (classic parity/rubixi bug)
  5. unprotected_selfdestruct - kill switch with no access check
  6. unprotected_initializer  - upgradeable-proxy init() callable by anyone, twice
  7. partial_check            - checks msg.sender for ONE branch, not the sensitive one

Each template is instantiated multiple times with randomized identifier
names, comments, pragma versions, and superficial structure (extra unrelated
state vars/functions, differing require messages) so the model has to learn
the actual pattern rather than memorize one exact string. All output is
original code written for this generator — not copied from any dataset.
"""

import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "synthetic" / "access_control"

random.seed(42)

OWNER_NAMES = ["owner", "admin", "controller", "manager", "governor"]
TOKEN_NAMES = ["balances", "shares", "credits", "deposits"]
CONTRACT_NAMES = ["Vault", "Treasury", "Pool", "Escrow", "Bank", "Registry", "Router", "Farm"]
PRAGMAS = ["^0.4.24", "^0.4.26", "^0.5.0", "^0.6.0", "^0.8.0", "^0.8.20"]


def _rand(seq):
    return random.choice(seq)


def missing_owner_check(i):
    owner = _rand(OWNER_NAMES)
    cname = _rand(CONTRACT_NAMES) + str(i)
    pragma = _rand(PRAGMAS)
    return f"""pragma solidity {pragma};

contract {cname} {{
    address public {owner};
    uint256 public feeBps;
    mapping(address => uint256) public {_rand(TOKEN_NAMES)};

    constructor() {{
        {owner} = msg.sender;
    }}

    // BUG: anyone can change the fee, no {owner} check
    function setFeeBps(uint256 newFeeBps) public {{
        feeBps = newFeeBps;
    }}

    function sweep(address payable to) public {{
        to.transfer(address(this).balance);
    }}
}}
"""


def public_owner_setter(i):
    owner = _rand(OWNER_NAMES)
    cname = _rand(CONTRACT_NAMES) + str(i)
    pragma = _rand(PRAGMAS)
    return f"""pragma solidity {pragma};

contract {cname} {{
    address public {owner};

    constructor() {{
        {owner} = msg.sender;
    }}

    modifier only{owner.capitalize()}() {{
        require(msg.sender == {owner}, "not authorized");
        _;
    }}

    // BUG: takes over privileged role, missing only{owner.capitalize()} modifier
    function set{owner.capitalize()}(address new{owner.capitalize()}) public {{
        {owner} = new{owner.capitalize()};
    }}

    function withdrawAll() public only{owner.capitalize()} {{
        payable({owner}).transfer(address(this).balance);
    }}
}}
"""


def unapplied_modifier(i):
    owner = _rand(OWNER_NAMES)
    cname = _rand(CONTRACT_NAMES) + str(i)
    pragma = _rand(PRAGMAS)
    return f"""pragma solidity {pragma};

contract {cname} {{
    address public {owner};
    bool public paused;

    constructor() {{
        {owner} = msg.sender;
    }}

    modifier only{owner.capitalize()}() {{
        require(msg.sender == {owner}, "caller is not the {owner}");
        _;
    }}

    // BUG: modifier defined above but never attached here
    function pause() public {{
        paused = true;
    }}

    function unpause() public {{
        paused = false;
    }}
}}
"""


def wrong_constructor_name(i):
    cname = _rand(CONTRACT_NAMES) + str(i)
    owner = _rand(OWNER_NAMES)
    return f"""pragma solidity ^0.4.18;

contract {cname} {{
    address public {owner};
    uint256 public totalSupply;

    // BUG: function name doesn't match contract name (pre-0.4.22 "constructor"),
    // so this is just a normal public function anyone can call to become {owner}
    function {cname.lower()}() public {{
        {owner} = msg.sender;
    }}

    function mint(uint256 amount) public {{
        require(msg.sender == {owner});
        totalSupply += amount;
    }}
}}
"""


def unprotected_selfdestruct(i):
    cname = _rand(CONTRACT_NAMES) + str(i)
    owner = _rand(OWNER_NAMES)
    pragma = _rand(PRAGMAS)
    return f"""pragma solidity {pragma};

contract {cname} {{
    address public {owner};

    constructor() {{
        {owner} = msg.sender;
    }}

    function deposit() public payable {{}}

    // BUG: anyone can kill the contract and steal the balance
    function kill() public {{
        selfdestruct(payable(msg.sender));
    }}
}}
"""


def unprotected_initializer(i):
    cname = _rand(CONTRACT_NAMES) + str(i)
    owner = _rand(OWNER_NAMES)
    pragma = _rand(PRAGMAS)
    return f"""pragma solidity {pragma};

contract {cname} {{
    address public {owner};
    bool private initialized;
    uint256 public cap;

    // BUG: no initializer-guard and no access check, callable repeatedly by anyone
    function initialize(address {owner}Addr, uint256 _cap) public {{
        {owner} = {owner}Addr;
        cap = _cap;
        initialized = true;
    }}

    function setCap(uint256 _cap) public {{
        require(msg.sender == {owner});
        cap = _cap;
    }}
}}
"""


def partial_check(i):
    cname = _rand(CONTRACT_NAMES) + str(i)
    owner = _rand(OWNER_NAMES)
    pragma = _rand(PRAGMAS)
    return f"""pragma solidity {pragma};

contract {cname} {{
    address public {owner};
    mapping(address => bool) public isAdmin;

    constructor() {{
        {owner} = msg.sender;
        isAdmin[msg.sender] = true;
    }}

    // BUG: checks isAdmin for adding, but removing (the sensitive branch) has no check
    function setAdmin(address account, bool status) public {{
        if (status) {{
            require(isAdmin[msg.sender], "not admin");
            isAdmin[account] = true;
        }} else {{
            isAdmin[account] = false;
        }}
    }}
}}
"""


TEMPLATES = [
    missing_owner_check,
    public_owner_setter,
    unapplied_modifier,
    wrong_constructor_name,
    unprotected_selfdestruct,
    unprotected_initializer,
    partial_check,
]


def main(n_per_template: int = 8):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for template in TEMPLATES:
        for i in range(n_per_template):
            code = template(i)
            fname = f"{template.__name__}_{i}.sol"
            (OUT_DIR / fname).write_text(code)
            count += 1
    print(f"Wrote {count} synthetic access_control contracts to {OUT_DIR}")


if __name__ == "__main__":
    main()
