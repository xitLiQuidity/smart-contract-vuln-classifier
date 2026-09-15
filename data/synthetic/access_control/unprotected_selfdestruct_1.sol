pragma solidity ^0.6.0;

contract Bank1 {
    address public governor;

    constructor() {
        governor = msg.sender;
    }

    function deposit() public payable {}

    // BUG: anyone can kill the contract and steal the balance
    function kill() public {
        selfdestruct(payable(msg.sender));
    }
}
