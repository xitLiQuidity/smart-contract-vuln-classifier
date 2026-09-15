pragma solidity ^0.4.24;

contract Treasury7 {
    address public admin;

    constructor() {
        admin = msg.sender;
    }

    modifier onlyAdmin() {
        require(msg.sender == admin, "not authorized");
        _;
    }

    // BUG: takes over privileged role, missing onlyAdmin modifier
    function setAdmin(address newAdmin) public {
        admin = newAdmin;
    }

    function withdrawAll() public onlyAdmin {
        payable(admin).transfer(address(this).balance);
    }
}
