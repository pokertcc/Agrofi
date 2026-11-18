// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./AgroNFT.sol";

interface IERC20Local {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
}

/**
 * @title LendingPool
 * @notice Protocolo de concessão de crédito com colateralização de safras em AgroNFT e liquidação paramétrica.
 */
contract LendingPool is IERC721Receiver {
    IERC20Local public immutable usdc;
    AgroNFT public immutable agroNFT;

    address public owner;
    uint256 public constant BASIS_POINTS = 10000;
    uint256 public constant MIN_HEALTH_FACTOR = 10000; // 1.00x (Threshold de liquidação paramétrica)

    uint256 public totalLiquidityDeposited;
    uint256 public totalBorrowedAmount;

    struct Loan {
        address borrower;
        uint256 debt;
        bool isActive;
    }

    mapping(uint256 => Loan) public loans;
    mapping(address => uint256) public liquidityBalances;
    mapping(address => bool) public authorizedOracles;

    event LiquidityDeposited(address indexed lender, uint256 amount);
    event LiquidityWithdrawn(address indexed lender, uint256 amount);
    event CollateralDeposited(address indexed borrower, uint256 indexed tokenId);
    event CollateralWithdrawn(address indexed borrower, uint256 indexed tokenId);
    event Borrowed(address indexed borrower, uint256 indexed tokenId, uint256 amount);
    event Repaid(address indexed borrower, uint256 indexed tokenId, uint256 amount);
    event ParametricLiquidation(uint256 indexed tokenId, address indexed liquidator, address indexed borrower, uint256 debtCovered);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "LendingPool: unauthorized");
        _;
    }

    modifier onlyOracle() {
        require(msg.sender == owner || authorizedOracles[msg.sender], "LendingPool: not authorized oracle");
        _;
    }

    constructor(address _usdc, address _agroNFT) {
        require(_usdc != address(0) && _agroNFT != address(0), "LendingPool: zero address");
        owner = msg.sender;
        usdc = IERC20Local(_usdc);
        agroNFT = AgroNFT(_agroNFT);
        authorizedOracles[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    function setAuthorizedOracle(address oracle, bool auth) external onlyOwner {
        authorizedOracles[oracle] = auth;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "LendingPool: zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function renounceOwnership() external onlyOwner {
        emit OwnershipTransferred(owner, address(0));
        owner = address(0);
    }

    function depositLiquidity(uint256 amount) external {
        require(amount > 0, "LendingPool: amount must be > 0");
        require(usdc.transferFrom(msg.sender, address(this), amount), "LendingPool: USDC transfer failed");

        liquidityBalances[msg.sender] += amount;
        totalLiquidityDeposited += amount;

        emit LiquidityDeposited(msg.sender, amount);
    }

    function withdrawLiquidity(uint256 amount) external {
        require(amount > 0, "LendingPool: amount must be > 0");
        require(liquidityBalances[msg.sender] >= amount, "LendingPool: insufficient lender balance");
        require(availableLiquidity() >= amount, "LendingPool: insufficient pool liquidity");

        liquidityBalances[msg.sender] -= amount;
        totalLiquidityDeposited -= amount;

        require(usdc.transfer(msg.sender, amount), "LendingPool: USDC transfer failed");
        emit LiquidityWithdrawn(msg.sender, amount);
    }

    function availableLiquidity() public view returns (uint256) {
        return totalLiquidityDeposited >= totalBorrowedAmount ? totalLiquidityDeposited - totalBorrowedAmount : 0;
    }

    function depositCollateral(uint256 tokenId) external {
        require(agroNFT.ownerOf(tokenId) == msg.sender, "LendingPool: caller is not NFT owner");
        require(!loans[tokenId].isActive, "LendingPool: collateral already deposited");

        agroNFT.transferFrom(msg.sender, address(this), tokenId);
        agroNFT.setCollateralStatus(tokenId, true);

        loans[tokenId] = Loan({
            borrower: msg.sender,
            debt: 0,
            isActive: true
        });

        emit CollateralDeposited(msg.sender, tokenId);
    }

    function getMaxBorrowable(uint256 tokenId) public view returns (uint256) {
        (uint256 appraisal, uint256 ltv, , ) = agroNFT.getCollateralData(tokenId);
        return (appraisal * ltv) / BASIS_POINTS;
    }

    function borrow(uint256 tokenId, uint256 amount) external {
        Loan storage loan = loans[tokenId];
        require(loan.isActive, "LendingPool: loan position inactive");
        require(loan.borrower == msg.sender, "LendingPool: caller is not borrower");
        require(amount > 0, "LendingPool: amount must be > 0");

        (, , uint256 healthFactor, ) = agroNFT.getCollateralData(tokenId);
        require(healthFactor >= MIN_HEALTH_FACTOR, "LendingPool: collateral health factor too low");

        uint256 maxBorrowable = getMaxBorrowable(tokenId);
        require(loan.debt + amount <= maxBorrowable, "LendingPool: requested amount exceeds max LTV");
        require(availableLiquidity() >= amount, "LendingPool: insufficient pool liquidity");

        loan.debt += amount;
        totalBorrowedAmount += amount;

        require(usdc.transfer(msg.sender, amount), "LendingPool: USDC transfer failed");
        emit Borrowed(msg.sender, tokenId, amount);
    }

    function repay(uint256 tokenId, uint256 amount) external {
        Loan storage loan = loans[tokenId];
        require(loan.isActive, "LendingPool: loan position inactive");
        require(amount > 0, "LendingPool: amount must be > 0");

        uint256 actualRepayment = amount > loan.debt ? loan.debt : amount;
        require(usdc.transferFrom(msg.sender, address(this), actualRepayment), "LendingPool: USDC transfer failed");

        loan.debt -= actualRepayment;
        totalBorrowedAmount -= actualRepayment;

        emit Repaid(msg.sender, tokenId, actualRepayment);
    }

    function withdrawCollateral(uint256 tokenId) external {
        Loan storage loan = loans[tokenId];
        require(loan.isActive, "LendingPool: loan position inactive");
        require(loan.borrower == msg.sender, "LendingPool: caller is not borrower");
        require(loan.debt == 0, "LendingPool: cannot withdraw with outstanding debt");

        loan.isActive = false;
        loan.borrower = address(0);

        agroNFT.setCollateralStatus(tokenId, false);
        agroNFT.transferFrom(address(this), msg.sender, tokenId);

        emit CollateralWithdrawn(msg.sender, tokenId);
    }

    function executeParametricLiquidation(uint256 tokenId) external {
        Loan storage loan = loans[tokenId];
        require(loan.isActive, "LendingPool: loan position inactive");
        require(loan.debt > 0, "LendingPool: no debt to liquidate");

        (, , uint256 healthFactor, ) = agroNFT.getCollateralData(tokenId);
        require(healthFactor < MIN_HEALTH_FACTOR, "LendingPool: position solvent, cannot liquidate");

        uint256 debtToCover = loan.debt;
        address originalBorrower = loan.borrower;

        // Liquidante quita a divida ativa
        require(usdc.transferFrom(msg.sender, address(this), debtToCover), "LendingPool: USDC repayment failed");

        loan.debt = 0;
        loan.isActive = false;
        loan.borrower = address(0);
        totalBorrowedAmount -= debtToCover;

        // NFT do colateral e transferido imediatamente ao liquidante
        agroNFT.setCollateralStatus(tokenId, false);
        agroNFT.transferFrom(address(this), msg.sender, tokenId);

        emit ParametricLiquidation(tokenId, msg.sender, originalBorrower, debtToCover);
    }

    function updateLTVAndHealthFactor(uint256 tokenId, uint256 ltv, uint256 healthFactor) external onlyOracle {
        agroNFT.updateLTVAndHealthFactor(tokenId, ltv, healthFactor);
    }

    function getLoan(uint256 tokenId) external view returns (address borrower, uint256 debt, bool isActive) {
        Loan memory l = loans[tokenId];
        return (l.borrower, l.debt, l.isActive);
    }

    function onERC721Received(address, address, uint256, bytes calldata) external pure override returns (bytes4) {
        return this.onERC721Received.selector;
    }
}
