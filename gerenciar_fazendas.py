"""
AgroFi - Módulo de Gerenciamento Seguro de Chaves e Fazendas
Deriva endereços públicos a partir de chaves privadas armazenadas com segurança no .env,
atualizando farms_config.json sem NUNCA vazar chaves privadas para o frontend ou repositório.
"""
import os
import json
from pathlib import Path
from eth_account import Account

ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"
FARMS_CONFIG_PATH = ROOT_DIR / "farms_config.json"


def carregar_env():
    """Carrega variáveis do arquivo .env local sem expor logs sensíveis."""
    env_vars = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars


def salvar_fazenda_segura(land_id: str, farm_name: str, private_key: str, car_code: str = "", municipality: str = "", state: str = ""):
    """
    Registra ou atualiza uma fazenda garantindo que:
    1. A chave privada seja salva EXCLUSIVAMENTE no .env (ignorado pelo git e protegido no SO).
    2. Apenas o endereço público seja salvo no farms_config.json (consumido pela interface web).
    """
    # 1. Valida e deriva o endereço público
    try:
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        acct = Account.from_key(private_key)
        public_address = acct.address
    except Exception as e:
        raise ValueError(f"Chave privada inválida: {e}")

    # 2. Atualiza o .env com a chave privada
    env_vars = carregar_env()
    key_var_name = f"PRIVATE_KEY_{land_id.replace('-', '_')}"
    env_vars[key_var_name] = private_key

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("# AgroFi - Chaves Privadas das Fazendas (ARQUIVO PROTEGIDO - NUNCA COMPARTILHE)\n")
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")

    # 3. Atualiza farms_config.json contendo APENAS o endereço público
    if FARMS_CONFIG_PATH.exists():
        with open(FARMS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"farms": []}

    farms = data.get("farms", [])
    found = False
    for farm in farms:
        if farm.get("land_id") == land_id:
            farm["farm_name"] = farm_name
            farm["wallet_address"] = public_address
            if "private_key_test" in farm:
                del farm["private_key_test"]
            if car_code:
                farm["car_code"] = car_code
            if municipality:
                farm["municipality"] = municipality
            if state:
                farm["state"] = state
            found = True
            break

    if not found:
        farms.append({
            "land_id": land_id,
            "farm_name": farm_name,
            "car_code": car_code or f"{state or 'BR'}-0000000-PADRAO",
            "municipality": municipality or "Região Agrícola",
            "state": state or "BR",
            "biome": "Cerrado",
            "wallet_address": public_address,
            "nft_token_id": len(farms) + 1,
            "productive_area_ha": 1000.0,
            "total_area_ha": 1500.0,
            "owner_name": f"Produtor {farm_name}",
            "credit_limit_usd": 250000.0,
            "current_loan_usd": 0.0
        })

    data["farms"] = farms
    with open(FARMS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return public_address


if __name__ == "__main__":
    print("Módulo de Gerenciamento Seguro de Chaves AgroFi carregado.")
