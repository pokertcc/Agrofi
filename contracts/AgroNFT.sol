// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AgroNFT
 * @notice Título ERC-721 representativo de colateral agropecuário com LTV e Health Factor dinâmicos.
 */
interface IERC721Receiver {
    function onERC721Received(address operator, address from, uint256 tokenId, bytes calldata data) external returns (bytes4);
}

contract AgroNFT {
    string public name = "AgroFi Crop Collateral NFT";
    string public symbol = "AGRONFT";

    address public owner;
    uint256 public nextTokenId = 1;

    uint256 public constant DEFAULT_LTV = 6000;            // 60.00%
    uint256 public constant MAX_LTV = 7500;                // 75.00%
    uint256 public constant DEFAULT_HEALTH_FACTOR = 15000; // 1.50x

    struct Collateral {
        uint256 appraisalValue; // Avaliação em micro-USDC (6 decimais)
        uint256 ltv;            // LTV em Basis Points (ex: 6000 = 60%)
        uint256 healthFactor;   // Health Factor escalado por 10.000 (ex: 15000 = 1.50x)
        bool isDeposited;       // Se está travado no LendingPool
    }

    mapping(uint256 => address) public ownerOf;
    mapping(address => uint256) public balanceOf;
    mapping(uint256 => address) public getApproved;
    mapping(address => mapping(address => bool)) public isApprovedForAll;
    mapping(uint256 => string) public tokenURI;
    mapping(uint256 => Collateral) public collaterals;

    mapping(address => bool) public authorizedOracles;
    mapping(address => bool) public authorizedLendingPools;

    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    event Approval(address indexed owner, address indexed approved, uint256 indexed tokenId);
    event ApprovalForAll(address indexed owner, address indexed operator, bool approved);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    event CollateralMinted(uint256 indexed tokenId, address indexed to, uint256 appraisalValue, string tokenURI);
    event RiskUpdated(uint256 indexed tokenId, uint256 ltv, uint256 healthFactor);
    event AppraisalUpdated(uint256 indexed tokenId, uint256 newAppraisalValue);

    modifier onlyOwner() {
        require(msg.sender == owner, "AgroNFT: unauthorized");
        _;
    }

    modifier onlyOracle() {
        require(msg.sender == owner || authorizedOracles[msg.sender], "AgroNFT: not authorized oracle");
        _;
    }

    modifier onlyLendingPool() {
        require(authorizedLendingPools[msg.sender], "AgroNFT: not authorized lending pool");
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedOracles[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    function setAuthorizedOracle(address oracle, bool auth) external onlyOwner {
        authorizedOracles[oracle] = auth;
    }

    function setAuthorizedLendingPool(address pool, bool auth) external onlyOwner {
        authorizedLendingPools[pool] = auth;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "AgroNFT: zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function renounceOwnership() external onlyOwner {
        emit OwnershipTransferred(owner, address(0));
        owner = address(0);
    }

    function mintCollateral(address to, string calldata uri, uint256 appraisalValue) external returns (uint256) {
        require(to != address(0), "AgroNFT: mint to zero address");
        require(appraisalValue > 0, "AgroNFT: appraisal must be > 0");

        uint256 tokenId = nextTokenId++;
        ownerOf[tokenId] = to;
        balanceOf[to] += 1;
        tokenURI[tokenId] = uri;

        collaterals[tokenId] = Collateral({
            appraisalValue: appraisalValue,
            ltv: DEFAULT_LTV,
            healthFactor: DEFAULT_HEALTH_FACTOR,
            isDeposited: false
        });

        emit Transfer(address(0), to, tokenId);
        emit CollateralMinted(tokenId, to, appraisalValue, uri);
        return tokenId;
    }

    function updateLTVAndHealthFactor(uint256 tokenId, uint256 ltv, uint256 healthFactor) external onlyOracle {
        require(ownerOf[tokenId] != address(0), "AgroNFT: nonexistent token");
        require(ltv <= MAX_LTV, "AgroNFT: LTV exceeds max");

        Collateral storage col = collaterals[tokenId];
        col.ltv = ltv;
        col.healthFactor = healthFactor;

        emit RiskUpdated(tokenId, ltv, healthFactor);
    }

    function updateAppraisal(uint256 tokenId, uint256 newAppraisalValue) external onlyOracle {
        require(ownerOf[tokenId] != address(0), "AgroNFT: nonexistent token");
        collaterals[tokenId].appraisalValue = newAppraisalValue;
        emit AppraisalUpdated(tokenId, newAppraisalValue);
    }

    function setCollateralStatus(uint256 tokenId, bool isDeposited) external onlyLendingPool {
        require(ownerOf[tokenId] != address(0), "AgroNFT: nonexistent token");
        collaterals[tokenId].isDeposited = isDeposited;
    }

    function getCollateralData(uint256 tokenId) external view returns (uint256 appraisalValue, uint256 ltv, uint256 healthFactor, bool isDeposited) {
        require(ownerOf[tokenId] != address(0), "AgroNFT: nonexistent token");
        Collateral memory c = collaterals[tokenId];
        return (c.appraisalValue, c.ltv, c.healthFactor, c.isDeposited);
    }

    function approve(address to, uint256 tokenId) external {
        address tokenOwner = ownerOf[tokenId];
        require(msg.sender == tokenOwner || isApprovedForAll[tokenOwner][msg.sender], "AgroNFT: not authorized");
        getApproved[tokenId] = to;
        emit Approval(tokenOwner, to, tokenId);
    }

    function setApprovalForAll(address operator, bool approved) external {
        isApprovedForAll[msg.sender][operator] = approved;
        emit ApprovalForAll(msg.sender, operator, approved);
    }

    function transferFrom(address from, address to, uint256 tokenId) public {
        require(ownerOf[tokenId] == from, "AgroNFT: transfer from incorrect owner");
        require(to != address(0), "AgroNFT: transfer to zero address");
        require(
            msg.sender == from || getApproved[tokenId] == msg.sender || isApprovedForAll[from][msg.sender],
            "AgroNFT: transfer caller is not owner nor approved"
        );

        delete getApproved[tokenId];
        balanceOf[from] -= 1;
        balanceOf[to] += 1;
        ownerOf[tokenId] = to;

        emit Transfer(from, to, tokenId);
    }

    function safeTransferFrom(address from, address to, uint256 tokenId) external {
        safeTransferFrom(from, to, tokenId, "");
    }

    function safeTransferFrom(address from, address to, uint256 tokenId, bytes memory data) public {
        transferFrom(from, to, tokenId);
        if (to.code.length > 0) {
            try IERC721Receiver(to).onERC721Received(msg.sender, from, tokenId, data) returns (bytes4 retval) {
                require(retval == IERC721Receiver.onERC721Received.selector, "AgroNFT: invalid receiver");
            } catch {
                // Compatible fallback
            }
        }
    }

    function supportsInterface(bytes4 interfaceId) external pure returns (bool) {
        return interfaceId == 0x80ac58cd || interfaceId == 0x5b5e139f || interfaceId == 0x01ffc9a7;
    }
}
