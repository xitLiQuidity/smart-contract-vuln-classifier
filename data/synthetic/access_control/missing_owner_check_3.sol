pragma solidity ^0.4.24;

contract Vault3 {
    address public owner;
    uint256 public feeBps;
    mapping(address => uint256) public shares;

    constructor() {
        owner = msg.sender;
    }

    // BUG: anyone can change the fee, no owner check
    function setFeeBps(uint256 newFeeBps) public {
        feeBps = newFeeBps;
    }

    function sweep(address payable to) public {
        to.transfer(address(this).balance);
    }
}
