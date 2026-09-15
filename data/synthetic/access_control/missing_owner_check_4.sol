pragma solidity ^0.8.0;

contract Vault4 {
    address public admin;
    uint256 public feeBps;
    mapping(address => uint256) public shares;

    constructor() {
        admin = msg.sender;
    }

    // BUG: anyone can change the fee, no admin check
    function setFeeBps(uint256 newFeeBps) public {
        feeBps = newFeeBps;
    }

    function sweep(address payable to) public {
        to.transfer(address(this).balance);
    }
}
