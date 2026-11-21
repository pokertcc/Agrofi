// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@openzeppelin/contracts/token/ERC721/utils/ERC721Holder.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "./MockUSDC.sol";
import "./AgroNFT.sol";

/**
 * @title LendingPool
 * @dev Decentralized liquidity pool and collateralized lending contract for AgroFi.
 * Implements parametric lending against tokenized crops (AgroNFT) without traditional court reliance.
 */
contract LendingPool is ERC721Holder, ReentrancyGuard, Ownable {
    MockUSDC public immutable usdc;
    AgroNFT public immutable agroNFT;

    // Minimum Health Factor required to borrow and stay solvent (10000 = 1.00x)
    uint256 public constant MIN_HEALTH_FACTOR = 10000;
    uint256 public constant BASIS_POINTS = 10000;

    struct Loan {
        address borrower;
        uint256 debt;           // Outstanding debt in micro-USDC (6 decimals)
        bool isActive;          // True when collateral is held in pool
        uint256 borrowedAt;     // Timestamp of last borrow
    }

    // Mapping from AgroNFT tokenId to Loan
    mapping(uint256 => Loan) public loans;

    // Liquidity providers ledger
    mapping(address => uint256) public liquidityBalances;
    uint256 public totalLiquidityDeposited;
    uint256 public totalBorrowedAmount;

    // Authorized Oracles
    mapping(address => bool) public authorizedOracles;

    // Events
    event LiquidityDeposited(address indexed provider, uint256 amount);
    event LiquidityWithdrawn(address indexed provider, uint256 amount);
    event CollateralDeposited(uint256 indexed tokenId, address indexed borrower);
    event CollateralWithdrawn(uint256 indexed tokenId, address indexed borrower);
    event Borrowed(uint256 indexed tokenId, address indexed borrower, uint256 amount, uint256 totalDebt);
    event Repaid(uint256 indexed tokenId, address indexed payer, uint256 amountRepaid, uint256 remainingDebt);
    event ParametricLiquidationExecuted(
        uint256 indexed tokenId,
        address indexed borrower,
        address indexed liquidator,
        uint256 liquidatedDebt,
        uint256 healthFactor
    );
    event OracleAuthorized(address indexed oracle, bool authorized);

    modifier onlyOracle() {
        require(
            msg.sender == owner() || authorizedOracles[msg.sender],
            "LendingPool: caller not authorized oracle"
        );
        _;
    }

    constructor(address _usdc, address _agroNFT) Ownable(msg.sender) {
        require(_usdc != address(0), "LendingPool: invalid USDC address");
        require(_agroNFT != address(0), "LendingPool: invalid AgroNFT address");
        usdc = MockUSDC(_usdc);
        agroNFT = AgroNFT(_agroNFT);
        authorizedOracles[msg.sender] = true;
        emit OracleAuthorized(msg.sender, true);
    }

    // ==========================================
    // LIQUIDITY PROVIDER FUNCTIONS
    // ==========================================

    /**
     * @notice Lenders deposit MockUSDC to earn yield and fund agricultural credit.
     * @param amount Amount of USDC to deposit (6 decimals)
     */
    function depositLiquidity(uint256 amount) external nonReentrant {
        require(amount > 0, "LendingPool: amount must be > 0");

        liquidityBalances[msg.sender] += amount;
        totalLiquidityDeposited += amount;
        emit LiquidityDeposited(msg.sender, amount);

        bool success = usdc.transferFrom(msg.sender, address(this), amount);
        require(success, "LendingPool: USDC transfer failed");
    }

    /**
     * @notice Lenders withdraw available MockUSDC liquidity.
     * @param amount Amount of USDC to withdraw
     */
    function withdrawLiquidity(uint256 amount) external nonReentrant {
        require(amount > 0, "LendingPool: amount must be > 0");
        require(liquidityBalances[msg.sender] >= amount, "LendingPool: insufficient lender balance");
        require(usdc.balanceOf(address(this)) >= amount, "LendingPool: pool liquidity currently borrowed");

        liquidityBalances[msg.sender] -= amount;
        totalLiquidityDeposited -= amount;
        emit LiquidityWithdrawn(msg.sender, amount);

        bool success = usdc.transfer(msg.sender, amount);
        require(success, "LendingPool: USDC transfer failed");
    }

    // ==========================================
    // COLLATERAL & BORROWING FUNCTIONS
    // ==========================================

    /**
     * @notice Deposits an AgroNFT into the pool as collateral for borrowing.
     * @param tokenId The NFT token ID representing the agricultural asset
     */
    function depositCollateral(uint256 tokenId) external nonReentrant {
        require(agroNFT.ownerOf(tokenId) == msg.sender, "LendingPool: caller does not own AgroNFT");
        require(!loans[tokenId].isActive, "LendingPool: loan already active for this token");

        loans[tokenId] = Loan({
            borrower: msg.sender,
            debt: 0,
            isActive: true,
            borrowedAt: 0
        });
        emit CollateralDeposited(tokenId, msg.sender);

        agroNFT.setCollateralStatus(tokenId, true);
        agroNFT.safeTransferFrom(msg.sender, address(this), tokenId);
    }

    /**
     * @notice Borrows stablecoin (USDC) against the deposited AgroNFT collateral.
     * @param tokenId The ID of the collateralized AgroNFT
     * @param amount USDC amount requested (6 decimals)
     */
    function borrow(uint256 tokenId, uint256 amount) external nonReentrant {
        require(loans[tokenId].isActive, "LendingPool: collateral not deposited");
        require(loans[tokenId].borrower == msg.sender, "LendingPool: caller is not collateral owner");
        require(amount > 0, "LendingPool: borrow amount must be > 0");

        AgroNFT.CollateralData memory col = agroNFT.getCollateralData(tokenId);

        // Verify real-time Health Factor
        require(col.healthFactor >= MIN_HEALTH_FACTOR, "LendingPool: health factor below solvency threshold");

        // Calculate maximum borrow limit: (appraisalValue * LTV) / 10000
        uint256 maxBorrow = (col.appraisalValue * col.ltv) / BASIS_POINTS;
        require(loans[tokenId].debt + amount <= maxBorrow, "LendingPool: borrow exceeds maximum LTV capacity");

        // Verify pool liquidity
        require(usdc.balanceOf(address(this)) >= amount, "LendingPool: insufficient pool liquidity");

        loans[tokenId].debt += amount;
        loans[tokenId].borrowedAt = block.timestamp;
        totalBorrowedAmount += amount;
        emit Borrowed(tokenId, msg.sender, amount, loans[tokenId].debt);

        bool success = usdc.transfer(msg.sender, amount);
        require(success, "LendingPool: USDC transfer failed");
    }

    /**
     * @notice Repays outstanding USDC debt on a loan.
     * @param tokenId The ID of the collateralized AgroNFT
     * @param amount Amount of USDC to repay
     */
    function repay(uint256 tokenId, uint256 amount) external nonReentrant {
        require(loans[tokenId].isActive, "LendingPool: loan is not active");
        require(loans[tokenId].debt > 0, "LendingPool: no outstanding debt");
        require(amount > 0, "LendingPool: repay amount must be > 0");

        uint256 actualRepayment = amount > loans[tokenId].debt ? loans[tokenId].debt : amount;

        loans[tokenId].debt -= actualRepayment;
        totalBorrowedAmount -= actualRepayment;
        emit Repaid(tokenId, msg.sender, actualRepayment, loans[tokenId].debt);

        bool success = usdc.transferFrom(msg.sender, address(this), actualRepayment);
        require(success, "LendingPool: USDC transfer failed");
    }

    /**
     * @notice Withdraws collateral NFT once loan is fully repaid.
     * @param tokenId The ID of the AgroNFT to withdraw
     */
    function withdrawCollateral(uint256 tokenId) external nonReentrant {
        require(loans[tokenId].isActive, "LendingPool: loan is not active");
        require(loans[tokenId].borrower == msg.sender, "LendingPool: caller is not borrower");
        require(loans[tokenId].debt == 0, "LendingPool: cannot withdraw collateral with active debt");

        loans[tokenId].isActive = false;
        address borrower = loans[tokenId].borrower;
        emit CollateralWithdrawn(tokenId, borrower);

        agroNFT.setCollateralStatus(tokenId, false);
        agroNFT.safeTransferFrom(address(this), borrower, tokenId);
    }

    // ==========================================
    // ORACLE & RISK MANAGEMENT FUNCTIONS
    // ==========================================

    /**
     * @notice Updates LTV and Health Factor for a collateral token from the Web3 Oracle / Middleware.
     * @param tokenId The ID of the AgroNFT
     * @param ltv New LTV in basis points (e.g. 5000 = 50%)
     * @param healthFactor New Health Factor scaled by 1e4 (e.g. 9500 = 0.95)
     */
    function updateLTVAndHealthFactor(
        uint256 tokenId,
        uint256 ltv,
        uint256 healthFactor
    ) external onlyOracle {
        agroNFT.updateLTVAndHealthFactor(tokenId, ltv, healthFactor);
    }

    /**
     * @notice Helper allowing the oracle/middleware to mint collateral through the protocol interface.
     */
    function mintCollateral(
        address to,
        string memory tokenURI,
        uint256 appraisalValue
    ) external onlyOracle returns (uint256) {
        return agroNFT.mintCollateral(to, tokenURI, appraisalValue);
    }

    /**
     * @notice Executes parametric liquidation when Health Factor drops below solvency threshold (< 1.00).
     * Bypasses judicial repossession by transferring tokenized harvest rights to liquidator upon debt settlement.
     * @param tokenId The ID of the undercollateralized AgroNFT
     */
    function executeParametricLiquidation(uint256 tokenId) external nonReentrant {
        require(loans[tokenId].isActive, "LendingPool: loan is not active");
        require(loans[tokenId].debt > 0, "LendingPool: loan has no debt");

        AgroNFT.CollateralData memory col = agroNFT.getCollateralData(tokenId);
        require(col.healthFactor < MIN_HEALTH_FACTOR, "LendingPool: collateral is solvent; cannot liquidate");

        uint256 debtToCover = loans[tokenId].debt;
        address borrower = loans[tokenId].borrower;

        loans[tokenId].debt = 0;
        loans[tokenId].isActive = false;
        totalBorrowedAmount -= debtToCover;
        emit ParametricLiquidationExecuted(tokenId, borrower, msg.sender, debtToCover, col.healthFactor);

        bool success = usdc.transferFrom(msg.sender, address(this), debtToCover);
        require(success, "LendingPool: liquidator payment failed");

        agroNFT.setCollateralStatus(tokenId, false);
        agroNFT.safeTransferFrom(address(this), msg.sender, tokenId);
    }

    // ==========================================
    // VIEW & MANAGEMENT HELPERS
    // ==========================================

    function getLoan(uint256 tokenId) external view returns (Loan memory) {
        return loans[tokenId];
    }

    function availableLiquidity() external view returns (uint256) {
        return usdc.balanceOf(address(this));
    }

    function getMaxBorrowable(uint256 tokenId) external view returns (uint256) {
        AgroNFT.CollateralData memory col = agroNFT.getCollateralData(tokenId);
        return (col.appraisalValue * col.ltv) / BASIS_POINTS;
    }

    function setAuthorizedOracle(address oracle, bool authorized) external onlyOwner {
        require(oracle != address(0), "LendingPool: invalid oracle");
        authorizedOracles[oracle] = authorized;
        emit OracleAuthorized(oracle, authorized);
    }
}
