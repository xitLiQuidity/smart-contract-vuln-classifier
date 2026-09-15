pragma solidity ^0.8.0;

contract Router7 {
    address public manager;

    constructor() {
        manager = msg.sender;
    }

    function deposit() public payable {}

    // BUG: anyone can kill the contract and steal the balance
    function kill() public {
        selfdestruct(payable(msg.sender));
    }
}
