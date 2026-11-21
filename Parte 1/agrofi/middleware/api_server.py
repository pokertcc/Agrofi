import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from middleware.web3_client import AgroFiWeb3Client
from middleware.oracle_service import AgroRiskOracle, AgroRiskData
from middleware.config import ACCOUNTS

app = FastAPI(
    title="AgroFi Protocol - Gateway de Integração Web3",
    description="API REST de conexão entre a Camada de Dados Agronômica (Parte 1) e os Contratos Inteligentes Web3 (Parte 2).",
    version="1.0.0"
)

# Shared Web3 Client & Oracle
client = AgroFiWeb3Client()
oracle = AgroRiskOracle(client)

# ==========================================
# PYDANTIC SCHEMAS (Modelos de Entrada)
# ==========================================

class MintCollateralRequest(BaseModel):
    to: str = Field(default=ACCOUNTS["farmer"]["address"], description="Endereço da carteira do produtor rural")
    token_uri: str = Field(default="ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi", description="URI dos metadados da safra (IPFS)")
    appraisal_value: int = Field(default=100_000 * 10**6, description="Avaliação da safra em micro-USDC (6 decimais: 100,000 * 1e6)")

class UpdateRiskRequest(BaseModel):
    token_id: int = Field(default=1, description="ID do token AgroNFT")
    ltv: int = Field(default=6000, description="Loan-To-Value em basis points (6000 = 60.00%)")
    health_factor: int = Field(default=15000, description="Fator de Saúde escalado em 1e4 (15000 = 1.50x; limite = 10000 = 1.00x)")

class BorrowRequest(BaseModel):
    token_id: int = Field(default=1, description="ID do token AgroNFT colateralizado")
    amount: int = Field(default=50_000 * 10**6, description="Valor do empréstimo em micro-USDC (6 decimais)")

class EvaluateAndPushRiskRequest(BaseModel):
    token_id: int = Field(default=1, description="ID do token AgroNFT")
    ndvi: float = Field(default=0.80, ge=0.0, le=1.0, description="Índice Vegetativo de Satélite (0.0 a 1.0)")
    precipitation_deficit: float = Field(default=0.0, ge=-1.0, le=1.0, description="Déficit de chuva (-1.0 = -100%, +0.5 = +50%)")
    soil_moisture: float = Field(default=60.0, ge=0.0, le=100.0, description="Umidade do solo em porcentagem (0% a 100%)")
    commodity_price_ratio: float = Field(default=1.0, gt=0.0, description="Razão de preço da commodity em relação à base")

# ==========================================
# ENDPOINTS (Interface da Camada Agro)
# ==========================================

@app.get("/")
def read_root():
    return {
        "protocol": "AgroFi Protocol Web3 Gateway",
        "status": "Online",
        "contracts": client.addresses,
        "docs": "/docs"
    }

@app.post("/api/mint-collateral", summary="1. Tokenizar Safra Agrícola (mintCollateral)")
def mint_collateral_endpoint(req: MintCollateralRequest):
    """
    Consome o input da camada agronômica para emitir o NFT representativo da safra / direito de uso.
    """
    try:
        token_id = client.mintCollateral(
            to=req.to,
            token_uri=req.token_uri,
            appraisal_value=req.appraisal_value
        )
        return {
            "status": "success",
            "token_id": token_id,
            "owner": req.to,
            "appraisal_value_usdc": req.appraisal_value / 10**6
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/update-risk", summary="2. Atualizar Parâmetros de Risco (updateLTVAndHealthFactor)")
def update_risk_endpoint(req: UpdateRiskRequest):
    """
    Atualiza o LTV e o Health Factor do colateral diretamente no smart contract.
    """
    try:
        tx_hash = client.updateLTVAndHealthFactor(
            token_id=req.token_id,
            ltv=req.ltv,
            health_factor=req.health_factor
        )
        return {
            "status": "success",
            "token_id": req.token_id,
            "ltv_percent": req.ltv / 100,
            "health_factor": req.health_factor / 10000,
            "tx_hash": tx_hash
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/borrow", summary="3. Executar Empréstimo em Stablecoin (borrow)")
def borrow_endpoint(req: BorrowRequest):
    """
    Libera empréstimo em USDC contra o AgroNFT depositado na LendingPool.
    """
    try:
        tx_hash = client.borrow(
            token_id=req.token_id,
            amount=req.amount
        )
        return {
            "status": "success",
            "token_id": req.token_id,
            "amount_borrowed_usdc": req.amount / 10**6,
            "tx_hash": tx_hash
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/risk/evaluate-and-push", summary="Calcular e Injetar Risco Agronômico (NDVI/Clima)")
def evaluate_and_push_risk_endpoint(req: EvaluateAndPushRiskRequest):
    """
    Recebe telemetria agronômica bruta da Parte 1, calcula os fatores de risco e submete a transação on-chain automaticamente.
    """
    try:
        data = AgroRiskData(
            ndvi=req.ndvi,
            precipitation_deficit=req.precipitation_deficit,
            soil_moisture=req.soil_moisture,
            commodity_price_ratio=req.commodity_price_ratio
        )
        tx_hash, ltv, hf = oracle.push_risk_update(req.token_id, data)
        return {
            "status": "success",
            "token_id": req.token_id,
            "calculated_ltv_percent": ltv / 100,
            "calculated_health_factor": hf / 10000,
            "tx_hash": tx_hash
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/collateral/{token_id}", summary="Consultar Colateral AgroNFT")
def get_collateral_endpoint(token_id: int):
    try:
        data = client.agro_nft.functions.getCollateralData(token_id).call()
        owner = client.agro_nft.functions.ownerOf(token_id).call()
        return {
            "token_id": token_id,
            "owner": owner,
            "appraisal_value_usdc": data[0] / 10**6,
            "ltv_percent": data[1] / 100,
            "health_factor": data[2] / 10000,
            "is_collateralized": data[3],
            "minted_at": data[4]
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/pool-status", summary="Consultar Status da LendingPool")
def get_pool_status_endpoint():
    try:
        available = client.pool.functions.availableLiquidity().call()
        total_borrowed = client.pool.functions.totalBorrowedAmount().call()
        return {
            "available_liquidity_usdc": available / 10**6,
            "total_borrowed_usdc": total_borrowed / 10**6,
            "contracts": client.addresses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
