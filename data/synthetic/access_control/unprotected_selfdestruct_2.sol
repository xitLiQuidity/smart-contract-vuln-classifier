pragma solidity ^0.4.26;

contract Router2 {
    address public controller;

    constructor() {
        controller = msg.sender;
    }

    function deposit() public payable {}

    // BUG: anyone can kill the contract and steal the balance
    function kill() public {
        selfdestruct(payable(msg.sender));
    }
}
