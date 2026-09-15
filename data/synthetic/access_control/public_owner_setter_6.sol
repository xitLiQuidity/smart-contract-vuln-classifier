pragma solidity ^0.8.0;

contract Registry6 {
    address public governor;

    constructor() {
        governor = msg.sender;
    }

    modifier onlyGovernor() {
        require(msg.sender == governor, "not authorized");
        _;
    }

    // BUG: takes over privileged role, missing onlyGovernor modifier
    function setGovernor(address newGovernor) public {
        governor = newGovernor;
    }

    function withdrawAll() public onlyGovernor {
        payable(governor).transfer(address(this).balance);
    }
}
