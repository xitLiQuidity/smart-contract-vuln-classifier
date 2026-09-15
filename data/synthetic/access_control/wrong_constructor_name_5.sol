pragma solidity ^0.4.18;

contract Registry5 {
    address public admin;
    uint256 public totalSupply;

    // BUG: function name doesn't match contract name (pre-0.4.22 "constructor"),
    // so this is just a normal public function anyone can call to become admin
    function registry5() public {
        admin = msg.sender;
    }

    function mint(uint256 amount) public {
        require(msg.sender == admin);
        totalSupply += amount;
    }
}
