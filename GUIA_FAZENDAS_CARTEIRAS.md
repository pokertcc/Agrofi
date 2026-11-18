# 🌾 AgroFi Protocol - Guia de Configuração de Fazendas & Carteiras Web3

Este documento explica como funciona a arquitetura onde **cada fazenda cadastrada é associada a uma carteira Web3 (Ethereum/Sepolia/Anvil)**, como o portal principal (`http://localhost:8080`) se comunica com o painel de inteligência geoespacial (`http://localhost:8501`), e o passo a passo para adicionar ou alterar fazendas no protocolo.

---

## 1. Arquitetura de Navegação Integrada

```
+-------------------------------------------------------------+
|               PORTAL PRINCIPAL (localhost:8080)             |
|                                                             |
|   1. Usuário clica em "🦊 Conectar Carteira Web3"           |
|      (Detecta MetaMask ou seleciona a Fazenda)              |
|                                                             |
|   2. Cada Fazenda possui seu endereço Ethereum              |
|      vinculado ao seu CAR (Cadastro Ambiental Rural)        |
+------------------------------+------------------------------+
                               |
                               v (Redirecionamento Automático com parâmetros)
+-------------------------------------------------------------+
|          PAINEL DE INTELIGÊNCIA AGRO (localhost:8501)       |
|                                                             |
|   URL: http://localhost:8501/?land_id=...&wallet=0x...     |
|                                                             |
|   - Selo verde de Carteira Conectada no Topo e Sidebar      |
|   - Talhão selecionado automaticamente no MapLibre GL JS    |
|   - Valoração por Machine Learning & Análise NDVI           |
|   - Botão para retornar ao Portal Principal (:8080)         |
+-------------------------------------------------------------+
```

---

## 2. Fazendas e Carteiras Padrão Cadastradas

O arquivo [`farms_config.json`](file:///c:/Users/T-Gamer/Desktop/AgroFi/farms_config.json) é o repositório central de mapeamento:

| Identificador (`land_id`) | Nome da Fazenda | Localização / Bioma | Endereço da Carteira Web3 | Chave Privada de Teste (Anvil) | Limite Crédito |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`TALHAO-MT-001`** | **Fazenda Santa Helena** | Sorriso - MT (Amazônia) | `0x70997970C51812dc3A010C7d01b50e0d17dc79C8` | `0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d` | $250.000 USDC |
| **`TALHAO-GO-002`** | **Fazenda Boa Esperança** | Rio Verde - GO (Cerrado) | `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC` | `0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a` | $180.000 USDC |
| **`TALHAO-MT-003`** | **Agropecuária Chapadão** | Sapezal - MT (Cerrado) | `0x90F79bf6EB2c4f870365E785982E1f101E93b906` | `0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6` | $320.000 USDC |
| **`TALHAO-BA-004`** | **Fazenda Ouro Verde** | LEM - BA (Cerrado) | `0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65` | `0x47e179ec3427449b3b95b829b9c79d009b33e8a9632171950e7f07e6ae83a49b` | $210.000 USDC |
| **`ORACLE-ADMIN`** | **AgroFi Keeper / Relayer** | Infraestrutura | `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` | `0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80` | - |

---

## 3. Como Configurar e Adicionar uma Nova Fazenda

### Passo 1: Adicionar a entrada no `farms_config.json`
Abra o arquivo [`farms_config.json`](file:///c:/Users/T-Gamer/Desktop/AgroFi/farms_config.json) e adicione um novo bloco na lista `"farms"`:

```json
{
  "land_id": "TALHAO-PR-005",
  "farm_name": "Fazenda Vale do Sol",
  "car_code": "PR-4104808-1A2B3C4D5E6F7A8B9C0D1E2F3A4B5C6D",
  "municipality": "Cascavel",
  "state": "PR",
  "biome": "Mata Atlântica",
  "wallet_address": "0xSeuEnderecoMetaMaskAqui...",
  "private_key_test": "0xChavePrivadaOpcional...",
  "nft_token_id": 5,
  "main_crop": "Soja & Trigo",
  "productive_area_ha": 950.0,
  "total_area_ha": 1200.0,
  "owner_name": "Produtor Rural 5 (Cascavel - PR)",
  "credit_limit_usd": 220000.0,
  "current_loan_usd": 0.0
}
```

### Passo 2: Cadastrar as Geometrias do CAR (Opcional se desejar polígono vetorial)
No arquivo [`src/etl/sicar_ingestor.py`](file:///c:/Users/T-Gamer/Desktop/AgroFi/src/etl/sicar_ingestor.py), na função `generate_benchmark_car_features`, inclua o polígono do imóvel com suas coordenadas geográficas (latitude, longitude, área de reserva legal e área consolidada).

### Passo 3: Importar a Carteira no MetaMask
1. Abra a extensão **MetaMask** no seu navegador;
2. Clique no menu de contas (canto superior direito) $\rightarrow$ **Adicionar conta ou carteira de hardware** $\rightarrow$ **Importar conta**;
3. Cole a **chave privada** correspondente à fazenda;
4. Dê o nome da fazenda para a conta (ex: *"AgroFi - Fazenda Santa Helena"*);
5. Escolha a rede **Ethereum Sepolia Testnet** ou a rede local **Anvil (RPC: `http://127.0.0.1:8545`, Chain ID: `31337`)**.

---

## 4. Como Usar no Dia a Dia

1. Abra **`http://localhost:8080`** no seu navegador (Página Principal);
2. Clique em **"🦊 Conectar Carteira Web3"** ou clique diretamente no card da fazenda que deseja operar;
3. O sistema reconhece a carteira, grava a sessão e redireciona automaticamente para **`http://localhost:8501/?land_id=...&wallet=...`**;
4. No Streamlit (`localhost:8501`), você verá:
   - Banner de **Fazenda Conectada via Web3** com endereço da carteira;
   - Mapa vetorial focado no talhão selecionado;
   - Curva de fenologia NDVI e simulação de secas;
   - Botão **"🏠 Voltar ao Portal AgroFi (8080)"** para retornar quando desejar.
