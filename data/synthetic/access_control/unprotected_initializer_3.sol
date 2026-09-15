pragma solidity ^0.4.26;

contract Bank3 {
    address public manager;
    bool private initialized;
    uint256 public cap;

    // BUG: no initializer-guard and no access check, callable repeatedly by anyone
    function initialize(address managerAddr, uint256 _cap) public {
        manager = managerAddr;
        cap = _cap;
        initialized = true;
    }

    function setCap(uint256 _cap) public {
        require(msg.sender == manager);
        cap = _cap;
    }
}
