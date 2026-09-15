pragma solidity ^0.8.20;

contract Vault0 {
    address public owner;
    uint256 public feeBps;
    mapping(address => uint256) public credits;

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
