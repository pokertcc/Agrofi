# 📋 Roteiro de Testes Passo a Passo - Protocolo AgroFi (Web3 & DeFi)

Este relatório é um guia prático para você executar e conferir, com seus próprios olhos, cada uma das operações financeiras e contratuais do protocolo AgroFi no nó local Anvil:

1. **Transferências de Tokens** (`MockUSDC`)
2. **Depósito e Gestão da Pool de Liquidez** (`LendingPool`)
3. **Tokenização da Safra Agrícola** (`AgroNFT`)
4. **Colateralização e Saque do Empréstimo** (`borrow`)
5. **Pagamento da Dívida e Resgate do Colateral** (`repay` & `withdrawCollateral`)
6. **Choque Climático (Oráculo) & Liquidação Paramétrica** (Proteção sem processo judicial)

---

## 🚀 Método Mais Rápido: Execução Automática Interativa

Criamos um script que executa todas as etapas e permite que você pause a cada transação para conferir:

```powershell
# Execução com pausas entre cada etapa para você conferir:
.\.venv\Scripts\python.exe step_by_step_test.py --interactive

# Ou execução direta contínua:
.\.venv\Scripts\python.exe step_by_step_test.py
```

---

## 🔬 Roteiro Detalhado Passo a Passo (O que acontece em cada fase)

### 📌 Passo 1: Emissão e Transferência de Tokens (MockUSDC)
- **O que faz**: O Administrador emite \$500.000 USDC para a carteira do Credor e \$60.000 USDC para a carteira do Produtor.
- **Contrato**: `MockUSDC.sol` (`0x5FbDB2315678afecb367f032d93F642f64180aa3`)
- **Como conferir no terminal**:
  ```powershell
  .\.venv\Scripts\python.exe inspect_tokens.py
  ```
- **Resultado esperado**:
  - Saldo Credor: `+$500,000.00 USDC`
  - Saldo Produtor: `+$60,000.00 USDC`

---

### 📌 Passo 2: Fornecer Liquidez à Pool (LendingPool)
- **O que faz**: O Credor (Lender) deposita \$300.000 USDC na `LendingPool` para financiar safras e gerar rendimentos.
- **Função On-Chain**: `LendingPool.depositLiquidity(300000 * 1e6)`
- **Resultado esperado**:
  - Saldo da carteira do Credor cai em \$300.000 USDC.
  - A Liquidez Disponível na `LendingPool` sobe para **\$300.000,00 USDC**.
- **Como conferir**:
  ```powershell
  cast call 0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0 "availableLiquidity()(uint256)"
  # Retorna: 300000000000 (300,000 USDC com 6 decimais)
  ```

---

### 📌 Passo 3: Tokenização da Safra Agrícola (AgroNFT)
- **O que faz**: O produtor rural tokeniza a safra futura de 500 hectares de soja.
- **Função On-Chain**: `AgroNFT.mintCollateral(produtor, "ipfs://...", 100000 * 1e6)`
- **Métricas registradas**:
  - `appraisalValue`: **\$100.000,00 USDC**
  - `ltv`: **60.00%** (Capacidade máxima de crédito de \$60.000 USDC)
  - `healthFactor`: **1.50x** (15000 bps - Status Seguro)
- **Como conferir**:
  - No Rabby Wallet ou na [**`wallet.html`**](file:///c:/Users/T-Gamer/Desktop/Projeto%20AgroFi/wallet.html), a conta do Produtor exibirá `1 NFT (Token #1)`.

---

### 📌 Passo 4: Depósito de Colateral & Saque de Empréstimo (borrow)
- **O que faz**:
  1. O Produtor transfere a custódia do `AgroNFT #1` para a `LendingPool`.
  2. O Produtor saca **\$50.000,00 USDC** de empréstimo.
- **Funções On-Chain**:
  - `LendingPool.depositCollateral(1)`
  - `LendingPool.borrow(1, 50000 * 1e6)`
- **Resultado esperado**:
  - Saldo USDC do Produtor aumenta em **+\$50.000,00 USDC**.
  - A `LendingPool` registra uma dívida ativa de **\$50.000,00 USDC**.
  - A liquidez disponível na pool cai de \$300.000 para **\$250.000 USDC**.
- **Como conferir**:
  ```powershell
  # Conferir dívida registrada:
  cast call 0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0 "getLoan(uint256)((address,uint256,bool,uint256))" 1
  ```

---

### 📌 Passo 5: Pagamento do Empréstimo (repay) & Resgate do Colateral
- **O que faz**: O Produtor devolve os \$50.000 USDC para a pool e retira seu NFT de volta.
- **Funções On-Chain**:
  - `LendingPool.repay(1, 50000 * 1e6)`
  - `LendingPool.withdrawCollateral(1)`
- **Resultado esperado**:
  - Dívida do empréstimo vai a **\$0.00 USDC**.
  - Empréstimo é marcado como inativo (`isActive: false`).
  - O `AgroNFT #1` sai da custódia do contrato e volta para a carteira do Produtor.
- **Como conferir**:
  - Abra a [**`wallet.html`**](file:///c:/Users/T-Gamer/Desktop/Projeto%20AgroFi/wallet.html) na conta Produtor: o NFT estará de volta sob sua posse!

---

### 📌 Passo 6: Choque Agroclimático (Oráculo) & Liquidação Paramétrica
- **O que faz**:
  1. O produtor toma outro empréstimo de \$40.000 USDC.
  2. O Oráculo Web3.py detecta uma seca severa por satélite (**NDVI 0.25** e **-75% de chuva**).
  3. O Oráculo chama `updateLTVAndHealthFactor`, reduzindo o Health Factor para **0.03x (< 1.00x)**.
  4. Um Liquidador executa a **Liquidação Paramétrica**: cobre os \$40.000 USDC e assume o colateral digital na hora, sem depender de decisão judicial de reintegração de terra.
- **Resultado esperado**:
  - A pool de liquidez não sofre calote (o liquidador quitou os \$40.000 USDC).
  - O NFT passa para a posse da carteira do Liquidador (`0x90F7...b906`).

---

## 🖥️ Como Acompanhar Visualmente pelo Navegador

Você pode manter o [**`dashboard.html`**](file:///c:/Users/T-Gamer/Desktop/Projeto%20AgroFi/dashboard.html) e a [**`wallet.html`**](file:///c:/Users/T-Gamer/Desktop/Projeto%20AgroFi/wallet.html) abertos no navegador enquanto roda o teste no terminal:

```powershell
# Abrir o Painel Visual com os gráficos e medidor de Health Factor:
Start-Process "dashboard.html"

# Abrir a Carteira com os saldos de todas as 4 contas:
Start-Process "wallet.html"
```

Toda transação enviada no terminal ou nos scripts reflete instantaneamente nos saldos do nó Anvil!
