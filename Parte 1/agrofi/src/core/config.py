"""
AgroFi Core Configuration Module
"""
from pathlib import Path
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models_store"


class AgroFiSettings(BaseModel):
    app_name: str = "AgroFi - Módulo Agro, Data Science & Visualização"
    version: str = "1.0.0"
    
    # Financial & Risk Parameters
    min_ltv: float = Field(0.35, description="Margem mínima de empréstimo (35%)")
    max_ltv: float = Field(0.65, description="Margem máxima segura de empréstimo (65%)")
    baseline_borrowed_ltv: float = Field(0.50, description="Nível de alavancagem de referência para cálculo do Health Factor")
    liquidation_threshold: float = Field(0.80, description="Limiar de liquidação em protocolo DeFi")
    
    # Random Seed
    random_state: int = 42


settings = AgroFiSettings()
