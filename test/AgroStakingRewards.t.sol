// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/AgroToken.sol";
import "../src/MockUSDC.sol";
import "../src/AgroStakingRewards.sol";

contract AgroStakingRewardsTest is Test {
    AgroToken public agroToken;
    MockUSDC public usdc;
    AgroStakingRewards public staking;

    address public admin = address(0xAA11);
    address public investor = address(0xBB22);

    function setUp() public {
        vm.startPrank(admin);
        
        // 1. Deploy MockUSDC (6 decimais)
        usdc = new MockUSDC();
        
        // 2. Deploy AgroToken (18 decimais)
        agroToken = new AgroToken(admin);
        
        // 3. Deploy AgroStakingRewards com 22% APY (2200 bps)
        staking = new AgroStakingRewards(address(usdc), address(agroToken), 2200);
        
        // 4. Autorizar o contrato de Staking como minter no AgroToken
        agroToken.setAuthorizedMinter(address(staking), true);

        // 5. Enviar 10.000 USDC (1e6) para o investidor testar
        usdc.mint(investor, 10_000 * 1e6);

        vm.stopPrank();
    }

    function testInitialConfiguration() public view {
        assertEq(address(staking.stakingToken()), address(usdc));
        assertEq(address(staking.rewardsToken()), address(agroToken));
        assertEq(staking.apyBasisPoints(), 2200);
        assertEq(staking.totalStaked(), 0);
        assertEq(staking.stakingDecimals(), 6);
    }

    function testStake() public {
        vm.startPrank(investor);
        usdc.approve(address(staking), 1_000 * 1e6);
        staking.stake(1_000 * 1e6);
        vm.stopPrank();

        assertEq(staking.totalStaked(), 1_000 * 1e6);
        assertEq(staking.stakedBalance(investor), 1_000 * 1e6);
        assertEq(usdc.balanceOf(investor), 9_000 * 1e6);
    }

    function testAccrueRewardsOverOneYear() public {
        vm.startPrank(investor);
        usdc.approve(address(staking), 10_000 * 1e6);
        staking.stake(10_000 * 1e6);
        vm.stopPrank();

        // Avançar 1 ano (365 dias) no tempo da blockchain
        vm.warp(block.timestamp + 365 days);

        // Com 10.000 USDC ($10k) e 22% APY, o rendimento deve ser exatamente 2.200 $AGRO (18 decimais)
        uint256 expectedReward = 2_200 * 1e18;
        uint256 earnedReward = staking.earned(investor);
        assertEq(earnedReward, expectedReward);
    }

    function testClaimRewards() public {
        vm.startPrank(investor);
        usdc.approve(address(staking), 10_000 * 1e6);
        staking.stake(10_000 * 1e6);

        // Avançar 180 dias (meio ano)
        vm.warp(block.timestamp + 180 days);

        uint256 pending = staking.earned(investor);
        assertGt(pending, 0);

        uint256 claimed = staking.claimRewards();
        assertEq(claimed, pending);
        assertEq(agroToken.balanceOf(investor), claimed);
        assertEq(staking.earned(investor), 0);
        vm.stopPrank();
    }

    function testWithdraw() public {
        vm.startPrank(investor);
        usdc.approve(address(staking), 5_000 * 1e6);
        staking.stake(5_000 * 1e6);

        staking.withdraw(2_000 * 1e6);
        assertEq(staking.stakedBalance(investor), 3_000 * 1e6);
        assertEq(usdc.balanceOf(investor), 7_000 * 1e6);
        vm.stopPrank();
    }

    function testExit() public {
        vm.startPrank(investor);
        usdc.approve(address(staking), 5_000 * 1e6);
        staking.stake(5_000 * 1e6);

        vm.warp(block.timestamp + 30 days);

        staking.exit();
        assertEq(staking.stakedBalance(investor), 0);
        assertEq(usdc.balanceOf(investor), 10_000 * 1e6);
        assertGt(agroToken.balanceOf(investor), 0);
        vm.stopPrank();
    }

    function test_RevertWhen_StakeZero() public {
        vm.startPrank(investor);
        vm.expectRevert("AgroStakingRewards: cannot stake 0");
        staking.stake(0);
        vm.stopPrank();
    }
}
