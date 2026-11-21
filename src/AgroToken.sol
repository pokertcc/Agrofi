// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AgroToken ($AGRO)
 * @notice Token ERC-20 nativo de governança, staking e incentivo de liquidez agrícola do AgroFi Protocol.
 * Suporta emissão controlada para a Pool de Recompensa (Reward Pool) e queima deflacionária.
 */
contract AgroToken {
    string public name = "AgroFi Protocol Token";
    string public symbol = "AGRO";
    uint8 public decimals = 18;
    uint256 public totalSupply;

    // Teto máximo de fornecimento (100 Milhões de tokens $AGRO)
    uint256 public constant MAX_SUPPLY = 100_000_000 * 10 ** 18;

    address public owner;

    // Contratos autorizados a emitir recompensas (ex: LendingPool, StakingPool)
    mapping(address => bool) public authorizedMinters;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event MinterUpdated(address indexed minter, bool status);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "AgroToken: caller is not the owner");
        _;
    }

    modifier onlyMinter() {
        require(msg.sender == owner || authorizedMinters[msg.sender], "AgroToken: caller not authorized minter");
        _;
    }

    constructor(address initialOwner) {
        owner = initialOwner != address(0) ? initialOwner : msg.sender;

        // Emissão inicial: 20 Milhões de tokens para reserva de incentivos de safra e liquidez
        _mint(owner, 20_000_000 * 10 ** 18);
    }

    function transfer(address to, uint256 value) external returns (bool) {
        require(to != address(0), "AgroToken: transfer to zero address");
        require(balanceOf[msg.sender] >= value, "AgroToken: insufficient balance");
        balanceOf[msg.sender] -= value;
        balanceOf[to] += value;
        emit Transfer(msg.sender, to, value);
        return true;
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        require(to != address(0), "AgroToken: transfer to zero address");
        require(balanceOf[from] >= value, "AgroToken: insufficient balance");
        require(allowance[from][msg.sender] >= value, "AgroToken: allowance exceeded");
        allowance[from][msg.sender] -= value;
        balanceOf[from] -= value;
        balanceOf[to] += value;
        emit Transfer(from, to, value);
        return true;
    }

    /**
     * @notice Emite recompensas de safra para investidores e produtores que aportam liquidez.
     * Somente o owner ou contratos de pools cadastrados podem invocar esta função.
     */
    function mintRewards(address to, uint256 amount) external onlyMinter returns (bool) {
        require(totalSupply + amount <= MAX_SUPPLY, "AgroToken: max supply reached");
        _mint(to, amount);
        return true;
    }

    /**
     * @notice Queima de tokens para deflação econômica em liquidações ou taxas de originação.
     */
    function burn(uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "AgroToken: insufficient balance to burn");
        balanceOf[msg.sender] -= amount;
        totalSupply -= amount;
        emit Transfer(msg.sender, address(0), amount);
        return true;
    }

    /**
     * @notice Autoriza ou revoga um contrato de pool de recompensa a emitir tokens.
     */
    function setAuthorizedMinter(address minter, bool status) external onlyOwner {
        authorizedMinters[minter] = status;
        emit MinterUpdated(minter, status);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "AgroToken: invalid new owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function _mint(address to, uint256 value) internal {
        totalSupply += value;
        balanceOf[to] += value;
        emit Transfer(address(0), to, value);
    }
}
