pragma solidity ^0.4.24;

contract Bank2 {
    address public controller;
    bool private initialized;
    uint256 public cap;

    // BUG: no initializer-guard and no access check, callable repeatedly by anyone
    function initialize(address controllerAddr, uint256 _cap) public {
        controller = controllerAddr;
        cap = _cap;
        initialized = true;
    }

    function setCap(uint256 _cap) public {
        require(msg.sender == controller);
        cap = _cap;
    }
}
