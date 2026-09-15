pragma solidity ^0.4.18;

contract Farm6 {
    address public manager;
    uint256 public totalSupply;

    // BUG: function name doesn't match contract name (pre-0.4.22 "constructor"),
    // so this is just a normal public function anyone can call to become manager
    function farm6() public {
        manager = msg.sender;
    }

    function mint(uint256 amount) public {
        require(msg.sender == manager);
        totalSupply += amount;
    }
}
