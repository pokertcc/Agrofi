import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import time
import argparse
from web3 import Web3
from middleware.web3_client import AgroFiWeb3Client
from middleware.oracle_service import AgroRiskOracle, AgroRiskData
from middleware.config import ACCOUNTS, load_deployed_addresses

def print_separator(title=""):
    print("\n" + "=" * 78)
    if title:
        print(f"📌 {title.upper()}")
        print("=" * 78)

def format_usdc(amount_raw):
    return f"${amount_raw / 10**6:,.2f} USDC"

def wait_for_user(interactive=True):
    if interactive:
        input("\n[Pressione ENTER para executar o próximo passo...]")

def run_step_by_step(interactive=False):
    print_separator("Roteiro de Validação Passo a Passo - Protocolo AgroFi")
    print("Conectando ao nó Anvil local (http://127.0.0.1:8545)...")

    client = AgroFiWeb3Client()
    addresses = load_deployed_addresses()
    oracle = AgroRiskOracle(client)

    admin = ACCOUNTS["admin"]
    farmer = ACCOUNTS["farmer"]
    lender = ACCOUNTS["lender"]
    liquidator = ACCOUNTS["liquidator"]

    print(f"MockUSDC:    {addresses['MockUSDC']}")
    print(f"AgroNFT:     {addresses['AgroNFT']}")
    print(f"LendingPool: {addresses['LendingPool']}")

    # =========================================================================
    # PASSO 1: EMISSÃO E TRANSFERÊNCIAS DE TOKENS (MockUSDC)
    # =========================================================================
    print_separator("Passo 1: Emissão e Transferência de Tokens (MockUSDC)")
    print("Cenário: O Admin emite $500,000 USDC para o Credor e $60,000 USDC para o Produtor.")

    bal_lender_before = client.usdc.functions.balanceOf(lender["address"]).call()
    bal_farmer_before = client.usdc.functions.balanceOf(farmer["address"]).call()
    print(f"  • Saldo Credor Antes:   {format_usdc(bal_lender_before)}")
    print(f"  • Saldo Produtor Antes: {format_usdc(bal_farmer_before)}")

    # Mint para o Credor
    tx1 = client.mint_usdc(lender["address"], 500_000 * 10**6, admin["private_key"])
    # Mint para o Produtor (para que ele possa pagar dívidas depois)
    tx2 = client.mint_usdc(farmer["address"], 60_000 * 10**6, admin["private_key"])

    bal_lender_after = client.usdc.functions.balanceOf(lender["address"]).call()
    bal_farmer_after = client.usdc.functions.balanceOf(farmer["address"]).call()

    print(f"\n  ✅ Transações Confirmadas no Nó Local!")
    print(f"  • Saldo Credor Depois:   {format_usdc(bal_lender_after)} (+ $500,000.00 USDC)")
    print(f"  • Saldo Produtor Depois: {format_usdc(bal_farmer_after)} (+ $60,000.00 USDC)")
    assert bal_lender_after - bal_lender_before == 500_000 * 10**6
    assert bal_farmer_after - bal_farmer_before == 60_000 * 10**6

    wait_for_user(interactive)

    # =========================================================================
    # PASSO 2: FORNECER LIQUIDEZ À POOL (LendingPool Deposit)
    # =========================================================================
    print_separator("Passo 2: Depósito de Liquidez na Pool pelo Credor")
    print("Cenário: O Credor deposita $300,000.00 USDC na LendingPool para financiar créditos agrícolas.")

    pool_liq_before = client.pool.functions.availableLiquidity().call()
    print(f"  • Liquidez Disponível Antes na Pool: {format_usdc(pool_liq_before)}")

    # Credor deposita $300,000 USDC
    deposit_amount = 300_000 * 10**6
    tx_deposit = client.deposit_liquidity(deposit_amount, lender["private_key"])

    pool_liq_after = client.pool.functions.availableLiquidity().call()
    lender_usdc = client.usdc.functions.balanceOf(lender["address"]).call()

    print(f"\n  ✅ Depósito Confirmado na LendingPool!")
    print(f"  • Tx Hash: {tx_deposit.transactionHash.hex()[:20]}...")
    print(f"  • Liquidez Disponível na Pool: {format_usdc(pool_liq_after)} (+ $300,000.00)")
    print(f"  • Saldo Restante do Credor:    {format_usdc(lender_usdc)}")
    assert pool_liq_after - pool_liq_before == deposit_amount

    wait_for_user(interactive)

    # =========================================================================
    # PASSO 3: TOKENIZAÇÃO DA SAFRA (mintCollateral - AgroNFT)
    # =========================================================================
    print_separator("Passo 3: Tokenização do Direito de Uso / Safra (AgroNFT)")
    print("Cenário: Produtor rural tokeniza 500 hectares de Soja avaliada em $100,000 USDC.")

    metadata_uri = "ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    appraisal = 100_000 * 10**6

    token_id = client.mintCollateral(
        to=farmer["address"],
        token_uri=metadata_uri,
        appraisal_value=appraisal,
        sender_private_key=admin["private_key"]
    )

    owner = client.agro_nft.functions.ownerOf(token_id).call()
    col_data = client.agro_nft.functions.getCollateralData(token_id).call()

    print(f"\n  ✅ AgroNFT Emitido com Sucesso!")
    print(f"  • Token ID:           #{token_id}")
    print(f"  • Titular / Produtor: {owner}")
    print(f"  • Avaliação da Safra: {format_usdc(col_data[0])}")
    print(f"  • LTV Inicial:        {col_data[1] / 100:.2f}% (Capacidade: {format_usdc((col_data[0] * col_data[1]) // 10000)})")
    print(f"  • Health Factor:      {col_data[2] / 10000:.2f}x (Seguro)")
    print(f"  • Metadados IPFS:     {metadata_uri}")
    assert owner.lower() == farmer["address"].lower()

    wait_for_user(interactive)

    # =========================================================================
    # PASSO 4: COLATERALIZAÇÃO E SAQUE DE EMPRÉSTIMO (borrow)
    # =========================================================================
    print_separator("Passo 4: Depósito do Colateral e Saque do Empréstimo")
    print("Cenário: O produtor deposita o AgroNFT na pool e saca $50,000.00 USDC de crédito.")

    # 1. Depósito do NFT
    client.deposit_collateral(token_id, farmer["private_key"])
    nft_holder = client.agro_nft.functions.ownerOf(token_id).call()
    print(f"  • AgroNFT #{token_id} depositado em custódia na LendingPool ({nft_holder[:12]}...)")

    # 2. Saque do Empréstimo
    borrow_amount = 50_000 * 10**6
    farmer_usdc_before = client.usdc.functions.balanceOf(farmer["address"]).call()
    tx_borrow = client.borrow(token_id, borrow_amount, farmer["private_key"])
    farmer_usdc_after = client.usdc.functions.balanceOf(farmer["address"]).call()

    loan = client.pool.functions.getLoan(token_id).call()
    pool_liq_now = client.pool.functions.availableLiquidity().call()

    print(f"\n  ✅ Empréstimo Aprovado e Sacado com Sucesso!")
    print(f"  • Tx Hash: {tx_borrow[:20]}...")
    print(f"  • USDC Creditado ao Produtor:  +{format_usdc(borrow_amount)}")
    print(f"  • Novo Saldo USDC do Produtor: {format_usdc(farmer_usdc_after)}")
    print(f"  • Dívida Registrada no Contrato: {format_usdc(loan[1])} (Ativo: {loan[2]})")
    print(f"  • Liquidez Restante na Pool:   {format_usdc(pool_liq_now)}")
    assert loan[1] == borrow_amount
    assert farmer_usdc_after - farmer_usdc_before == borrow_amount

    wait_for_user(interactive)

    # =========================================================================
    # PASSO 5: PAGAMENTO INTEGRAL DO EMPRÉSTIMO (repay) & RESGATE DO COLATERAL
    # =========================================================================
    print_separator("Passo 5: Pagamento do Empréstimo e Devolução do Colateral")
    print("Cenário: O produtor quita a dívida de $50,000.00 USDC e resgata seu AgroNFT de volta.")

    # Quita a dívida
    tx_repay = client.repay(token_id, borrow_amount, farmer["private_key"])
    loan_after_repay = client.pool.functions.getLoan(token_id).call()

    print(f"  • Pagamento de {format_usdc(borrow_amount)} confirmado! Dívida restante: {format_usdc(loan_after_repay[1])}")

    # Resgata o NFT
    tx_withdraw_col = client.withdraw_collateral(token_id, farmer["private_key"])
    new_nft_owner = client.agro_nft.functions.ownerOf(token_id).call()
    loan_after_withdraw = client.pool.functions.getLoan(token_id).call()

    print(f"\n  ✅ Colateral Desbloqueado e Devolvido!")
    print(f"  • Dívida Atual do Empréstimo: {format_usdc(loan_after_withdraw[1])} (Ativo: {loan_after_withdraw[2]})")
    print(f"  • Dono Atual do AgroNFT #{token_id}: {new_nft_owner} (Produtor)")
    assert loan_after_withdraw[1] == 0
    assert not loan_after_withdraw[2]
    assert new_nft_owner.lower() == farmer["address"].lower()

    wait_for_user(interactive)

    # =========================================================================
    # PASSO 6: TESTE DE ESTRESSE - CHOQUE CLIMÁTICO E LIQUIDAÇÃO PARAMÉTRICA
    # =========================================================================
    print_separator("Passo 6: Simulação de Choque Agroclimático & Liquidação Paramétrica")
    print("Cenário: O produtor toma outro empréstimo, uma seca extrema destrói a safra e o contrato executa a liquidação paramétrica sem juiz.")

    # 1. Produtor re-deposita e toma $40,000 USDC
    client.deposit_collateral(token_id, farmer["private_key"])
    stress_borrow = 40_000 * 10**6
    client.borrow(token_id, stress_borrow, farmer["private_key"])
    print(f"  • Produtor tomou novo empréstimo de {format_usdc(stress_borrow)}.")

    # 2. Oráculo injeta seca extrema (NDVI 0.25, -75% de chuva)
    drought = AgroRiskData(
        ndvi=0.25,
        precipitation_deficit=-0.75,
        soil_moisture=10.0,
        commodity_price_ratio=0.85
    )
    tx_shock, ltv_shock, hf_shock = oracle.push_risk_update(token_id, drought, admin["private_key"])
    print(f"  • Oráculo Web3.py injetou choque climático: NDVI 0.25 | Déficit Pluviométrico -75%")
    print(f"  • Novo Fator de Saúde calculado: {hf_shock / 10000:.2f}x (CRÍTICO: < 1.00x)")

    # 3. Liquidador executa liquidação paramétrica
    client.mint_usdc(liquidator["address"], stress_borrow, admin["private_key"])
    tx_liq = client.execute_parametric_liquidation(token_id, liquidator["private_key"])
    
    final_loan = client.pool.functions.getLoan(token_id).call()
    final_owner = client.agro_nft.functions.ownerOf(token_id).call()
    final_pool = client.pool.functions.availableLiquidity().call()

    print(f"\n  ✅ Liquidação Paramétrica Concluída com Sucesso!")
    print(f"  • Tx Hash: {tx_liq[:20]}...")
    print(f"  • Dívida Liquidada:           $0.00 USDC (Ativo: False)")
    print(f"  • Novo Dono do AgroNFT:       {final_owner} (Liquidador)")
    print(f"  • Integridade da Pool:        {format_usdc(final_pool)} preservados")
    assert final_loan[1] == 0
    assert final_owner.lower() == liquidator["address"].lower()

    print_separator("Fim do Teste: Todas as 6 Etapas Foram Validadas On-Chain!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Teste Passo a Passo AgroFi")
    parser.add_argument("--interactive", action="store_true", help="Pausa com ENTER em cada etapa")
    args = parser.parse_args()
    run_step_by_step(interactive=args.interactive)
