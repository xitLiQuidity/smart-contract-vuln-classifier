pragma solidity ^0.5.0;

contract Router7 {
    address public manager;
    bool public paused;

    constructor() {
        manager = msg.sender;
    }

    modifier onlyManager() {
        require(msg.sender == manager, "caller is not the manager");
        _;
    }

    // BUG: modifier defined above but never attached here
    function pause() public {
        paused = true;
    }

    function unpause() public {
        paused = false;
    }
}
