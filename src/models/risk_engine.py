"""
AgroFi Risk Engine & Stochastic Dynamic LTV (35% - 65%)
Computes crop failure risk, parametric drought shock, Monte Carlo VaR (95%/99%) and Web3 Health Factor.
"""
from typing import Dict, Any, Optional, List
import numpy as np
from src.core.config import settings
from src.core.schemas import RiskAssessmentResult


class CropRiskAndLTVEngine:
    """
    Motor Estocástico de Análise de Risco Agronômico e LTV Dinâmico.
    Ajusta dinamicamente a margem de colateral seguro entre 35% e 65%
    e calcula o Health Factor e Métricas de VaR (Value at Risk) para DeFi RWA.
    """

    def __init__(
        self,
        min_ltv: float = 0.35,
        max_ltv: float = 0.65,
        target_borrowed_ltv: float = 0.50
    ):
        self.min_ltv = min_ltv # 35%
        self.max_ltv = max_ltv # 65%
        self.target_borrowed_ltv = target_borrowed_ltv # 50% baseline

    def evaluate_risk(
        self,
        land_id: str,
        ndvi_stress_index: float,
        critical_window_zscore: float,
        slope_mean_pct: float,
        compliance_score: float,
        soil_om: float = 30.0,
        simulated_drought_severity: float = 0.0,
        borrowed_amount: Optional[float] = None,
        total_land_value: Optional[float] = None,
        enso_phase: str = "Neutral" # "El_Nino", "La_Nina", "Neutral"
    ) -> RiskAssessmentResult:
        """
        Calcula o risco ponderado de quebra de safra e o LTV dinâmico estritamente no intervalo [0.35, 0.65].
        
        Pesos do Risco:
        - 50%: Anomalia e estresse de NDVI no período reprodutivo crítico
        - 20%: Vulnerabilidade topográfica / declividade (erosão e escoamento hídrico)
        - 20%: Conformidade ambiental (reserva legal / APP no CAR)
        - 10%: Matéria orgânica do solo (resiliência hídrica)
        """
        # Ajuste por fase climática ENSO (La Niña aumenta risco de veranico no Centro-Sul)
        enso_penalty = 0.08 if enso_phase == "La_Nina" else (0.05 if enso_phase == "El_Nino" else 0.0)

        # 1. Risco Climático / NDVI
        effective_ndvi_stress = np.clip(
            ndvi_stress_index + (simulated_drought_severity / 100.0) * 0.85 + enso_penalty,
            0.0, 1.0
        )
        
        # 2. Risco Topográfico (declividade > 8% aumenta risco de perda e erosão)
        slope_risk = np.clip((slope_mean_pct - 2.0) / 18.0, 0.0, 1.0)

        # 3. Risco Ambiental (déficit de reserva legal gera risco de embargo)
        environmental_risk = np.clip(1.0 - compliance_score, 0.0, 1.0)

        # 4. Resiliência do Solo (Solos com baixa matéria orgânica retêm menos água)
        soil_vulnerability = np.clip((40.0 - soil_om) / 30.0, 0.0, 1.0)

        # Risco Composto de Quebra de Safra (0.0 a 1.0)
        crop_risk_score = (
            (0.50 * effective_ndvi_stress) +
            (0.20 * slope_risk) +
            (0.20 * environmental_risk) +
            (0.10 * soil_vulnerability)
        )
        crop_risk_score = float(np.clip(crop_risk_score, 0.0, 1.0))

        # 5. Cálculo Estocástico do LTV Dinâmico
        dynamic_ltv = self.max_ltv - (self.max_ltv - self.min_ltv) * crop_risk_score
        dynamic_ltv = float(np.clip(dynamic_ltv, self.min_ltv, self.max_ltv))

        # 6. Cálculo do Health Factor (HF)
        if borrowed_amount is not None and total_land_value is not None and total_land_value > 0 and borrowed_amount > 0:
            current_borrow_ratio = borrowed_amount / total_land_value
            health_factor = dynamic_ltv / current_borrow_ratio
        else:
            health_factor = dynamic_ltv / self.target_borrowed_ltv

        return RiskAssessmentResult(
            land_id=land_id,
            crop_failure_probability=round(crop_risk_score, 3),
            ndvi_anomaly_zscore=round(critical_window_zscore, 2),
            climate_stress_index=round(effective_ndvi_stress, 3),
            slope_risk_penalty=round(slope_risk, 3),
            environmental_compliance_score=round(compliance_score, 3),
            dynamic_ltv=round(dynamic_ltv, 4),
            health_factor=round(float(health_factor), 3)
        )

    def simulate_monte_carlo_distribution(
        self,
        base_risk_score: float,
        total_land_value: float,
        n_simulations: int = 5000
    ) -> Dict[str, Any]:
        """
        Executa simulação de Monte Carlo com 5.000 iterações avaliando:
        - Value-at-Risk (VaR 95% e 99%)
        - Expected Shortfall / Conditional VaR (CVaR 95%)
        - Distribuição de LTV e capacidade de empréstimo segura
        """
        if hasattr(n_simulations, 'default'):
            n_simulations = int(n_simulations.default)
        else:
            n_simulations = int(n_simulations)

        np.random.seed(settings.random_state)
        
        # Choque estocástico beta assimétrico (representa estiagens assimétricas)
        shocks = np.random.beta(a=2.0, b=5.0, size=n_simulations) - 0.285
        simulated_risks = np.clip(base_risk_score + shocks, 0.0, 1.0)
        
        # Simulação de LTV correspondente
        simulated_ltvs = np.clip(
            self.max_ltv - (self.max_ltv - self.min_ltv) * simulated_risks,
            self.min_ltv,
            self.max_ltv
        )

        # Capacidade de crédito simulada (R$)
        simulated_borrow_capacity = simulated_ltvs * total_land_value
        nominal_capacity = (self.max_ltv - (self.max_ltv - self.min_ltv) * base_risk_score) * total_land_value

        # Quedas de capacidade em relação à média esperada
        drawdowns = np.maximum(0.0, nominal_capacity - simulated_borrow_capacity)

        # VaR 95% e VaR 99%
        var_95 = float(np.percentile(drawdowns, 95))
        var_99 = float(np.percentile(drawdowns, 99))

        # Conditional VaR (Média das perdas acima do percentil 95%)
        tail_losses = drawdowns[drawdowns >= var_95]
        cvar_95 = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_95

        return {
            "n_simulations": n_simulations,
            "nominal_borrow_capacity_brl": round(nominal_capacity, 2),
            "p10_conservative_ltv": round(float(np.percentile(simulated_ltvs, 10)), 4),
            "p50_median_ltv": round(float(np.percentile(simulated_ltvs, 50)), 4),
            "p90_optimistic_ltv": round(float(np.percentile(simulated_ltvs, 90)), 4),
            "var_95_drawdown_brl": round(var_95, 2),
            "var_99_drawdown_brl": round(var_99, 2),
            "cvar_95_expected_shortfall_brl": round(cvar_95, 2),
            "simulated_ltv_sample": [round(float(v), 4) for v in simulated_ltvs[:100]] # Amostra para gráficos
        }

    def simulate_monte_carlo_drawdown(
        self,
        base_risk_score: float,
        n_simulations: int = 1000,
        total_land_value: float = 50_000_000.0
    ) -> Dict[str, Any]:
        """Alias retrocompatível para simulate_monte_carlo_distribution."""
        return self.simulate_monte_carlo_distribution(
            base_risk_score=base_risk_score,
            total_land_value=total_land_value,
            n_simulations=n_simulations
        )
