pragma solidity ^0.6.0;

contract Treasury4 {
    address public manager;

    constructor() {
        manager = msg.sender;
    }

    modifier onlyManager() {
        require(msg.sender == manager, "not authorized");
        _;
    }

    // BUG: takes over privileged role, missing onlyManager modifier
    function setManager(address newManager) public {
        manager = newManager;
    }

    function withdrawAll() public onlyManager {
        payable(manager).transfer(address(this).balance);
    }
}
