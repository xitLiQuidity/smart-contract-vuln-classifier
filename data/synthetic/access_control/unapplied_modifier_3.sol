pragma solidity ^0.5.0;

contract Pool3 {
    address public controller;
    bool public paused;

    constructor() {
        controller = msg.sender;
    }

    modifier onlyController() {
        require(msg.sender == controller, "caller is not the controller");
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
