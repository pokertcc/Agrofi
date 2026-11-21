// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/MockUSDC.sol";
import "../src/AgroNFT.sol";
import "../src/LendingPool.sol";

contract DeploySepoliaAgroFi is Script {
    function run() external returns (address usdcAddr, address nftAddr, address poolAddr) {
        // Reads PRIVATE_KEY from environment or command line
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("==================================================");
        console.log("Deploying AgroFi to Ethereum Sepolia Testnet");
        console.log("Deployer Address:", deployer);
        console.log("Balance:", deployer.balance);
        console.log("==================================================");

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

        // 4. Authorize LendingPool and Deployer on AgroNFT
        agroNFT.setAuthorizedLendingPool(poolAddr, true);
        agroNFT.setAuthorizedOracle(deployer, true);

        // 5. Authorize Deployer as Oracle on LendingPool
        pool.setAuthorizedOracle(deployer, true);

        // 6. Fund LendingPool with initial 200,000 USDC
        usdc.approve(poolAddr, 200_000 * 1e6);
        pool.depositLiquidity(200_000 * 1e6);

        vm.stopBroadcast();

        console.log("\n==================================================");
        console.log("SUCCESS! AgroFi Deployed on Sepolia Testnet");
        console.log("==================================================");
        console.log("MockUSDC:    https://sepolia.etherscan.io/address/", usdcAddr);
        console.log("AgroNFT:     https://sepolia.etherscan.io/address/", nftAddr);
        console.log("LendingPool: https://sepolia.etherscan.io/address/", poolAddr);
    }
}
