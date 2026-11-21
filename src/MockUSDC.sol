// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title MockUSDC
 * @dev Mock ERC-20 token simulating USD Coin with 6 decimals.
 * Used for testing liquidity pools and credit execution in AgroFi.
 */
contract MockUSDC is ERC20, Ownable {
    uint8 private constant _DECIMALS = 6;

    event TokensMinted(address indexed to, uint256 amount);
    event TokensBurned(address indexed from, uint256 amount);

    constructor() ERC20("USD Coin (AgroFi Mock)", "MockUSDC") Ownable(msg.sender) {
        // Mint initial supply of 1,000,000 USDC to deployer
        _mint(msg.sender, 1_000_000 * 10 ** _DECIMALS);
    }

    /**
     * @dev Overrides decimals to match standard USDC (6 decimals).
     */
    function decimals() public pure override returns (uint8) {
        return _DECIMALS;
    }

    /**
     * @notice Allows any user or authorized system to mint test tokens.
     * @param to Recipient address
     * @param amount Token amount in micro-USDC (1 USDC = 1_000_000 units)
     */
    function mint(address to, uint256 amount) external {
        require(to != address(0), "MockUSDC: mint to zero address");
        _mint(to, amount);
        emit TokensMinted(to, amount);
    }

    /**
     * @notice Allows burning tokens from an address.
     * @param from Address to burn tokens from
     * @param amount Token amount to burn
     */
    function burn(address from, uint256 amount) external {
        if (msg.sender != from) {
            _spendAllowance(from, msg.sender, amount);
        }
        _burn(from, amount);
        emit TokensBurned(from, amount);
    }
}
