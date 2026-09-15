pragma solidity ^0.8.20;

contract Pool7 {
    address public admin;
    mapping(address => bool) public isAdmin;

    constructor() {
        admin = msg.sender;
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
