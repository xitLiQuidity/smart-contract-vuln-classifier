pragma solidity ^0.4.26;

contract Registry3 {
    address public controller;
    mapping(address => bool) public isAdmin;

    constructor() {
        controller = msg.sender;
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
