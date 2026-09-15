pragma solidity ^0.4.26;

contract Bank0 {
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
