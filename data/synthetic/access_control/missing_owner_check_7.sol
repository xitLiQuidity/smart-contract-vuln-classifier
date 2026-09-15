pragma solidity ^0.5.0;

contract Registry7 {
    address public manager;
    uint256 public feeBps;
    mapping(address => uint256) public shares;

    constructor() {
        manager = msg.sender;
    }

    // BUG: anyone can change the fee, no manager check
    function setFeeBps(uint256 newFeeBps) public {
        feeBps = newFeeBps;
    }

    function sweep(address payable to) public {
        to.transfer(address(this).balance);
    }
}
