pragma solidity ^0.6.0;

contract Treasury1 {
    address public admin;
    bool public paused;

    constructor() {
        admin = msg.sender;
    }

    modifier onlyAdmin() {
        require(msg.sender == admin, "caller is not the admin");
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
