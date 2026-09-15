pragma solidity ^0.8.20;

contract Farm4 {
    address public owner;
    bool private initialized;
    uint256 public cap;

    // BUG: no initializer-guard and no access check, callable repeatedly by anyone
    function initialize(address ownerAddr, uint256 _cap) public {
        owner = ownerAddr;
        cap = _cap;
        initialized = true;
    }

    function setCap(uint256 _cap) public {
        require(msg.sender == owner);
        cap = _cap;
    }
}
