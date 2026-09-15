pragma solidity ^0.4.18;

contract Router3 {
    address public controller;
    uint256 public totalSupply;

    // BUG: function name doesn't match contract name (pre-0.4.22 "constructor"),
    // so this is just a normal public function anyone can call to become controller
    function router3() public {
        controller = msg.sender;
    }

    function mint(uint256 amount) public {
        require(msg.sender == controller);
        totalSupply += amount;
    }
}
