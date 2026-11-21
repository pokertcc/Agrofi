import sys
import os
import json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from web3 import Web3
from eth_account import Account

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
OUT_DIR = BASE_DIR / "out"
SEPOLIA_DEPLOY_FILE = BASE_DIR / "sepolia_deployed_addresses.json"
SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
SEPOLIA_CHAIN_ID = 11155111

USDC_ADDRESS = "0x178B9bFA3E86a9Ed3F67963e28afBe49BCf45ED2"
AGRO_ADDRESS = "0xBBa1B54b0b6962F586a9971965811b79b1CdAeB8"
APY_BPS = 2200 # 22% APY

def load_private_key() -> str:
    key = os.getenv("SEPOLIA_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
    if key:
        return key.strip()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("SEPOLIA_PRIVATE_KEY=") or line.startswith("PRIVATE_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and val != "0x...":
                    return val
    raise ValueError("Chave privada não encontrada no .env")

def main():
    print("=" * 70)
    print("🌾 DEPLOY DO CONTRATO AGROSTAKINGREWARDS NA REDE ETHEREUM SEPOLIA")
    print("=" * 70)

    pk = load_private_key()
    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
    if not w3.is_connected():
        print(f"❌ Erro ao conectar ao RPC Sepolia: {SEPOLIA_RPC_URL}")
        return

    admin_acc = Account.from_key(pk)
    deployer = admin_acc.address
    balance_wei = w3.eth.get_balance(deployer)
    balance_eth = w3.from_wei(balance_wei, "ether")

    print(f"  • Deployer / Admin:  {deployer}")
    print(f"  • Saldo Sepolia ETH: {balance_eth:.5f} ETH")
    print(f"  • MockUSDC (Stake):  {USDC_ADDRESS}")
    print(f"  • AgroToken (Reward):{AGRO_ADDRESS}")
    print(f"  • APY Configurado:   22.0% ({APY_BPS} bps)")
    print("-" * 70)

    # 1. Carregar artefato compilado
    artifact_path = OUT_DIR / "AgroStakingRewards.sol" / "AgroStakingRewards.json"
    if not artifact_path.exists():
        print(f"❌ Artefato não encontrado em {artifact_path}. Execute 'forge build' primeiro.")
        return

    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)

    bytecode = artifact["bytecode"]["object"]
    abi = artifact["abi"]

    # 2. Deploy do AgroStakingRewards
    print("⏳ [1/2] Enviando transação de deploy do AgroStakingRewards...")
    factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(deployer, "pending")
    gas_price = int(w3.eth.gas_price * 1.2)

    gas_estimate = factory.constructor(
        Web3.to_checksum_address(USDC_ADDRESS),
        Web3.to_checksum_address(AGRO_ADDRESS),
        APY_BPS
    ).estimate_gas({"from": deployer})

    tx = factory.constructor(
        Web3.to_checksum_address(USDC_ADDRESS),
        Web3.to_checksum_address(AGRO_ADDRESS),
        APY_BPS
    ).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gas": int(gas_estimate * 1.25),
        "gasPrice": gas_price,
        "chainId": SEPOLIA_CHAIN_ID
    })

    signed = w3.eth.account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  • Tx Deploy: https://sepolia.etherscan.io/tx/{tx_hash.hex()}")
    print("  • Aguardando confirmação no bloco Sepolia...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    if receipt.status != 1:
        print("❌ Deploy falhou!")
        return

    staking_addr = receipt.contractAddress
    print(f"  ✅ AgroStakingRewards implantado em: {staking_addr}")

    # 3. Autorizar o contrato de Staking como minter no AgroToken
    print("\n⏳ [2/2] Autorizando AgroStakingRewards como minter no AgroToken ($AGRO)...")
    agro_artifact_path = OUT_DIR / "AgroToken.sol" / "AgroToken.json"
    with open(agro_artifact_path, "r", encoding="utf-8") as f:
        agro_artifact = json.load(f)

    agro_contract = w3.eth.contract(address=Web3.to_checksum_address(AGRO_ADDRESS), abi=agro_artifact["abi"])
    nonce = w3.eth.get_transaction_count(deployer, "pending")

    auth_tx = agro_contract.functions.setAuthorizedMinter(
        Web3.to_checksum_address(staking_addr),
        True
    ).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gas": 100000,
        "gasPrice": gas_price,
        "chainId": SEPOLIA_CHAIN_ID
    })

    auth_signed = w3.eth.account.sign_transaction(auth_tx, pk)
    auth_tx_hash = w3.eth.send_raw_transaction(auth_signed.raw_transaction)
    print(f"  • Tx Autorização Minter: https://sepolia.etherscan.io/tx/{auth_tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(auth_tx_hash, timeout=120)
    print("  ✅ Minter autorizado com sucesso no contrato $AGRO!")

    # 4. Salvar em sepolia_deployed_addresses.json
    try:
        data = {}
        if SEPOLIA_DEPLOY_FILE.exists():
            with open(SEPOLIA_DEPLOY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["AgroStakingRewards"] = staking_addr
        if "etherscan" not in data:
            data["etherscan"] = {}
        data["etherscan"]["AgroStakingRewards"] = f"https://sepolia.etherscan.io/address/{staking_addr}"
        with open(SEPOLIA_DEPLOY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"\n📁 Salvo com sucesso em: {SEPOLIA_DEPLOY_FILE.name}")
    except Exception as e:
        print(f"Aviso ao salvar json: {e}")

    print("\n" + "=" * 70)
    print("🎉 DEPLOY & CONFIGURAÇÃO CONCLUÍDOS COM SUCESSO!")
    print(f"  • Contrato Staking: {staking_addr}")
    print(f"  • Etherscan:        https://sepolia.etherscan.io/address/{staking_addr}")
    print("=" * 70)

if __name__ == "__main__":
    main()
