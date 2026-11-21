# 🌾 AgroFi Protocol - Guia de Integração (Módulo 2: Web3 & Smart Contracts)

Este repositório contém a infraestrutura descentralizada do **AgroFi Protocol**:
- **Smart Contracts (Solidity v0.8.24)**: Emissão de stablecoin (`MockUSDC`), tokenização de safra agrícola como colateral (`AgroNFT`) e cofre de empréstimos e liquidação paramétrica (`LendingPool`).
- **Middleware & Oráculo Web3.py**: Traduz métricas agro (NDVI, déficit pluviométrico, umidade do solo) em risco on-chain (LTV e Fator de Saúde).
- **Painéis Visuais**: `dashboard.html` (DeFi & Simulação de Risco) e `explorer.html` (AgroFiScan / Comprovantes).

---

## 🌐 1. Contratos Já Ativos na Blockchain (Ethereum Sepolia)

> [!NOTE]
> **Você NÃO precisa compilar ou fazer deploy de contratos!**  
> Os contratos inteligentes já estão oficialmente implantados e ativos na rede pública Ethereum Sepolia:

- 💵 **MockUSDC (ERC-20):** [`0x178B9bFA3E86a9Ed3F67963e28afBe49BCf45ED2`](https://sepolia.etherscan.io/address/0x178B9bFA3E86a9Ed3F67963e28afBe49BCf45ED2)
- 🌱 **AgroNFT (ERC-721):** [`0xb89Cd470755AD1E25052b57D97af6Fc98b00Dfb2`](https://sepolia.etherscan.io/address/0xb89Cd470755AD1E25052b57D97af6Fc98b00Dfb2)
- 🏦 **LendingPool (DeFi):** [`0x020c06c4d1410B2131e9815c5D25F7Ee90D37a26`](https://sepolia.etherscan.io/address/0x020c06c4d1410B2131e9815c5D25F7Ee90D37a26)
- 👤 **Deployer / Oracle:** [`0xa449e7838fF89EE956174B682449870597e93C71`](https://sepolia.etherscan.io/address/0xa449e7838fF89EE956174B682449870597e93C71)

Todos os endereços e metadados estão salvos no arquivo `sepolia_deployed_addresses.json`.

---

## ⚙️ 2. Instalação das Dependências no seu Computador

No terminal (na pasta raiz do projeto), execute:

```bash
# 1. (Opcional) Crie e ative um ambiente virtual
python -m venv .venv
# No Windows:
.\.venv\Scripts\activate
# No Linux/Mac:
source .venv/bin/activate

# 2. Instale as dependências necessárias
pip install -r requirements.txt
```

---

## 🚀 3. Como a Parte 1 (Camada Agro) Conecta no Middleware

Você pode conectar a inteligência da Parte 1 com o Módulo Web3 de **duas formas**:

### Método A: Import Direto no Python (Recomendado - Mais Rápido)
No seu script Python ou Jupyter Notebook da Parte 1, importe diretamente as classes do `middleware`:

```python
from middleware.web3_client import AgroFiWeb3Client
from middleware.oracle_service import AgroRiskOracle, AgroRiskData

# 1. Inicializa o cliente Web3 conectado à rede
client = AgroFiWeb3Client()
oracle = AgroRiskOracle(client)

# 2. Quando o seu modelo calcular a saúde da lavoura:
telemetria_safra = AgroRiskData(
    ndvi=0.28,                     # Índice de Vegetação (0.0 a 1.0)
    precipitation_deficit=-0.70,   # Déficit hídrico (-0.70 = -70%)
    soil_moisture=18.0,            # Umidade do solo (%)
    commodity_price_ratio=0.95     # Cotação em relação à base
)

# 3. Transmite e grava a nota de risco diretamente no Smart Contract
# Token ID #1 = Safra da Fazenda Santa Fé
tx_hash, novo_ltv, novo_hf = oracle.push_risk_update(token_id=1, data=telemetria_safra)

print(f"✅ Atualização gravada com sucesso!")
print(f"• Novo LTV: {novo_ltv / 100:.2f}%")
print(f"• Novo Health Factor: {novo_hf / 10000:.2f}x")
print(f"• Hash da Transação: {tx_hash}")
```

### Método B: Via API REST (FastAPI)
Se preferir rodar como um microsserviço independente com interface Swagger:

1. No terminal, inicie o servidor:
```bash
uvicorn middleware.api_server:app --reload --port 8000
```
2. Abra a documentação interativa no navegador:
`http://127.0.0.1:8000/docs`

3. O seu script da Parte 1 pode enviar dados via `requests`:
```python
import requests

payload = {
    "token_id": 1,
    "ndvi": 0.28,
    "precipitation_deficit": -0.70,
    "soil_moisture": 18.0,
    "commodity_price_ratio": 0.95
}

response = requests.post("http://127.0.0.1:8000/api/risk/evaluate-and-push", json=payload)
print(response.json())
```

---

## 🖥️ 4. Visualização dos Painéis Gráficos

Para visualizar o ecossistema em funcionamento, basta abrir os arquivos `.html` no seu navegador:

- **`dashboard.html`**: Painel visual completo do protocolo AgroFi, simulador de oráculo de risco, monitoramento de LTV/Health Factor e botão de liquidação paramétrica.
- **`explorer.html`**: AgroFiScan, explorador de blocos e emissor de comprovantes de transação com exportação em PDF.
- **`wallet.html`**: Carteira Web3 multi-contas para inspecionar os saldos do Produtor, Credor e Liquidador.

---

## 🧪 5. Scripts de Teste e Demonstração

Para rodar uma validação completa passo a passo da infraestrutura:

```bash
# Executa o roteiro completo de 6 etapas (Emissão, Depósito, Empréstimo, Oráculo e Liquidação)
python step_by_step_test.py
```
