pragma solidity ^0.4.26;

contract Bank5 {
    address public governor;
    bool private initialized;
    uint256 public cap;

    // BUG: no initializer-guard and no access check, callable repeatedly by anyone
    function initialize(address governorAddr, uint256 _cap) public {
        governor = governorAddr;
        cap = _cap;
        initialized = true;
    }

    function setCap(uint256 _cap) public {
        require(msg.sender == governor);
        cap = _cap;
    }
}
