// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title AgroNFT
 * @dev ERC-721 token representing agricultural collateral (crop production, land use right, harvest).
 * Maintains real-time risk parameters (LTV, Health Factor, Appraisal Value) updated by oracles.
 */
contract AgroNFT is ERC721URIStorage, Ownable {
    uint256 private _nextTokenId;

    struct CollateralData {
        uint256 appraisalValue; // In USDC units (6 decimals)
        uint256 ltv; // Basis points (e.g., 6000 = 60.00%)
        uint256 healthFactor; // Scaled by 1e4 (e.g., 15000 = 1.50; 10000 = 1.00 threshold)
        bool isCollateralized; // True when locked in LendingPool
        uint256 mintedAt; // Timestamp of tokenization
    }

    // Mapping from tokenId to CollateralData
    mapping(uint256 => CollateralData) public collaterals;

    // Authorized oracles and lending pools
    mapping(address => bool) public authorizedOracles;
    mapping(address => bool) public authorizedLendingPools;

    // Constants
    uint256 public constant DEFAULT_LTV = 6000; // 60.00%
    uint256 public constant DEFAULT_HEALTH_FACTOR = 15000; // 1.50
    uint256 public constant MAX_LTV = 8500; // 85.00%

    // Events
    event CollateralMinted(
        uint256 indexed tokenId,
        address indexed to,
        string tokenURI,
        uint256 appraisalValue,
        uint256 ltv,
        uint256 healthFactor
    );
    event RiskParametersUpdated(uint256 indexed tokenId, uint256 ltv, uint256 healthFactor);
    event AppraisalUpdated(uint256 indexed tokenId, uint256 newAppraisalValue);
    event CollateralStatusChanged(uint256 indexed tokenId, bool isCollateralized);
    event OracleAuthorizationChanged(address indexed oracle, bool authorized);
    event LendingPoolAuthorizationChanged(address indexed pool, bool authorized);

    modifier onlyAuthorizedUpdater() {
        require(
            msg.sender == owner() || authorizedOracles[msg.sender] || authorizedLendingPools[msg.sender],
            "AgroNFT: caller not authorized to update risk"
        );
        _;
    }

    modifier onlyLendingPool() {
        require(
            msg.sender == owner() || authorizedLendingPools[msg.sender], "AgroNFT: caller not authorized lending pool"
        );
        _;
    }

    constructor() ERC721("AgroFi Agricultural Collateral", "AGRO-NFT") Ownable(msg.sender) {
        _nextTokenId = 1;
        authorizedOracles[msg.sender] = true;
        emit OracleAuthorizationChanged(msg.sender, true);
    }

    /**
     * @notice Mints agricultural collateral NFT.
     * @param to Recipient address (producer/borrower)
     * @param _tokenURI Metadata URI detailing the harvest, crop type, geofence, and audit
     * @param appraisalValue Valuation of the agricultural asset in USDC units (6 decimals)
     * @return tokenId The ID of the newly minted NFT
     */
    function mintCollateral(address to, string memory _tokenURI, uint256 appraisalValue) external returns (uint256) {
        require(to != address(0), "AgroNFT: mint to zero address");
        require(appraisalValue > 0, "AgroNFT: appraisal value must be > 0");

        uint256 tokenId = _nextTokenId++;

        collaterals[tokenId] = CollateralData({
            appraisalValue: appraisalValue,
            ltv: DEFAULT_LTV,
            healthFactor: DEFAULT_HEALTH_FACTOR,
            isCollateralized: false,
            mintedAt: block.timestamp
        });

        emit CollateralMinted(tokenId, to, _tokenURI, appraisalValue, DEFAULT_LTV, DEFAULT_HEALTH_FACTOR);

        _safeMint(to, tokenId);
        _setTokenURI(tokenId, _tokenURI);

        return tokenId;
    }

    /**
     * @notice Updates risk metrics (LTV and Health Factor) based on data layer / oracle feed.
     * @param tokenId The ID of the collateral NFT
     * @param ltv New Loan-To-Value in basis points (e.g. 6000 = 60%)
     * @param healthFactor New Health Factor scaled by 1e4 (e.g. 12500 = 1.25)
     */
    function updateLTVAndHealthFactor(uint256 tokenId, uint256 ltv, uint256 healthFactor)
        external
        onlyAuthorizedUpdater
    {
        require(_ownerOf(tokenId) != address(0), "AgroNFT: token does not exist");
        require(ltv <= MAX_LTV, "AgroNFT: ltv exceeds max allowed");

        collaterals[tokenId].ltv = ltv;
        collaterals[tokenId].healthFactor = healthFactor;

        emit RiskParametersUpdated(tokenId, ltv, healthFactor);
    }

    /**
     * @notice Updates the appraisal value of the crop/harvest.
     */
    function updateAppraisal(uint256 tokenId, uint256 newAppraisalValue) external onlyAuthorizedUpdater {
        require(_ownerOf(tokenId) != address(0), "AgroNFT: token does not exist");
        require(newAppraisalValue > 0, "AgroNFT: invalid appraisal value");

        collaterals[tokenId].appraisalValue = newAppraisalValue;
        emit AppraisalUpdated(tokenId, newAppraisalValue);
    }

    /**
     * @notice Sets collateral status when locked or released by LendingPool.
     */
    function setCollateralStatus(uint256 tokenId, bool status) external onlyLendingPool {
        require(_ownerOf(tokenId) != address(0), "AgroNFT: token does not exist");
        collaterals[tokenId].isCollateralized = status;
        emit CollateralStatusChanged(tokenId, status);
    }

    /**
     * @notice Returns full collateral risk data.
     */
    function getCollateralData(uint256 tokenId) external view returns (CollateralData memory) {
        require(_ownerOf(tokenId) != address(0), "AgroNFT: token does not exist");
        return collaterals[tokenId];
    }

    /**
     * @notice Authorizes or deauthorizes an oracle address.
     */
    function setAuthorizedOracle(address oracle, bool authorized) external onlyOwner {
        require(oracle != address(0), "AgroNFT: invalid oracle address");
        authorizedOracles[oracle] = authorized;
        emit OracleAuthorizationChanged(oracle, authorized);
    }

    /**
     * @notice Authorizes or deauthorizes a LendingPool address.
     */
    function setAuthorizedLendingPool(address pool, bool authorized) external onlyOwner {
        require(pool != address(0), "AgroNFT: invalid pool address");
        authorizedLendingPools[pool] = authorized;
        emit LendingPoolAuthorizationChanged(pool, authorized);
    }
}
