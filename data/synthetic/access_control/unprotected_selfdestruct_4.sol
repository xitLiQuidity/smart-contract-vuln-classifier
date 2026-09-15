pragma solidity ^0.4.24;

contract Treasury4 {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function deposit() public payable {}

    // BUG: anyone can kill the contract and steal the balance
    function kill() public {
        selfdestruct(payable(msg.sender));
    }
}
