"""
AgroFi - Integracao Web3 & Oraculo de Risco (Modo Local Anvil & Ethereum Sepolia)
Conecta a Camada de Satelite/Dados de Machine Learning (Parte 1) aos Smart Contracts (Parte 2).
"""
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pathlib import Path

# Garante que o diretório atual venha primeiro no sys.path
base_dir = Path(__file__).resolve().parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

# Adiciona o diretório da Parte 1 para permitir importar src.api.service
for p in [base_dir / "Parte 1" / "agrofi", base_dir.parent / "AgroFi"]:
    if p.exists() and (p / "src" / "api" / "service.py").exists():
        if str(p) not in sys.path:
            sys.path.append(str(p))
        break

from middleware.web3_client import AgroFiWeb3Client
from middleware.oracle_service import AgroRiskOracle, AgroRiskData
from middleware.config import ACCOUNTS

print("=" * 70)
print("  AgroFi - Integracao Fim a Fim (Parte 1: Agro/ML -> Parte 2: Web3/DeFi)")
print("=" * 70)

# Conecta a rede ativa (detecta automaticamente Anvil local ou Sepolia)
try:
    client = AgroFiWeb3Client()
except Exception as e:
    print(f"[ERRO DE CONEXAO] {e}")
    sys.exit(1)

is_local = client.chain_id == 31337 or "127.0.0.1" in str(client.w3.provider)
net_name = "Anvil Local (31337)" if is_local else f"Ethereum Sepolia Testnet ({client.chain_id})"

print(f"• Rede Conectada:       {net_name}")
print(f"• Bloco Atual:          {client.w3.eth.block_number}")
print(f"• Contrato LendingPool: {client.addresses.get('LendingPool', 'Nao configurado')}")
print(f"• Contrato AgroNFT:     {client.addresses.get('AgroNFT', 'Nao configurado')}")
print("-" * 70)

# 1. Ingestao de Dados da Parte 1 (Camada Geoespacial e Machine Learning)
land_id = "TALHAO-MT-001"
simulated_drought = -35.0  # Choque de seca de -35%

print(f"[Parte 1] Processando telemetria geoespacial para o talhao '{land_id}'...")
try:
    from src.api.service import orchestrator
    eval_res = orchestrator.evaluate_land_full(land_id, simulated_drought_pct=simulated_drought)
    ndvi_metrics = eval_res["vegetation_ndvi"]
    val_result = eval_res["valuation"]
    risk_result = eval_res["risk_assessment"]
    
    ndvi_observed = ndvi_metrics["ndvi_mean"]
    precip_deficit = simulated_drought / 100.0
    soil_moisture = 22.0
    commodity_ratio = 0.98
    appraisal_usdc = int(min(val_result["predicted_value"] / 1000.0, 500_000.0)) * 10**6  # Escala USDC
    
    print(f"  ✓ Dados carregados do pipeline SICAR/Sentinel-2/Stacking Ensemble:")
    print(f"    - NDVI Médio Observado: {ndvi_observed:.3f} (Pico: {ndvi_metrics['ndvi_peak']:.3f})")
    print(f"    - Estresse Hídrico:     {risk_result['climate_stress_index']*100:.1f}%")
    print(f"    - Valor Patrimonial:    R$ {val_result['predicted_value']:,.2f}")
    print(f"    - LTV Dinâmico ML:      {risk_result['dynamic_ltv']*100:.2f}%")
except Exception as e:
    print(f"  [Aviso] Nao foi possivel carregar diretamente de src.api.service ({e}). Usando telemetria representativa.")
    ndvi_observed = 0.28
    precip_deficit = -0.70
    soil_moisture = 18.0
    commodity_ratio = 0.95
    appraisal_usdc = 100_000 * 10**6

dados = AgroRiskData(
    ndvi=ndvi_observed,
    precipitation_deficit=precip_deficit,
    soil_moisture=soil_moisture,
    commodity_price_ratio=commodity_ratio
)

# 2. Inicializacao do Oraculo e Avaliacao
oracle = AgroRiskOracle(client)
debt_usdc = int(appraisal_usdc * 0.50)  # 50% de alavancagem
calc_ltv, calc_hf = oracle.evaluate_risk(dados, appraisal_usdc, debt_usdc)

print("-" * 70)
print("[Parte 2] Parametros de Risco Calculados pelo Oraculo:")
print(f"  • NDVI de Entrada:      {dados.ndvi:.2f}")
print(f"  • Deficit de Chuva:     {dados.precipitation_deficit * 100:.1f}%")
print(f"  • LTV Dinamico:         {calc_ltv / 100:.2f}%")
print(f"  • Fator de Saude (HF):  {calc_hf / 10000:.2f}x ({'Risco de Liquidacao!' if calc_hf < 10000 else 'Seguro/Solvente'})")
print("-" * 70)

# 3. Transmissao On-Chain
token_id = 1
try:
    print(f"Transmitindo atualizacao para o contrato na rede {net_name} (Token ID #{token_id})...")
    tx_hash, ltv, hf = oracle.push_risk_update(token_id=token_id, risk_data=dados)
    print(f"\n✓ Transacao gravada on-chain com sucesso!")
    if not is_local:
        print(f"  Link no Etherscan: https://sepolia.etherscan.io/tx/{tx_hash}")
    else:
        print(f"  Tx Hash Local: {tx_hash}")
except Exception as e:
    err_str = str(e)
    if "token does not exist" in err_str.lower() or "owner query for nonexistent token" in err_str.lower():
        print(f"\n[Nota On-Chain] O Token ID #{token_id} ainda nao foi emitido (minted).")
        print("  O calculo matematico foi 100% validado pelo Oraculo!")
        if is_local:
            print("  Para emitir localmente e testar o ciclo completo, execute: python -m middleware.stress_test")
        else:
            print("  Para emitir na Sepolia, utilize client.mintCollateral(...) com a chave privada autorizada.")
    else:
        print(f"\n[Aviso ao transmitir transacao]: {err_str}")

print("=" * 70)
