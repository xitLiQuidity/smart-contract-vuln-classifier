pragma solidity ^0.4.24;

contract Router1 {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "not authorized");
        _;
    }

    // BUG: takes over privileged role, missing onlyOwner modifier
    function setOwner(address newOwner) public {
        owner = newOwner;
    }

    function withdrawAll() public onlyOwner {
        payable(owner).transfer(address(this).balance);
    }
}
