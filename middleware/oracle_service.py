import time
import math
from dataclasses import dataclass
from typing import Optional
from .web3_client import AgroFiWeb3Client
from .config import ACCOUNTS

@dataclass
class AgroRiskData:
    ndvi: float               # Normalized Difference Vegetation Index (0.0 to 1.0)
    precipitation_deficit: float # Percentage deficit compared to expected rainfall (-100% to +100%)
    soil_moisture: float      # Soil moisture percentage (0% to 100%)
    commodity_price_ratio: float # Current commodity spot price / baseline expected price (e.g. 1.05 = +5%)

class AgroRiskOracle:
    def __init__(self, client: Optional[AgroFiWeb3Client] = None):
        self.client = client or AgroFiWeb3Client()

    def evaluate_risk(self, data: AgroRiskData, appraisal_value: int, current_debt: int):
        """
        Calculates dynamic LTV and Health Factor from agro metrics.
        - Appraisal value: 6 decimals (e.g. 100,000 * 1e6)
        - Current debt: 6 decimals (e.g. 50,000 * 1e6)
        Returns (ltv_bps, health_factor_scaled)
        """
        # 1. Vegetation Vigor Score (0 - 100)
        # Optimal soybean/corn NDVI is around 0.75 - 0.85
        ndvi_clamped = max(0.0, min(1.0, data.ndvi))
        vigor_score = min(100.0, (ndvi_clamped / 0.80) * 100.0)

        # 2. Climate Stress Penalty
        # If precipitation deficit is severe (e.g. -50% rainfall), penalty applies
        climate_penalty = 0.0
        if data.precipitation_deficit < -0.20:
            climate_penalty += abs(data.precipitation_deficit) * 40.0
        if data.soil_moisture < 30.0:
            climate_penalty += (30.0 - data.soil_moisture) * 1.5

        # 3. Overall Agro Health Score (0 - 100)
        health_score = max(5.0, min(100.0, (vigor_score - climate_penalty) * data.commodity_price_ratio))

        # 4. Dynamic LTV (Basis Points)
        # Base healthy LTV is 65% (6500 bps), scaled down if health score decreases
        base_ltv = 6500
        ltv_bps = int(max(2000, min(7500, base_ltv * (health_score / 100.0))))

        # 5. Dynamic Health Factor calculation
        # Health Factor = (Adjusted Collateral Value * LTV) / Debt
        # Scaled by 10000 (10000 = 1.00x)
        if current_debt == 0:
            health_factor_scaled = 20000 # 2.00x (Solvent/No Debt)
        else:
            adjusted_collateral_value = appraisal_value * (health_score / 100.0)
            max_capacity = (adjusted_collateral_value * ltv_bps) / 10000
            hf = (max_capacity / current_debt)
            health_factor_scaled = int(hf * 10000)

        return ltv_bps, health_factor_scaled

    def push_risk_update(
        self,
        token_id: int,
        risk_data: Optional[AgroRiskData] = None,
        data: Optional[AgroRiskData] = None,
        oracle_private_key: str = ACCOUNTS["admin"]["private_key"]
    ):
        """
        Consumes agro risk data, computes parameters and publishes update on-chain.
        Accepts either risk_data or data for compatibility.
        """
        effective_data = data or risk_data
        if effective_data is None:
            raise ValueError("risk_data or data must be provided")
        risk_data = effective_data
        # Fetch current loan and collateral data
        col_data = self.client.agro_nft.functions.getCollateralData(token_id).call()
        appraisal_value = col_data[0]

        loan = self.client.pool.functions.getLoan(token_id).call()
        current_debt = loan[1]

        ltv_bps, health_factor_scaled = self.evaluate_risk(risk_data, appraisal_value, current_debt)

        print(f"[Oracle] Token ID {token_id} | NDVI: {risk_data.ndvi:.2f} | Rainfall Deficit: {risk_data.precipitation_deficit*100:.1f}%")
        print(f"[Oracle] Calculated LTV: {ltv_bps/100:.2f}% | Health Factor: {health_factor_scaled/10000:.2f}x")

        tx_hash = self.client.updateLTVAndHealthFactor(
            token_id=token_id,
            ltv=ltv_bps,
            health_factor=health_factor_scaled,
            sender_private_key=oracle_private_key
        )
        print(f"[Oracle] On-Chain Update Broadcasted! Tx: {tx_hash}")
        return tx_hash, ltv_bps, health_factor_scaled
