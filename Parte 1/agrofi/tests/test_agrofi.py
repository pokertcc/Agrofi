"""
AgroFi Comprehensive Test Suite
Validates ETL pipelines, ML regressors, Risk Engine bounds (35% - 65%) and Web3 Contract.
"""
import pytest
import numpy as np
from src.core.schemas import Web3CollateralPayload
from src.etl.vtn_ingestor import VTNIngestor
from src.etl.sicar_ingestor import SICARIngestor
from src.etl.srtm_processor import SRTMProcessor
from src.etl.sentinel_ndvi import SentinelNDVIEngine
from src.models.valuation_regressor import ValuationModelEngine
from src.models.risk_engine import CropRiskAndLTVEngine
from src.api.service import AgroFiOrchestrator


def test_vtn_ingestor():
    ingestor = VTNIngestor()
    df = ingestor.load_data()
    assert not df.empty
    assert "vtn_preco_ha" in df.columns
    assert "aptidao" in df.columns
    
    price_sorriso = ingestor.get_reference_price("Sorriso", "Lavoura - Aptidão Boa", 2024)
    assert price_sorriso > 50000.0


def test_sicar_ingestor():
    sicar = SICARIngestor()
    gdf = sicar.load_data()
    assert not gdf.empty
    assert "land_id" in gdf.columns
    assert "geometry" in gdf.columns
    
    parcel = sicar.get_parcel("TALHAO-MT-001")
    assert parcel is not None
    assert parcel["municipality"] == "Sorriso"
    assert parcel["productive_area_ha"] > 0
    assert 0.0 <= parcel["compliance_score"] <= 1.0


def test_srtm_processor():
    srtm = SRTMProcessor()
    metrics = srtm.extract_topographic_metrics("TALHAO-MT-001")
    assert "slope_mean_pct" in metrics
    assert "mechanization_suitability_score" in metrics
    assert metrics["slope_mean_pct"] >= 0.0
    assert 0.0 <= metrics["mechanization_suitability_score"] <= 1.0


def test_sentinel_ndvi_engine():
    ndvi_engine = SentinelNDVIEngine()
    df = ndvi_engine.load_data()
    assert not df.empty
    assert "ndvi_observed" in df.columns

    res = ndvi_engine.compute_phenology_and_anomalies("TALHAO-MT-001", simulated_drought_shock_pct=0.0)
    assert 0.0 <= res["ndvi_peak"] <= 1.0
    assert "vegetative_stress_index" in res
    assert 0.0 <= res["vegetative_stress_index"] <= 1.0

    # Teste de seca simulada
    res_drought = ndvi_engine.compute_phenology_and_anomalies("TALHAO-MT-001", simulated_drought_shock_pct=-35.0)
    assert res_drought["vegetative_stress_index"] >= res["vegetative_stress_index"]


def test_valuation_regressor_benchmark():
    engine = ValuationModelEngine()
    metrics = engine.train_and_benchmark()
    assert "LightGBM" in metrics
    assert "XGBoost" in metrics
    assert metrics["LightGBM"]["r2"] > 0.85
    assert metrics["XGBoost"]["r2"] > 0.85

    features = {
        "total_area_ha": 1500.0,
        "productive_area_ha": 1200.0,
        "productive_ratio": 0.80,
        "vtn_reference_price_ha": 65000.0,
        "aptitude_score": 5.0,
        "slope_mean_pct": 3.2,
        "slope_max_pct": 5.8,
        "elevation_mean_m": 420.0,
        "mechanization_suitability_score": 0.95,
        "compliance_score": 0.90,
        "soil_organic_matter": 32.0,
        "historical_ndvi_mean": 0.75,
        "historical_ndvi_peak": 0.86,
    }

    pred_lgb = engine.predict_land_value(features, model_choice="LightGBM")
    pred_xgb = engine.predict_land_value(features, model_choice="XGBoost")

    assert pred_lgb["predicted_value"] > 0
    assert pred_xgb["predicted_value"] > 0
    assert pred_lgb["ci_low"] < pred_lgb["predicted_value"] < pred_lgb["ci_high"]


