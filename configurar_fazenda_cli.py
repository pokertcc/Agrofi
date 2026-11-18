"""
AgroFi - CLI de Configuração Segura de Fazendas (Padrão de Produção Web3)
Permite cadastrar as 4 fazendas com proteção total das chaves privadas no .env local.
"""
import os
import sys
import json
import getpass
from pathlib import Path
from eth_account import Account

ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"
FARMS_CONFIG_PATH = ROOT_DIR / "farms_config.json"


def obter_ou_criar_env():
    env_vars = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars


def salvar_env(env_vars):
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("# ================================================================\n")
        f.write("# AgroFi Protocol - Cofre Seguro de Chaves Privadas (PRODUÇÃO)\n")
        f.write("# NUNCA submeta este arquivo ao Git ou compartilhe com terceiros.\n")
        f.write("# ================================================================\n\n")
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")


def cadastrar_4_fazendas():
    print("=" * 65)
    print("🌾 AGROFI PROTOCOL - CONFIGURAÇÃO SEGURA DAS 4 FAZENDAS")
    print("=" * 65)
    print("Modo de Segurança de Produção ativado:")
    print("• As chaves privadas serão gravadas EXCLUSIVAMENTE no arquivo .env local.")
    print("• Apenas os endereços públicos (0x...) serão expostos ao portal web.\n")

    env_vars = obter_ou_criar_env()

    # Modelos padrão de fazendas
    padroes = [
        {"land_id": "TALHAO-MT-001", "default_name": "Fazenda Santa Helena", "city": "Sorriso", "uf": "MT", "car": "MT-5107925-8A4F1D9C3E2B4A1F8C2D3E4F5A6B7C8D", "area": 1420.0, "total": 1850.0, "crop": "Soja & Milho", "credit": 250000.0, "loan": 150000.0},
        {"land_id": "TALHAO-GO-002", "default_name": "Fazenda Boa Esperança", "city": "Rio Verde", "uf": "GO", "car": "GO-5218805-4B8C1D2E3F4A5B6C7D8E9F0A1B2C3D4E", "area": 1040.0, "total": 1320.0, "crop": "Grãos & Sorgo", "credit": 180000.0, "loan": 80000.0},
        {"land_id": "TALHAO-MT-003", "default_name": "Agropecuária Chapadão", "city": "Sapezal", "uf": "MT", "car": "MT-5107875-9C0D1E2F3A4B5C6D7E8F9A0B1C2D3E4F", "area": 1520.0, "total": 2400.0, "crop": "Algodão & Soja", "credit": 320000.0, "loan": 200000.0},
        {"land_id": "TALHAO-BA-004", "default_name": "Fazenda Ouro Verde", "city": "Luís Eduardo Magalhães", "uf": "BA", "car": "BA-2919553-7A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D", "area": 1220.0, "total": 1600.0, "crop": "Soja Irrigada", "credit": 210000.0, "loan": 95000.0},
    ]

    farms_list = []

    for i, p in enumerate(padroes, 1):
        print(f"\n--- [FAZENDA {i}/4] ---")
        nome = input(f"Nome da Fazenda [{p['default_name']}]: ").strip() or p['default_name']
        
        while True:
            pk = input(f"Chave Privada da {nome} (0x...): ").strip()
            if not pk:
                print("❌ A chave privada não pode ser vazia. Tente novamente.")
                continue
            if not pk.startswith("0x"):
                pk = "0x" + pk
            try:
                acct = Account.from_key(pk)
                public_addr = acct.address
                print(f"✅ Chave válida! Endereço público derivado: {public_addr}")
                break
            except Exception as e:
                print(f"❌ Chave inválida: {e}. Certifique-se de que possui 64 caracteres hexadecimais.")

        # Guarda a chave privada no .env
        env_key = f"PRIVATE_KEY_{p['land_id'].replace('-', '_')}"
        env_vars[env_key] = pk

        farms_list.append({
            "land_id": p["land_id"],
            "farm_name": nome,
            "car_code": p["car"],
            "municipality": p["city"],
            "state": p["uf"],
            "biome": "Cerrado" if p["uf"] != "MT" or "Sorriso" not in p["city"] else "Amazônia",
            "wallet_address": public_addr,
            "nft_token_id": i,
            "main_crop": p["crop"],
            "productive_area_ha": p["area"],
            "total_area_ha": p["total"],
            "owner_name": f"Produtor {nome}",
            "credit_limit_usd": p["credit"],
            "current_loan_usd": p["loan"]
        })

    # Grava o .env de forma segura
    salvar_env(env_vars)
    print("\n🔒 Chaves privadas salvas com sucesso em .env (protegido pelo .gitignore).")

    # Grava o farms_config.json contendo APENAS metadados públicos
    with open(FARMS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"farms": farms_list}, f, indent=2, ensure_ascii=False)

    print("📄 Arquivo farms_config.json atualizado com os novos endereços públicos.")
    print("🎉 Configuração concluída! Acesse http://localhost:8080 para visualizar.")


if __name__ == "__main__":
    cadastrar_4_fazendas()
