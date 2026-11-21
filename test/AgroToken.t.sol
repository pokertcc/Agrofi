// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/AgroToken.sol";

contract AgroTokenTest is Test {
    AgroToken public agroToken;
    address public owner = address(0x1);
    address public alice = address(0x2);
    address public pool = address(0x3);

    function setUp() public {
        vm.prank(owner);
        agroToken = new AgroToken(owner);
    }

    function testInitialSupplyAndMetadata() public view {
        assertEq(agroToken.name(), "AgroFi Protocol Token");
        assertEq(agroToken.symbol(), "AGRO");
        assertEq(agroToken.decimals(), 18);
        assertEq(agroToken.totalSupply(), 20_000_000 * 10 ** 18);
        assertEq(agroToken.balanceOf(owner), 20_000_000 * 10 ** 18);
    }

    function testTransfer() public {
        vm.prank(owner);
        agroToken.transfer(alice, 1000 * 10 ** 18);
        assertEq(agroToken.balanceOf(alice), 1000 * 10 ** 18);
        assertEq(agroToken.balanceOf(owner), (20_000_000 - 1000) * 10 ** 18);
    }

    function testMintRewardsByAuthorizedPool() public {
        vm.prank(owner);
        agroToken.setAuthorizedMinter(pool, true);

        vm.prank(pool);
        agroToken.mintRewards(alice, 5000 * 10 ** 18);
        assertEq(agroToken.balanceOf(alice), 5000 * 10 ** 18);
        assertEq(agroToken.totalSupply(), 20_005_000 * 10 ** 18);
    }

    function test_RevertWhen_MintRewardsUnauthorized() public {
        vm.prank(alice);
        vm.expectRevert("AgroToken: caller not authorized minter");
        agroToken.mintRewards(alice, 5000 * 10 ** 18);
    }

    function testBurn() public {
        vm.prank(owner);
        agroToken.burn(1_000_000 * 10 ** 18);
        assertEq(agroToken.totalSupply(), 19_000_000 * 10 ** 18);
        assertEq(agroToken.balanceOf(owner), 19_000_000 * 10 ** 18);
    }
}
