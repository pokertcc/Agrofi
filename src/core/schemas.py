"""
Pydantic Schemas and Data Transfer Objects for AgroFi
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


class AgriculturalAptitude(str, Enum):
    BOA = "Lavoura - Aptidão Boa"
    REGULAR = "Lavoura - Aptidão Regular"
    RESTRITA = "Lavoura - Aptidão Restrita"
    PASTAGEM_PLANTADA = "Pastagem Plantada"
    SILVICULTURA_PASTAGEM_NATURAL = "Silvicultura ou Pastagem Natural"
    PRESERVACAO = "Preservação da Fauna ou Flora"


class LandParcelInput(BaseModel):
    land_id: str = Field(..., description="Identificador único do talhão / imóvel")
    car_code: str = Field(..., description="Código do Cadastro Ambiental Rural (SICAR)")
    municipality: str = Field(..., description="Município do imóvel rural")
    state: str = Field("MT", description="Unidade Federativa (UF)")
    total_area_ha: float = Field(..., gt=0, description="Área total do imóvel em hectares")
    productive_area_ha: float = Field(..., gt=0, description="Área consolidada agricultável em hectares")
    legal_reserve_ha: float = Field(0.0, ge=0, description="Área de Reserva Legal em hectares")
    app_ha: float = Field(0.0, ge=0, description="Área de Preservação Permanente em hectares")
    aptitude: AgriculturalAptitude = Field(AgriculturalAptitude.BOA, description="Classificação de Aptidão Agrícola")
    slope_mean_pct: float = Field(..., ge=0, description="Declividade média do relevo em percentual (%)")
    elevation_mean_m: float = Field(..., ge=0, description="Altitude média em metros")
    soil_organic_matter_g_dm3: float = Field(30.0, description="Teor médio de matéria orgânica do solo")
    historical_ndvi_mean: float = Field(0.72, ge=0, le=1.0, description="Média histórica do NDVI na safra")
    historical_ndvi_peak: float = Field(0.85, ge=0, le=1.0, description="Pico vegetativo histórico do NDVI")


class ValuationMetrics(BaseModel):
    r2_score: float
    rmse: float
    mae: float
    selected_model: str


class LandValuationResult(BaseModel):
    land_id: str
    car_code: str
    total_area_ha: float
    productive_area_ha: float
    price_per_ha: float
    predicted_value: float
    confidence_interval_low: float
    confidence_interval_high: float
    model_name: str
    features_used: Dict[str, float]


class RiskAssessmentResult(BaseModel):
    land_id: str
    crop_failure_probability: float = Field(..., ge=0.0, le=1.0)
    ndvi_anomaly_zscore: float
    climate_stress_index: float
    slope_risk_penalty: float
    environmental_compliance_score: float
    dynamic_ltv: float = Field(..., ge=0.35, le=0.65, description="Margem dinâmica de LTV entre 35% e 65%")
    health_factor: float = Field(..., ge=0.0, description="Fator de saúde do colateral")


class Web3CollateralPayload(BaseModel):
    """
    Contrato estrito de saída para o middleware Web3 / Smart Contract DeFi.
    """
    land_id: str
    car_code: str
    predicted_value: float
    ltv_ratio: float
    health_factor: float

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "land_id": "TALHAO-MT-001",
                "car_code": "MT-5107925-8A4F1D9C3E2B4A1F8C2D3E4F5A6B7C8D",
                "predicted_value": 45200000.0,
                "ltv_ratio": 0.58,
                "health_factor": 1.45
            }
        }
    )
