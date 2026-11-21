// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/MockUSDC.sol";
import "../src/AgroNFT.sol";
import "../src/LendingPool.sol";

contract DeployAgroFi is Script {
    function run() external returns (address usdcAddr, address nftAddr, address poolAddr) {
        // Default private key for Anvil Account #0
        uint256 deployerPrivateKey = vm.envOr(
            "PRIVATE_KEY",
            uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80)
        );

        address deployer = vm.addr(deployerPrivateKey);

        vm.startBroadcast(deployerPrivateKey);

        // 1. Deploy MockUSDC
        MockUSDC usdc = new MockUSDC();
        usdcAddr = address(usdc);

        // 2. Deploy AgroNFT
        AgroNFT agroNFT = new AgroNFT();
        nftAddr = address(agroNFT);

        // 3. Deploy LendingPool
        LendingPool pool = new LendingPool(usdcAddr, nftAddr);
        poolAddr = address(pool);

        // 4. Authorize LendingPool and deployer on AgroNFT
        agroNFT.setAuthorizedLendingPool(poolAddr, true);
        agroNFT.setAuthorizedOracle(deployer, true);

        // 5. Authorize deployer as Oracle on LendingPool
        pool.setAuthorizedOracle(deployer, true);

        // 6. Provide initial pool liquidity (200,000 USDC)
        usdc.approve(poolAddr, 200_000 * 1e6);
        pool.depositLiquidity(200_000 * 1e6);

        vm.stopBroadcast();

        console.log("=== AgroFi Protocol Deployed Successfully ===");
        console.log("Deployer / Oracle:", deployer);
        console.log("MockUSDC deployed to:", usdcAddr);
        console.log("AgroNFT deployed to:", nftAddr);
        console.log("LendingPool deployed to:", poolAddr);
        console.log("Initial Pool Liquidity: 200,000 USDC");
    }
}
