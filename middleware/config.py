import os
import json
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "out"
DEPLOYED_ADDRESSES_FILE = BASE_DIR / "deployed_addresses.json"

# RPC & Network (Suporta tanto nó local Anvil quanto Ethereum Sepolia Testnet)
LOCAL_RPC_URL = os.getenv("LOCAL_RPC_URL", "http://127.0.0.1:8545")
SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")

def is_local_node_alive(host: str = "127.0.0.1", port: int = 8545, timeout: float = 0.5) -> bool:
    """Verifica rapidamente se um nó local (Anvil / Hardhat) está ativo na porta 8545."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False

def get_default_network():
    """
    Determina a rede padrão:
    1. Se RPC_URL for definida explicitamente pelo usuário, respeita a variável de ambiente.
    2. Se um nó local Anvil (127.0.0.1:8545) estiver rodando, prioriza o ambiente local (Chain ID 31337).
    3. Caso contrário, utiliza a Ethereum Sepolia Testnet (Chain ID 11155111).
    """
    env_rpc = os.getenv("RPC_URL")
    env_chain = os.getenv("CHAIN_ID")

    if env_rpc:
        chain_id = int(env_chain) if env_chain else (11155111 if "sepolia" in env_rpc.lower() else 31337)
        return env_rpc, chain_id

    # Prioriza o nó local se estiver rodando
    if is_local_node_alive():
        return LOCAL_RPC_URL, 31337

    return SEPOLIA_RPC_URL, 11155111

RPC_URL, CHAIN_ID = get_default_network()

# Standard Pre-funded Anvil Test Accounts (10,000 ETH each)
ACCOUNTS = {
    "admin": {
        "address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "private_key": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    },
    "farmer": {
        "address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "private_key": "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
    },
    "lender": {
        "address": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
        "private_key": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
    },
    "liquidator": {
        "address": "0x90F79bf6EB2c4f870365E785982E1f101E93b906",
        "private_key": "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"
    }
}

def load_artifact(contract_name: str) -> dict:
    artifact_path = OUT_DIR / f"{contract_name}.sol" / f"{contract_name}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact for {contract_name} not found at {artifact_path}. Run 'forge build' first.")
    with open(artifact_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_deployed_addresses(chain_id: int = None) -> dict:
    active_chain = chain_id or CHAIN_ID
    sepolia_file = BASE_DIR / "sepolia_deployed_addresses.json"

    # Se for rede local Anvil (31337) ou similar, carregar deployed_addresses.json
    if active_chain == 31337 or "127.0.0.1" in RPC_URL or "localhost" in RPC_URL:
        if DEPLOYED_ADDRESSES_FILE.exists():
            with open(DEPLOYED_ADDRESSES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)

    # Se for Sepolia (11155111)
    if active_chain == 11155111 or "sepolia" in RPC_URL.lower():
        if sepolia_file.exists():
            with open(sepolia_file, "r", encoding="utf-8") as f:
                return json.load(f)

    # Fallbacks caso o arquivo específico não exista
    if DEPLOYED_ADDRESSES_FILE.exists():
        with open(DEPLOYED_ADDRESSES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    if sepolia_file.exists():
        with open(sepolia_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_deployed_addresses(addresses: dict) -> None:
    with open(DEPLOYED_ADDRESSES_FILE, "w", encoding="utf-8") as f:
        json.dump(addresses, f, indent=2)
