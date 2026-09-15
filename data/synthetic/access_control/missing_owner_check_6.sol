pragma solidity ^0.4.24;

contract Bank6 {
    address public governor;
    uint256 public feeBps;
    mapping(address => uint256) public shares;

    constructor() {
        governor = msg.sender;
    }

    // BUG: anyone can change the fee, no governor check
    function setFeeBps(uint256 newFeeBps) public {
        feeBps = newFeeBps;
    }

    function sweep(address payable to) public {
        to.transfer(address(this).balance);
    }
}
