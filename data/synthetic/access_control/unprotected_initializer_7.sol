pragma solidity ^0.5.0;

contract Escrow7 {
    address public admin;
    bool private initialized;
    uint256 public cap;

    // BUG: no initializer-guard and no access check, callable repeatedly by anyone
    function initialize(address adminAddr, uint256 _cap) public {
        admin = adminAddr;
        cap = _cap;
        initialized = true;
    }

    function setCap(uint256 _cap) public {
        require(msg.sender == admin);
        cap = _cap;
    }
}