def test_risk_engine_ltv_bounds():
    risk_engine = CropRiskAndLTVEngine()

    # Cenário 1: Condição Ideal (Risco Mínimo) -> LTV deve aproximar 65% (0.65)
    best_case = risk_engine.evaluate_risk(
        land_id="TEST-001",
        ndvi_stress_index=0.0,
        critical_window_zscore=1.5,
        slope_mean_pct=1.5,
        compliance_score=1.0,
        soil_om=38.0,
        simulated_drought_severity=0.0
    )
    assert 0.35 <= best_case.dynamic_ltv <= 0.65
    assert best_case.dynamic_ltv >= 0.60
    assert best_case.health_factor > 1.20

    # Cenário 2: Condição Extrema (Seca Catastrófica + Alta Declividade) -> LTV deve contrair próximo ao piso de 35%
    worst_case = risk_engine.evaluate_risk(
        land_id="TEST-002",
        ndvi_stress_index=1.0,
        critical_window_zscore=-3.5,
        slope_mean_pct=25.0,
        compliance_score=0.2,
        soil_om=15.0,
        simulated_drought_severity=100.0
    )
    assert 0.35 <= worst_case.dynamic_ltv <= 0.38
    assert worst_case.health_factor < 1.0

    # Cenário 3: Colapso Total (Risco 100%) -> LTV atinge exatamente o piso mínimo de 35% (0.35)
    catastrophic_case = risk_engine.evaluate_risk(
        land_id="TEST-003",
        ndvi_stress_index=1.0,
        critical_window_zscore=-4.0,
        slope_mean_pct=30.0,
        compliance_score=0.0,
        soil_om=5.0,
        simulated_drought_severity=100.0
    )
    assert catastrophic_case.dynamic_ltv == 0.35
    assert catastrophic_case.crop_failure_probability == 1.0


def test_web3_output_contract():
    orchestrator = AgroFiOrchestrator()
    payload = orchestrator.get_web3_collateral_payload("TALHAO-MT-001", simulated_drought_pct=0.0)

    # Verificação estrita do modelo Pydantic
    assert isinstance(payload, Web3CollateralPayload)
    
    # Verificação do dicionário serializado
    data = payload.model_dump()
    assert set(data.keys()) == {"land_id", "car_code", "predicted_value", "ltv_ratio", "health_factor"}
    assert isinstance(data["land_id"], str)
    assert isinstance(data["car_code"], str)
    assert isinstance(data["predicted_value"], float)
    assert isinstance(data["ltv_ratio"], float)
    assert isinstance(data["health_factor"], float)
    assert 0.35 <= data["ltv_ratio"] <= 0.65


def test_stacking_and_quantiles():
    engine = ValuationModelEngine()
    metrics = engine.train_and_benchmark()
    assert "StackingEnsemble" in metrics
    assert metrics["StackingEnsemble"]["r2"] > 0.85

    features = {
        "total_area_ha": 1850.0,
        "productive_area_ha": 1420.0,
        "productive_ratio": 1420.0 / 1850.0,
        "vtn_reference_price_ha": 68000.0,
        "aptitude_score": 5.0,
        "slope_mean_pct": 1.88,
        "slope_max_pct": 3.4,
        "elevation_mean_m": 385.0,
        "mechanization_suitability_score": 1.0,
        "compliance_score": 0.85,
        "soil_organic_matter": 32.0,
        "historical_ndvi_mean": 0.74,
        "historical_ndvi_peak": 0.86,
    }

    pred_stack = engine.predict_land_value(features, model_choice="StackingEnsemble")
    assert pred_stack["predicted_value"] > 0
    assert pred_stack["q10_conservative_floor"] <= pred_stack["q90_optimistic_cap"]
    assert pred_stack["q10_conservative_floor"] <= pred_stack["predicted_value"]


def test_monte_carlo_var_distribution():
    risk_engine = CropRiskAndLTVEngine()
    mc_results = risk_engine.simulate_monte_carlo_distribution(
        base_risk_score=0.25,
        total_land_value=90_000_000.0,
        n_simulations=1000
    )
    assert "var_95_drawdown_brl" in mc_results
    assert "cvar_95_expected_shortfall_brl" in mc_results
    assert mc_results["var_95_drawdown_brl"] >= 0
    assert mc_results["cvar_95_expected_shortfall_brl"] >= mc_results["var_95_drawdown_brl"]
    assert 0.35 <= mc_results["p10_conservative_ltv"] <= 0.65


def test_oracle_keeper_service():
    from src.api.oracle_keeper import oracle_keeper
    tx = oracle_keeper.prepare_onchain_update("TALHAO-MT-001", token_id=1, simulated_drought_pct=0.0)
    assert tx.token_id == 1
    assert tx.land_id == "TALHAO-MT-001"
    assert int(tx.predicted_value_wei) > 0
    assert 3500 <= tx.ltv_ratio_bps <= 6500
    assert tx.tx_status == "SIMULATED_SUCCESS"

