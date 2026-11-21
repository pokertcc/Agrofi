// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/MockUSDC.sol";
import "../src/AgroNFT.sol";
import "../src/LendingPool.sol";

contract AgroFiTest is Test {
    MockUSDC public usdc;
    AgroNFT public agroNFT;
    LendingPool public pool;

    address public admin = address(1);
    address public oracle = address(2);
    address public lender = address(3);
    address public farmer = address(4);
    address public liquidator = address(5);

    uint256 public constant APPRAISAL_VALUE = 100_000 * 1e6; // $100,000 USDC
    string public constant TOKEN_URI = "ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";

    function setUp() public {
        vm.startPrank(admin);

        // Deploy contracts
        usdc = new MockUSDC();
        agroNFT = new AgroNFT();
        pool = new LendingPool(address(usdc), address(agroNFT));

        // Authorize pool and oracle on AgroNFT
        agroNFT.setAuthorizedLendingPool(address(pool), true);
        agroNFT.setAuthorizedOracle(oracle, true);

        // Authorize oracle on LendingPool
        pool.setAuthorizedOracle(oracle, true);

        vm.stopPrank();

        // Fund accounts with MockUSDC
        usdc.mint(lender, 500_000 * 1e6); // $500,000 USDC for liquidity
        usdc.mint(liquidator, 100_000 * 1e6); // $100,000 USDC for liquidation
        usdc.mint(farmer, 10_000 * 1e6); // $10,000 USDC for repayments

        // Lender provides liquidity to pool
        vm.startPrank(lender);
        usdc.approve(address(pool), type(uint256).max);
        pool.depositLiquidity(300_000 * 1e6); // Deposit $300,000 USDC
        vm.stopPrank();
    }

    // ==========================================
    // SPRINT 1 TESTS: MockUSDC
    // ==========================================

    function test_MockUSDC_DecimalsAndMint() public {
        assertEq(usdc.decimals(), 6);

        address testUser = address(0x99);
        uint256 mintAmount = 1_000 * 1e6;
        usdc.mint(testUser, mintAmount);

        assertEq(usdc.balanceOf(testUser), mintAmount);
    }

    // ==========================================
    // SPRINT 2 TESTS: AgroNFT & LendingPool
    // ==========================================

    function test_AgroNFT_MintCollateral() public {
        vm.prank(oracle);
        uint256 tokenId = agroNFT.mintCollateral(farmer, TOKEN_URI, APPRAISAL_VALUE);

        assertEq(tokenId, 1);
        assertEq(agroNFT.ownerOf(tokenId), farmer);
        assertEq(agroNFT.tokenURI(tokenId), TOKEN_URI);

        AgroNFT.CollateralData memory data = agroNFT.getCollateralData(tokenId);
        assertEq(data.appraisalValue, APPRAISAL_VALUE);
        assertEq(data.ltv, 6000); // Default 60.00%
        assertEq(data.healthFactor, 15000); // Default 1.50
        assertFalse(data.isCollateralized);
    }

    function test_AgroNFT_UpdateRiskParameters() public {
        vm.prank(oracle);
        uint256 tokenId = agroNFT.mintCollateral(farmer, TOKEN_URI, APPRAISAL_VALUE);

        // Update via authorized oracle
        vm.prank(oracle);
        agroNFT.updateLTVAndHealthFactor(tokenId, 7000, 18000);

        AgroNFT.CollateralData memory data = agroNFT.getCollateralData(tokenId);
        assertEq(data.ltv, 7000);
        assertEq(data.healthFactor, 18000);

        // Unauthorized caller reverts
        vm.prank(address(0xdead));
        vm.expectRevert("AgroNFT: caller not authorized to update risk");
        agroNFT.updateLTVAndHealthFactor(tokenId, 5000, 12000);
    }

    function test_LendingPool_DepositCollateralAndBorrow() public {
        // Mint NFT to farmer
        vm.prank(oracle);
        uint256 tokenId = agroNFT.mintCollateral(farmer, TOKEN_URI, APPRAISAL_VALUE);

        // Farmer deposits NFT into LendingPool
        vm.startPrank(farmer);
        agroNFT.approve(address(pool), tokenId);
        pool.depositCollateral(tokenId);

        assertEq(agroNFT.ownerOf(tokenId), address(pool));
        assertTrue(agroNFT.getCollateralData(tokenId).isCollateralized);

        // Check max borrow: 100,000 * 60% = 60,000 USDC
        uint256 maxBorrow = pool.getMaxBorrowable(tokenId);
        assertEq(maxBorrow, 60_000 * 1e6);

        // Farmer borrows 50,000 USDC
        uint256 borrowAmount = 50_000 * 1e6;
        uint256 balBefore = usdc.balanceOf(farmer);
        pool.borrow(tokenId, borrowAmount);
        uint256 balAfter = usdc.balanceOf(farmer);

        assertEq(balAfter - balBefore, borrowAmount);

        LendingPool.Loan memory loan = pool.getLoan(tokenId);
        assertEq(loan.debt, borrowAmount);
        assertEq(loan.borrower, farmer);
        assertTrue(loan.isActive);
        vm.stopPrank();
    }

    function test_LendingPool_BorrowExceedingLTVReverts() public {
        vm.prank(oracle);
        uint256 tokenId = agroNFT.mintCollateral(farmer, TOKEN_URI, APPRAISAL_VALUE);

        vm.startPrank(farmer);
        agroNFT.approve(address(pool), tokenId);
        pool.depositCollateral(tokenId);

        // Max borrow is 60,000 USDC. Borrowing 65,000 must revert
        vm.expectRevert("LendingPool: borrow exceeds maximum LTV capacity");
        pool.borrow(tokenId, 65_000 * 1e6);
        vm.stopPrank();
    }

    function test_LendingPool_RepayAndWithdrawCollateral() public {
        vm.prank(oracle);
        uint256 tokenId = agroNFT.mintCollateral(farmer, TOKEN_URI, APPRAISAL_VALUE);

        vm.startPrank(farmer);
        agroNFT.approve(address(pool), tokenId);
        pool.depositCollateral(tokenId);

        uint256 borrowAmount = 40_000 * 1e6;
        pool.borrow(tokenId, borrowAmount);

        // Try to withdraw while debt > 0 -> Revert
        vm.expectRevert("LendingPool: cannot withdraw collateral with active debt");
        pool.withdrawCollateral(tokenId);

        // Approve and repay full debt
        usdc.approve(address(pool), borrowAmount);
        pool.repay(tokenId, borrowAmount);

        LendingPool.Loan memory loan = pool.getLoan(tokenId);
        assertEq(loan.debt, 0);

        // Withdraw collateral NFT
        pool.withdrawCollateral(tokenId);
        assertEq(agroNFT.ownerOf(tokenId), farmer);
        assertFalse(agroNFT.getCollateralData(tokenId).isCollateralized);
        vm.stopPrank();
    }

    // ==========================================
    // SPRINT 3 & 4 TESTS: Risk Invalidation & Parametric Liquidation
    // ==========================================

    function test_LendingPool_ParametricLiquidation() public {
        vm.prank(oracle);
        uint256 tokenId = agroNFT.mintCollateral(farmer, TOKEN_URI, APPRAISAL_VALUE);

        vm.startPrank(farmer);
        agroNFT.approve(address(pool), tokenId);
        pool.depositCollateral(tokenId);

        uint256 borrowAmount = 50_000 * 1e6;
        pool.borrow(tokenId, borrowAmount);
        vm.stopPrank();

        // While solvent (healthFactor = 15000 >= 10000), liquidation must revert
        vm.startPrank(liquidator);
        usdc.approve(address(pool), borrowAmount);
        vm.expectRevert("LendingPool: collateral is solvent; cannot liquidate");
        pool.executeParametricLiquidation(tokenId);
        vm.stopPrank();

        // Oracle injects adverse agro event: Severe drought drops Health Factor to 8500 (0.85 < 1.00)
        vm.prank(oracle);
        pool.updateLTVAndHealthFactor(tokenId, 4000, 8500);

        // Liquidator triggers parametric liquidation
        vm.startPrank(liquidator);
        pool.executeParametricLiquidation(tokenId);
        vm.stopPrank();

        // Verifications:
        // 1. Debt is cleared in pool
        LendingPool.Loan memory loan = pool.getLoan(tokenId);
        assertEq(loan.debt, 0);
        assertFalse(loan.isActive);

        // 2. Liquidator receives AgroNFT (harvest asset seized programmatically)
        assertEq(agroNFT.ownerOf(tokenId), liquidator);

        // 3. Pool liquidity is preserved (liquidator paid the debt)
        assertEq(pool.availableLiquidity(), 300_000 * 1e6);
    }
}
