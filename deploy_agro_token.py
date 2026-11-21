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
    raise ValueError("Chave privada não encontrada no arquivo .env nem nas variáveis de ambiente.")

def main():
    print("=" * 70)
    print("🌾 DEPLOY AUTOMÁTICO DO TOKEN $AGRO NA REDE ETHEREUM SEPOLIA")
    print("=" * 70)

    try:
        pk = load_private_key()
    except Exception as e:
        print(f"❌ Erro ao ler a chave privada: {e}")
        return

    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
    if not w3.is_connected():
        print(f"❌ Não foi possível conectar ao nó Sepolia: {SEPOLIA_RPC_URL}")
        return

    account = Account.from_key(pk)
    deployer = account.address
    balance_wei = w3.eth.get_balance(deployer)
    balance_eth = w3.from_wei(balance_wei, "ether")

    print(f"  • Carteira Deployer: {deployer}")
    print(f"  • Saldo Sepolia ETH: {balance_eth:.5f} ETH")
    print(f"  • Rede:              Sepolia (Chain ID: {SEPOLIA_CHAIN_ID})")
    print("-" * 70)

    if balance_eth < 0.005:
        print("❌ Saldo insuficiente de Sepolia ETH (mínimo recomendado ~0.005 ETH).")
        return

    artifact_path = OUT_DIR / "AgroToken.sol" / "AgroToken.json"
    if not artifact_path.exists():
        print("❌ Artefato compilado não encontrado. Execute 'forge build' primeiro.")
        return

    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)

    bytecode = artifact["bytecode"]["object"]
    abi = artifact["abi"]

    print("[1/3] Preparando transação de implantação do AgroToken...")
    factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(deployer, "pending")
    
    # Construtor recebe initialRecipient (deployer)
    gas_estimate = factory.constructor(deployer).estimate_gas({"from": deployer})
    gas_price = w3.eth.gas_price

    tx = factory.constructor(deployer).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gas": int(gas_estimate * 1.25),
        "gasPrice": int(gas_price * 1.2),
        "chainId": SEPOLIA_CHAIN_ID
    })

    print("[2/3] Assinando e enviando transação para a rede Sepolia...")
    signed = w3.eth.account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hex = tx_hash.hex()
    print(f"  • Transação enviada: https://sepolia.etherscan.io/tx/{tx_hex}")
    print("  • Aguardando confirmação no bloco (geralmente leva 10-15 segundos)...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    if receipt.status != 1:
        print("❌ A transação falhou ao ser minerada na rede.")
        return

    token_address = receipt.contractAddress
    print("\n" + "=" * 70)
    print("🎉 DEPLOY CONCLUÍDO COM SUCESSO!")
    print("=" * 70)
    print(f"  • Contrato $AGRO:  {token_address}")
    print(f"  • Etherscan:       https://sepolia.etherscan.io/address/{token_address}")
    print(f"  • Titular Inicial: {deployer} (recebeu 20.000.000 $AGRO)")
    print("=" * 70)

    # Atualizar sepolia_deployed_addresses.json
    try:
        data = {}
        if SEPOLIA_DEPLOY_FILE.exists():
            with open(SEPOLIA_DEPLOY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["AgroToken"] = token_address
        if "etherscan" not in data:
            data["etherscan"] = {}
        data["etherscan"]["AgroToken"] = f"https://sepolia.etherscan.io/address/{token_address}"
        with open(SEPOLIA_DEPLOY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"📁 Atualizado com sucesso em: {SEPOLIA_DEPLOY_FILE.name}")
    except Exception as e:
        print(f"Aviso ao salvar json: {e}")

if __name__ == "__main__":
    main()
