"""
AgroFi Web3 Bridge & API Integration Service
Implements the strict JSON Output Contract for Blockchain/Middleware consumption.
"""
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from src.core.schemas import Web3CollateralPayload, LandValuationResult, RiskAssessmentResult
from src.etl.vtn_ingestor import VTNIngestor
from src.etl.sicar_ingestor import SICARIngestor
from src.etl.srtm_processor import SRTMProcessor
from src.etl.sentinel_ndvi import SentinelNDVIEngine
from src.models.valuation_regressor import ValuationModelEngine
from src.models.risk_engine import CropRiskAndLTVEngine


class AgroFiOrchestrator:
    """
    Controlador central do AgroFi que conecta Ingestão (VTN, CAR, SRTM, Sentinel),
    Modelos Preditivos (LightGBM/XGBoost) e Motor de Risco/LTV.
    """

    def __init__(self):
        self.vtn_ingestor = VTNIngestor()
        self.sicar_ingestor = SICARIngestor()
        self.srtm_processor = SRTMProcessor()
        self.sentinel_engine = SentinelNDVIEngine()
        self.valuation_model = ValuationModelEngine()
        self.risk_engine = CropRiskAndLTVEngine()

        # Inicializa dados e modelos
        self.vtn_ingestor.load_data()
        self.sicar_ingestor.load_data()
        self.sentinel_engine.load_data()
        self.valuation_model.train_and_benchmark()

    def evaluate_land_full(
        self,
        land_id: str,
        simulated_drought_pct: float = 0.0,
        model_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa o pipeline completo para um imóvel rural e compõe todas as métricas analíticas.
        """
        parcel = self.sicar_ingestor.get_parcel(land_id)
        if not parcel:
            raise ValueError(f"Talhão/Imóvel '{land_id}' não encontrado no SICAR.")

        # Extração de Métricas Topográficas (SRTM)
        topo_metrics = self.srtm_processor.extract_topographic_metrics(land_id)

        # Extração de Fenologia e Anomalias (Sentinel-2 NDVI)
        ndvi_metrics = self.sentinel_engine.compute_phenology_and_anomalies(
            land_id=land_id,
            simulated_drought_shock_pct=simulated_drought_pct
        )

        # Preço VTN de Referência
        vtn_ref = self.vtn_ingestor.get_reference_price(
            municipality=parcel["municipality"],
            aptitude=parcel["aptitude"],
            year=2024
        )

        # Features para Valoração
        features = {
            "total_area_ha": parcel["total_area_ha"],
            "productive_area_ha": parcel["productive_area_ha"],
            "productive_ratio": parcel["productive_area_ha"] / parcel["total_area_ha"],
            "vtn_reference_price_ha": vtn_ref,
            "aptitude_score": 5.0 if "Boa" in parcel["aptitude"] else 4.0,
            "slope_mean_pct": topo_metrics["slope_mean_pct"],
            "slope_max_pct": topo_metrics["slope_max_pct"],
            "elevation_mean_m": topo_metrics["elevation_mean_m"],
            "mechanization_suitability_score": topo_metrics["mechanization_suitability_score"],
            "compliance_score": parcel["compliance_score"],
            "soil_organic_matter": 32.0,
            "historical_ndvi_mean": ndvi_metrics["ndvi_mean"],
            "historical_ndvi_peak": ndvi_metrics["ndvi_peak"],
        }

        # 1. Valoração Patrimonial
        val_result = self.valuation_model.predict_land_value(features, model_choice=model_choice)

        # 2. Motor de Risco e LTV Dinâmico
        risk_result = self.risk_engine.evaluate_risk(
            land_id=land_id,
            ndvi_stress_index=ndvi_metrics["vegetative_stress_index"],
            critical_window_zscore=ndvi_metrics["critical_window_zscore"],
            slope_mean_pct=topo_metrics["slope_mean_pct"],
            compliance_score=parcel["compliance_score"],
            soil_om=32.0,
            simulated_drought_severity=abs(simulated_drought_pct) if simulated_drought_pct < 0 else 0.0,
            total_land_value=val_result["predicted_value"]
        )

        # 3. Payload Estrito Web3
        web3_payload = Web3CollateralPayload(
            land_id=land_id,
            car_code=parcel["car_code"],
            predicted_value=float(val_result["predicted_value"]),
            ltv_ratio=float(risk_result.dynamic_ltv),
            health_factor=float(risk_result.health_factor)
        )

        return {
            "web3_contract_payload": web3_payload.model_dump(),
            "parcel_metadata": parcel,
            "topography": topo_metrics,
            "vegetation_ndvi": ndvi_metrics,
            "valuation": val_result,
            "risk_assessment": risk_result.model_dump(),
            "features_used": features
        }

    def get_web3_collateral_payload(
        self,
        land_id: str,
        simulated_drought_pct: float = 0.0
    ) -> Web3CollateralPayload:
        """
        Retorna estritamente o payload padronizado para o protocolo Web3/Smart Contract.
        """
        res = self.evaluate_land_full(land_id, simulated_drought_pct=simulated_drought_pct)
        return Web3CollateralPayload(**res["web3_contract_payload"])


# Criação da Aplicação FastAPI
app = FastAPI(
    title="AgroFi - Oráculo Geoespacial e Motor de Risco DeFi",
    description="API de Valoração Rural e LTV Dinâmico para Colateral RWA",
    version="1.0.0"
)

# Habilita CORS para permitir conexões web e dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton do orquestrador
orchestrator = AgroFiOrchestrator()

# Import tardio do keeper para evitar import circular
from src.api.oracle_keeper import oracle_keeper, OracleRelayTransaction


@app.get("/api/v1/health")
def health_check():
    return {"status": "healthy", "service": "AgroFi Core Engine"}


@app.get("/api/v1/parcels")
def list_parcels():
    gdf = orchestrator.sicar_ingestor.load_data()
    return gdf[["land_id", "car_code", "farm_name", "municipality", "state", "total_area_ha"]].to_dict(orient="records")


@app.get("/api/v1/valuation/{land_id}", response_model=Web3CollateralPayload)
def get_web3_valuation(
    land_id: str,
    drought_stress_pct: float = Query(0.0, ge=-70.0, le=30.0, description="Simulação paramétrica de estresse hídrico")
):
    """
    Retorna o payload padronizado estrito para integração Web3/Middleware.
    """
    try:
        return orchestrator.get_web3_collateral_payload(land_id, simulated_drought_pct=drought_stress_pct)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/vault/solidity-payload/{land_id}")
def get_solidity_vault_payload(
    land_id: str,
    token_id: int = Query(1, ge=1, description="ERC-721 Token ID do RWA rural"),
    drought_stress_pct: float = Query(0.0, ge=-70.0, le=30.0, description="Simulação paramétrica de estresse hídrico")
):
    """
    Retorna o payload serializado para envio direto ao smart contract AgroFiVault.sol:
    updateLandValuation(uint256 tokenId, string landId, string carCode, uint256 predictedValue, uint256 ltvRatioBps, uint256 healthFactor)
    """
    try:
        payload = orchestrator.get_web3_collateral_payload(land_id, simulated_drought_pct=drought_stress_pct)
        solidity_predicted_value = int(payload.predicted_value * 10**18)
        solidity_ltv_bps = int(round(payload.ltv_ratio * 10000))
        solidity_health_factor = int(round(payload.health_factor * 10**18))

        return {
            "contract": "AgroFiVault.sol",
            "function": "updateLandValuation",
            "abi_signature": "updateLandValuation(uint256,string,string,uint256,uint256,uint256)",
            "params": {
                "tokenId": token_id,
                "landId": payload.land_id,
                "carCode": payload.car_code,
                "predictedValueWei": str(solidity_predicted_value),
                "ltvRatioBps": solidity_ltv_bps,
                "healthFactorWei": str(solidity_health_factor)
            },
            "offchain_summary": {
                "predicted_value_brl": payload.predicted_value,
                "dynamic_ltv_pct": round(payload.ltv_ratio * 100, 2),
                "health_factor": round(payload.health_factor, 3),
                "is_liquidatable": payload.health_factor < 1.0
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/vault/simulate-loan/{land_id}")
def simulate_loan_position(
    land_id: str,
    requested_borrow_brl: float = Query(..., gt=0, description="Valor solicitado em empréstimo (R$)"),
    drought_stress_pct: float = Query(0.0, ge=-70.0, le=30.0, description="Simulação de estresse hídrico na safra")
):
    """
    Simula uma tomada de empréstimo contra o colateral RWA e valida a solvência no AgroFiVault.
    """
    try:
        full_eval = orchestrator.evaluate_land_full(land_id, simulated_drought_pct=drought_stress_pct)
        payload = full_eval["web3_contract_payload"]

        predicted_val = payload["predicted_value"]
        ltv = payload["ltv_ratio"]
        max_borrow = predicted_val * ltv

        is_borrow_approved = requested_borrow_brl <= max_borrow
        borrow_ratio = requested_borrow_brl / predicted_val if predicted_val > 0 else 1.0
        real_health_factor = ltv / borrow_ratio if borrow_ratio > 0 else 0.0
        is_liquidatable = real_health_factor < 1.0

        return {
            "land_id": land_id,
            "requested_borrow_brl": requested_borrow_brl,
            "max_borrow_allowed_brl": round(max_borrow, 2),
            "is_borrow_approved": is_borrow_approved,
            "current_borrow_ratio_pct": round(borrow_ratio * 100, 2),
            "dynamic_ltv_limit_pct": round(ltv * 100, 2),
            "simulated_health_factor": round(real_health_factor, 3),
            "status": "LIQUIDÁVEL (Parametric Liquidation Triggered)" if is_liquidatable else ("APROVADO" if is_borrow_approved else "RECUSADO (Excede LTV Máximo)")
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/analytics/monte-carlo/{land_id}")
def get_monte_carlo_stress(land_id: str, n_simulations: int = Query(5000, ge=100, le=10000)):
    """
    Executa simulação de Monte Carlo para estimar a distribuição estocástica de LTV sob choques climáticos.
    """
    try:
        n_sim = int(n_simulations.default if hasattr(n_simulations, 'default') else n_simulations)
        full_eval = orchestrator.evaluate_land_full(land_id)
        base_risk = full_eval["risk_assessment"]["crop_failure_probability"]
        total_val = full_eval["valuation"]["predicted_value"]
        mc_results = orchestrator.risk_engine.simulate_monte_carlo_distribution(
            base_risk_score=base_risk,
            total_land_value=total_val,
            n_simulations=n_sim
        )
        return {
            "land_id": land_id,
            "base_crop_risk": base_risk,
            "total_land_value": total_val,
            "monte_carlo_distribution": mc_results
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/analytics/comparison")
def get_parcels_comparison():
    """
    Retorna comparativo analítico de todos os imóveis cadastrados no SICAR com LTV, valor e risco.
    """
    parcels = orchestrator.sicar_ingestor.load_data()
    comparison = []
    for _, row in parcels.iterrows():
        try:
            eval_res = orchestrator.evaluate_land_full(row["land_id"])
            p_load = eval_res["web3_contract_payload"]
            comparison.append({
                "land_id": row["land_id"],
                "farm_name": row["farm_name"],
                "municipality": row["municipality"],
                "state": row["state"],
                "total_area_ha": row["total_area_ha"],
                "predicted_value": p_load["predicted_value"],
                "ltv_ratio": p_load["ltv_ratio"],
                "health_factor": p_load["health_factor"],
                "crop_failure_prob": eval_res["risk_assessment"]["crop_failure_probability"]
            })
        except Exception:
            continue
    return comparison


@app.get("/api/v1/oracle/keeper/status")
def get_oracle_keeper_status():
    """
    Retorna o status de monitoramento do Oracle Keeper e últimos heartbeats.
    """
    return oracle_keeper.get_keeper_status()


@app.post("/api/v1/oracle/keeper/sync-all", response_model=List[OracleRelayTransaction])
def sync_all_parcels(drought_stress_pct: float = Query(0.0, ge=-70.0, le=30.0)):
    """
    Dispara a sincronização de todos os imóveis cadastrados em lote para o oráculo.
    """
    return oracle_keeper.execute_all_parcels_sync(simulated_drought_pct=drought_stress_pct)


@app.post("/api/v1/oracle/keeper/relay/{land_id}", response_model=OracleRelayTransaction)
def relay_oracle_transaction(
    land_id: str,
    token_id: int = Query(1, ge=1, description="Token ID do NFT RWA no AgroFiVault"),
    drought_stress_pct: float = Query(0.0, ge=-70.0, le=30.0)
):
    """
    Simula e prepara a transação on-chain para a função updateLandValuation do AgroFiVault.sol.
    """
    try:
        return oracle_keeper.prepare_onchain_update(
            land_id=land_id,
            token_id=token_id,
            simulated_drought_pct=drought_stress_pct
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
