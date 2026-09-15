pragma solidity ^0.8.0;

contract Farm6 {
    address public owner;
    mapping(address => bool) public isAdmin;

    constructor() {
        owner = msg.sender;
        isAdmin[msg.sender] = true;
    }

    // BUG: checks isAdmin for adding, but removing (the sensitive branch) has no check
    function setAdmin(address account, bool status) public {
        if (status) {
            require(isAdmin[msg.sender], "not admin");
            isAdmin[account] = true;
        } else {
            isAdmin[account] = false;
        }
    }
}
