pragma solidity ^0.8.0;

contract Registry2 {
    address public controller;

    constructor() {
        controller = msg.sender;
    }

    modifier onlyController() {
        require(msg.sender == controller, "not authorized");
        _;
    }

    // BUG: takes over privileged role, missing onlyController modifier
    function setController(address newController) public {
        controller = newController;
    }

    function withdrawAll() public onlyController {
        payable(controller).transfer(address(this).balance);
    }
}
