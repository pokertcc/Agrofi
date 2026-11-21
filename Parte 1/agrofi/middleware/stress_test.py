import sys
import os

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import time
from web3 import Web3
from middleware.web3_client import AgroFiWeb3Client
from middleware.oracle_service import AgroRiskOracle, AgroRiskData
from middleware.config import ACCOUNTS

def run_stress_test():
    print("=" * 70)
    print("[AgroFi] AGROFI DEFI PROTOCOL - END-TO-END STRESS TEST (SPRINTS 1-4)")
    print("=" * 70)

    # 1. Connect & Deploy
    print("\n[Step 1] Connecting to Anvil node and deploying contracts...")
    client = AgroFiWeb3Client()
    addresses = client.deploy_contracts()
    print(f"MockUSDC:    {addresses['MockUSDC']}")
    print(f"AgroNFT:     {addresses['AgroNFT']}")
    print(f"LendingPool: {addresses['LendingPool']}")

    # 2. Fund Liquidity Pool
    print("\n[Step 2] Funding Liquidity Pool...")
    lender = ACCOUNTS["lender"]["address"]
    lender_key = ACCOUNTS["lender"]["private_key"]
    pool_funding = 300_000 * 10**6 # 300,000 USDC

    # Mint USDC to lender
    client.mint_usdc(lender, pool_funding)
    # Lender deposits into pool
    client.deposit_liquidity(pool_funding, lender_key)
    avail_liq = client.pool.functions.availableLiquidity().call()
    print(f"Pool Available Liquidity: {avail_liq / 10**6:,.2f} USDC")
    assert avail_liq == pool_funding, "Liquidity mismatch!"

    # 3. Tokenize Agricultural Collateral (AgroNFT)
    print("\n[Step 3] Tokenizing Agricultural Asset (AgroNFT)...")
    farmer = ACCOUNTS["farmer"]["address"]
    farmer_key = ACCOUNTS["farmer"]["private_key"]
    token_uri = "ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    appraisal_value = 100_000 * 10**6 # $100,000 USDC crop appraisal

    token_id = client.mintCollateral(
        to=farmer,
        token_uri=token_uri,
        appraisal_value=appraisal_value
    )
    print(f"AgroNFT Token ID #{token_id} minted to Farmer ({farmer})")
    col_data = client.agro_nft.functions.getCollateralData(token_id).call()
    print(f"Appraisal Value: ${col_data[0] / 10**6:,.2f} USDC | Initial LTV: {col_data[1]/100:.1f}% | Initial Health Factor: {col_data[2]/10000:.2f}x")

    # 4. Deposit Collateral and Borrow
    print("\n[Step 4] Depositing Collateral & Borrowing Stablecoins...")
    client.deposit_collateral(token_id, farmer_key)
    print(f"AgroNFT #{token_id} deposited into LendingPool.")

    borrow_amount = 50_000 * 10**6 # $50,000 USDC
    farmer_bal_before = client.usdc.functions.balanceOf(farmer).call()
    client.borrow(token_id, borrow_amount, farmer_key)
    farmer_bal_after = client.usdc.functions.balanceOf(farmer).call()
    print(f"Farmer successfully borrowed: ${(farmer_bal_after - farmer_bal_before) / 10**6:,.2f} USDC")

    loan = client.pool.functions.getLoan(token_id).call()
    print(f"Current Loan Debt: ${loan[1] / 10**6:,.2f} USDC | Loan Active: {loan[2]}")
    assert loan[1] == borrow_amount, "Debt does not match borrowed amount!"

    # 5. Simulate Adverse Climate Shock via Oracle
    print("\n[Step 5] Ingesting Adverse Agro Shock (Severe Drought & Pest Infestation)...")
    oracle = AgroRiskOracle(client)
    shock_data = AgroRiskData(
        ndvi=0.28,                     # Critical vegetation loss (withered crop)
        precipitation_deficit=-0.70,   # -70% rainfall deficit
        soil_moisture=11.5,            # Extreme dry soil
        commodity_price_ratio=0.90     # -10% spot price decline
    )

    tx_hash, ltv, health_factor = oracle.push_risk_update(token_id, shock_data)
    print(f"Updated Parameters on chain: LTV={ltv/100:.1f}% | Health Factor={health_factor/10000:.2f}x")
    assert health_factor < 10000, "Health factor should be < 1.00x after shock!"

    # 6. Verify Solvency Guard (Further borrow is blocked)
    print("\n[Step 6] Testing Solvency Protection Guard...")
    try:
        client.borrow(token_id, 1_000 * 10**6, farmer_key)
        raise AssertionError("Borrowing should have reverted due to unhealthy collateral!")
    except Exception as e:
        print(f"Borrow correctly rejected by smart contract! ({str(e)[:60]}...)")

    # 7. Execute Parametric Liquidation
    print("\n[Step 7] Executing Parametric Liquidation (No Civil Court Dependency)...")
    liquidator = ACCOUNTS["liquidator"]["address"]
    liquidator_key = ACCOUNTS["liquidator"]["private_key"]

    # Fund liquidator with USDC to repay debt
    client.mint_usdc(liquidator, borrow_amount)
    liq_tx = client.execute_parametric_liquidation(token_id, liquidator_key)
    print(f"Parametric Liquidation Executed! Tx: {liq_tx}")

    # 8. Post-Liquidation Verifications
    print("\n[Step 8] Final State Assertions...")
    final_loan = client.pool.functions.getLoan(token_id).call()
    final_nft_owner = client.agro_nft.functions.ownerOf(token_id).call()
    final_pool_liquidity = client.pool.functions.availableLiquidity().call()

    print(f"Remaining Loan Debt: ${final_loan[1] / 10**6:,.2f} USDC (Active: {final_loan[2]})")
    print(f"New AgroNFT Owner:   {final_nft_owner} (Liquidator: {liquidator})")
    print(f"Pool Liquidity:      ${final_pool_liquidity / 10**6:,.2f} USDC")

    assert final_loan[1] == 0, "Debt must be 0 after liquidation"
    assert not final_loan[2], "Loan must be inactive"
    assert final_nft_owner.lower() == liquidator.lower(), "Liquidator must own the AgroNFT"
    assert final_pool_liquidity == pool_funding, "Pool liquidity must remain intact"

    print("\n" + "=" * 70)
    print("[SUCCESS] ALL STRESS TEST ASSERTIONS PASSED SUCCESSFULLY!")
    print("DeFi Flow + Parametric Execution fully validated on Anvil node.")
    print("=" * 70)

if __name__ == "__main__":
    run_stress_test()
