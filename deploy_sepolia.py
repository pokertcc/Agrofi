import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import json
from web3 import Web3
from eth_account import Account
from pathlib import Path

# Paths & Sepolia Configuration
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "out"
SEPOLIA_DEPLOY_FILE = BASE_DIR / "sepolia_deployed_addresses.json"
SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
SEPOLIA_CHAIN_ID = 11155111

def load_artifact(contract_name: str) -> dict:
    artifact_path = OUT_DIR / f"{contract_name}.sol" / f"{contract_name}.json"
    with open(artifact_path, "r", encoding="utf-8") as f:
        return json.load(f)

def deploy_to_sepolia(private_key: str):
    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Não foi possível conectar ao nó Sepolia: {SEPOLIA_RPC_URL}")

    account = Account.from_key(private_key)
    deployer_addr = account.address
    balance_wei = w3.eth.get_balance(deployer_addr)
    balance_eth = w3.from_wei(balance_wei, "ether")

    print("=" * 75)
    print("🌾 DEPLOY DO PROTOCOLO AGROFI NA REDE ETHEREUM SEPOLIA (TESTNET PÚBLICA)")
    print("=" * 75)
    print(f"  • Carteira Deployer: {deployer_addr}")
    print(f"  • Saldo Sepolia ETH: {balance_eth:.5f} ETH")
    print(f"  • RPC Conectado:     {SEPOLIA_RPC_URL}")
    print("=" * 75)

    if balance_eth < 0.01:
        print("\n❌ Saldo insuficiente para pagar o gás da implantação dos 3 contratos.")
        print("   Você precisa de pelo menos ~0.02 Sepolia ETH.")
        print("   Obtenha gratuitamente em: https://cloud.google.com/application/web3/faucet/ethereum/sepolia")
        return

    def _deploy(contract_name: str, *constructor_args):
        print(f"\n[Deploying {contract_name} na Sepolia...]")
        artifact = load_artifact(contract_name)
        bytecode = artifact["bytecode"]["object"]
        abi = artifact["abi"]

        factory = w3.eth.contract(abi=abi, bytecode=bytecode)
        nonce = w3.eth.get_transaction_count(deployer_addr, "pending")

        gas_estimate = factory.constructor(*constructor_args).estimate_gas({"from": deployer_addr})
        gas_price = w3.eth.gas_price

        tx = factory.constructor(*constructor_args).build_transaction({
            "from": deployer_addr,
            "nonce": nonce,
            "gas": int(gas_estimate * 1.25),
            "gasPrice": int(gas_price * 1.15),
            "chainId": SEPOLIA_CHAIN_ID
        })

        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  • Tx Enviada: https://sepolia.etherscan.io/tx/{tx_hash.hex()}")
        print("  • Aguardando confirmação do bloco na Sepolia...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        if receipt.status != 1:
            raise RuntimeError(f"Deploy de {contract_name} falhou!")
        print(f"  ✅ {contract_name} implantado em: {receipt.contractAddress}")
        return receipt.contractAddress

    # 1. Deploy MockUSDC
    usdc_addr = _deploy("MockUSDC")
    # 2. Deploy AgroNFT
    nft_addr = _deploy("AgroNFT")
    # 3. Deploy LendingPool
    pool_addr = _deploy("LendingPool", usdc_addr, nft_addr)

    deployed = {
        "network": "Ethereum Sepolia Testnet",
        "chainId": SEPOLIA_CHAIN_ID,
        "deployer": deployer_addr,
        "MockUSDC": usdc_addr,
        "AgroNFT": nft_addr,
        "LendingPool": pool_addr,
        "etherscan": {
            "MockUSDC": f"https://sepolia.etherscan.io/address/{usdc_addr}",
            "AgroNFT": f"https://sepolia.etherscan.io/address/{nft_addr}",
            "LendingPool": f"https://sepolia.etherscan.io/address/{pool_addr}"
        }
    }

    with open(SEPOLIA_DEPLOY_FILE, "w", encoding="utf-8") as f:
        json.dump(deployed, f, indent=2)

    print("\n" + "=" * 75)
    print("🎉 SUCESSO! PROTOCOLO AGROFI IMPLANTADO NA SEPOLIA COM LINKS PÚBLICOS:")
    print("=" * 75)
    print(f"💵 MockUSDC:    https://sepolia.etherscan.io/address/{usdc_addr}")
    print(f"🌱 AgroNFT:     https://sepolia.etherscan.io/address/{nft_addr}")
    print(f"🏦 LendingPool: https://sepolia.etherscan.io/address/{pool_addr}")
    print("=" * 75)
    print(f"Endereços salvos com sucesso em: {SEPOLIA_DEPLOY_FILE}")

if __name__ == "__main__":
    pk = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SEPOLIA_PRIVATE_KEY")
    if not pk:
        pk = input("Cole a chave privada da sua carteira com Sepolia ETH (ex: 0x...): ").strip()
    deploy_to_sepolia(pk)
