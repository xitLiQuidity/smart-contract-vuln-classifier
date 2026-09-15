pragma solidity ^0.8.20;

contract Pool5 {
    address public admin;

    constructor() {
        admin = msg.sender;
    }

    function deposit() public payable {}

    // BUG: anyone can kill the contract and steal the balance
    function kill() public {
        selfdestruct(payable(msg.sender));
    }
}
