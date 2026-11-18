// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AgroLandNFT
 * @notice Título ERC-721 representativo de colaterais de imóveis rurais (RWA) no AgroFi.
 */
contract AgroLandNFT {
    string public name = "AgroFi Rural Land Title NFT";
    string public symbol = "AGROLAND";

    struct LandMetadata {
        string landId;
        string carCode;
        string municipality;
        string state;
        uint256 totalAreaHa;
        uint256 productiveAreaHa;
    }

    uint256 public nextTokenId = 1;
    address public owner;

    mapping(uint256 => address) public ownerOf;
    mapping(uint256 => address) public getApproved;
    mapping(address => mapping(address => bool)) public isApprovedForAll;
    mapping(uint256 => LandMetadata) public landMetadata;

    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    event Approval(address indexed owner, address indexed approved, uint256 indexed tokenId);
    event ApprovalForAll(address indexed owner, address indexed operator, bool approved);
    event LandMinted(uint256 indexed tokenId, string landId, string carCode, address indexed to);

    modifier onlyOwner() {
        require(msg.sender == owner, "AgroLandNFT: unauthorized");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function mint(
        address to,
        string calldata landId,
        string calldata carCode,
        string calldata municipality,
        string calldata state,
        uint256 totalAreaHa,
        uint256 productiveAreaHa
    ) external returns (uint256) {
        uint256 tokenId = nextTokenId++;
        ownerOf[tokenId] = to;

        landMetadata[tokenId] = LandMetadata({
            landId: landId,
            carCode: carCode,
            municipality: municipality,
            state: state,
            totalAreaHa: totalAreaHa,
            productiveAreaHa: productiveAreaHa
        });

        emit Transfer(address(0), to, tokenId);
        emit LandMinted(tokenId, landId, carCode, to);
        return tokenId;
    }

    function approve(address to, uint256 tokenId) external {
        address tokenOwner = ownerOf[tokenId];
        require(msg.sender == tokenOwner || isApprovedForAll[tokenOwner][msg.sender], "Not authorized");
        getApproved[tokenId] = to;
        emit Approval(tokenOwner, to, tokenId);
    }

    function setApprovalForAll(address operator, bool approved) external {
        isApprovedForAll[msg.sender][operator] = approved;
        emit ApprovalForAll(msg.sender, operator, approved);
    }

    function transferFrom(address from, address to, uint256 tokenId) public {
        require(ownerOf[tokenId] == from, "Wrong owner");
        require(to != address(0), "Invalid recipient");
        require(
            msg.sender == from || getApproved[tokenId] == msg.sender || isApprovedForAll[from][msg.sender],
            "Not authorized"
        );

        delete getApproved[tokenId];
        ownerOf[tokenId] = to;
        emit Transfer(from, to, tokenId);
    }

    function safeTransferFrom(address from, address to, uint256 tokenId) external {
        transferFrom(from, to, tokenId);
    }
}
