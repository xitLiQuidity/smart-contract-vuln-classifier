pragma solidity ^0.5.0;

contract Vault1 {
    address public governor;
    mapping(address => bool) public isAdmin;

    constructor() {
        governor = msg.sender;
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
