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
SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
SEPOLIA_CHAIN_ID = 11155111

# Endereços dos contratos na Sepolia
USDC_ADDRESS = "0x178B9bFA3E86a9Ed3F67963e28afBe49BCf45ED2"
AGRO_ADDRESS = "0xBBa1B54b0b6962F586a9971965811b79b1CdAeB8"

ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"}
        ],
        "name": "mint",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "mintRewards",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

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

def send_faucet(target_address: str, usdc_amount: int = 10000, agro_amount: int = 5000):
    pk = load_private_key()
    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
    if not w3.is_connected():
        print(f"❌ Erro ao conectar ao RPC Sepolia: {SEPOLIA_RPC_URL}")
        return

    admin_acc = Account.from_key(pk)
    target = Web3.to_checksum_address(target_address)
    
    print("=" * 70)
    print("💧 FAUCET SEPOLIA - AGROFI PROTOCOL")
    print("=" * 70)
    print(f"  • Pagador (Admin): {admin_acc.address}")
    print(f"  • Destinatário:     {target}")
    print(f"  • Dólares (USDC):   {usdc_amount:,.2f} USDC")
    print(f"  • Tokens $AGRO:     {agro_amount:,.2f} $AGRO")
    print("-" * 70)

    # 1. Mint USDC
    usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
    agro_contract = w3.eth.contract(address=Web3.to_checksum_address(AGRO_ADDRESS), abi=ERC20_ABI)

    nonce = w3.eth.get_transaction_count(admin_acc.address, "pending")
    gas_price = int(w3.eth.gas_price * 1.2)

    # Transação 1: Mint USDC
    print("⏳ [1/2] Emitindo MockUSDC para a carteira...")
    usdc_wei = usdc_amount * 10**18
    tx1 = usdc_contract.functions.mint(target, usdc_wei).build_transaction({
        "from": admin_acc.address,
        "nonce": nonce,
        "gas": 120000,
        "gasPrice": gas_price,
        "chainId": SEPOLIA_CHAIN_ID
    })
    signed1 = w3.eth.account.sign_transaction(tx1, pk)
    tx1_hash = w3.eth.send_raw_transaction(signed1.raw_transaction)
    print(f"  • Tx USDC: https://sepolia.etherscan.io/tx/{tx1_hash.hex()}")

    # Transação 2: Mint $AGRO
    print("⏳ [2/2] Emitindo $AGRO de incentivo para a carteira...")
    agro_wei = agro_amount * 10**18
    tx2 = agro_contract.functions.mintRewards(target, agro_wei).build_transaction({
        "from": admin_acc.address,
        "nonce": nonce + 1,
        "gas": 120000,
        "gasPrice": gas_price,
        "chainId": SEPOLIA_CHAIN_ID
    })
    signed2 = w3.eth.account.sign_transaction(tx2, pk)
    tx2_hash = w3.eth.send_raw_transaction(signed2.raw_transaction)
    print(f"  • Tx $AGRO: https://sepolia.etherscan.io/tx/{tx2_hash.hex()}")

    print("\n⏳ Aguardando confirmação dos blocos na Sepolia...")
    w3.eth.wait_for_transaction_receipt(tx1_hash, timeout=120)
    w3.eth.wait_for_transaction_receipt(tx2_hash, timeout=120)

    # Checar saldos finais
    bal_usdc = usdc_contract.functions.balanceOf(target).call() / 10**18
    bal_agro = agro_contract.functions.balanceOf(target).call() / 10**18

    print("=" * 70)
    print("🎉 FAUCET EXECUTADO COM SUCESSO!")
    print(f"  • Novo Saldo USDC:  {bal_usdc:,.2f} USDC")
    print(f"  • Novo Saldo $AGRO:  {bal_agro:,.2f} $AGRO")
    print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        addr = sys.argv[1].strip()
    else:
        addr = "0xa449e7838fF89EE956174B682449870597e93C71"
    send_faucet(addr)
