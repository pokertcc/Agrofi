"""
Sentinel-2 NDVI Time-Series & Anomaly Detection Engine
Processes bi-weekly vegetative indices, phenology cycles and drought anomalies.
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
import numpy as np
from src.core.config import RAW_DATA_DIR, PROCESSED_DATA_DIR


class SentinelNDVIEngine:
    """
    Motor de processamento temporal de NDVI do Sentinel-2.
    Gera métricas fenológicas, z-scores e detecção estocástica de anomalias climáticas.
    """

    def __init__(self, timeseries_path: Optional[Path] = None):
        self.timeseries_path = timeseries_path or (RAW_DATA_DIR / "sentinel_ndvi_timeseries.csv")
        self.df: Optional[pd.DataFrame] = None

    def generate_benchmark_timeseries(self) -> pd.DataFrame:
        """
        Gera séries temporais quinzenais (15 dias) de NDVI para o período 2023 - 2026.
        Mimetiza o ciclo fenológico de Safra (Soja: Outubro a Fevereiro) e
        Safrinha (Milho/Algodão: Fevereiro a Junho) com variações sazonais realistas.
        """
        dates = pd.date_range(start="2023-09-01", end="2026-06-30", freq="15D")
        land_ids = ["TALHAO-MT-001", "TALHAO-GO-002", "TALHAO-MT-003", "TALHAO-BA-004"]

        records = []
        for land in land_ids:
            for d in dates:
                month = d.month
                day_of_year = d.dayofyear
                
                # Curva fenológica ideal da região Centro-Oeste
                # Safra de Soja (Pico em Dezembro/Janeiro: NDVI ~0.82 - 0.88)
                if month in [10, 11]:
                    base_ndvi = 0.40 + (month - 9) * 0.20
                elif month in [12, 1]:
                    base_ndvi = 0.84 + np.sin((d.day / 31.0) * np.pi) * 0.04
                elif month == 2:
                    base_ndvi = 0.70 # Maturação e colheita
                # Safrinha de Milho (Pico em Abril: NDVI ~0.78 - 0.82)
                elif month in [3, 4]:
                    base_ndvi = 0.65 + (month - 2) * 0.08
                elif month == 5:
                    base_ndvi = 0.55 # Senescência
                else:
                    base_ndvi = 0.28 # Entressafra / Pousio / Solo exposto
                
                # Ruído natural de sensoriamento e nuvens residuais
                noise = np.random.normal(0, 0.02)
                observed_ndvi = float(np.clip(base_ndvi + noise, 0.15, 0.92))
                
                records.append({
                    "land_id": land,
                    "date": d.strftime("%Y-%m-%d"),
                    "year": d.year,
                    "month": d.month,
                    "day_of_year": day_of_year,
                    "ndvi_observed": round(observed_ndvi, 4),
                    "cloud_cover_pct": round(float(np.random.uniform(2.0, 18.0)), 1)
                })

        df = pd.DataFrame(records)
        self.df = df
        return df

    def save_raw(self) -> Path:
        if self.df is None:
            self.generate_benchmark_timeseries()
        self.timeseries_path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(self.timeseries_path, index=False, encoding="utf-8")
        return self.timeseries_path

    def load_data(self) -> pd.DataFrame:
        if self.timeseries_path.exists():
            self.df = pd.read_csv(self.timeseries_path)
        else:
            self.generate_benchmark_timeseries()
            self.save_raw()
        return self.df

    def compute_phenology_and_anomalies(
        self,
        land_id: str,
        simulated_drought_shock_pct: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calcula as métricas fenológicas e anomalias de NDVI para um talhão.
        Permite simulação de estresse climático paramétrico (ex: seca com queda de até -50% no NDVI).
        """
        if self.df is None:
            self.load_data()

        land_series = self.df[self.df["land_id"] == land_id].copy()
        if land_series.empty:
            land_series = self.df[self.df["land_id"] == "TALHAO-MT-001"].copy()

        land_series["date"] = pd.to_datetime(land_series["date"])
        land_series = land_series.sort_values("date")

        # Aplica choque paramétrico na safra corrente (ano mais recente) se fornecido
        current_year = land_series["year"].max()
        if simulated_drought_shock_pct != 0.0:
            mask = (land_series["year"] == current_year) & (land_series["month"].isin([11, 12, 1, 2, 3, 4]))
            shock_factor = 1.0 + (simulated_drought_shock_pct / 100.0)
            land_series.loc[mask, "ndvi_observed"] = np.clip(
                land_series.loc[mask, "ndvi_observed"] * shock_factor, 0.15, 0.95
            )

        # Baseline histórico por quinzena (mês e quinzena)
        land_series["fortnight"] = (land_series["date"].dt.day > 15).astype(int) + 1
        historical_baseline = land_series.groupby(["month", "fortnight"])["ndvi_observed"].agg(["mean", "std"]).reset_index()
        historical_baseline["std"] = historical_baseline["std"].fillna(0.04).replace(0, 0.04)

        merged = pd.merge(
            land_series,
            historical_baseline,
            on=["month", "fortnight"],
            how="left",
            suffixes=("", "_hist")
        )

        merged["z_score"] = (merged["ndvi_observed"] - merged["mean"]) / merged["std"]

        # Métricas da Safra Corrente
        current_season = merged[merged["year"] == current_year]
        if current_season.empty:
            current_season = merged.tail(24)

        peak_ndvi = float(current_season["ndvi_observed"].max())
        mean_ndvi = float(current_season["ndvi_observed"].mean())
        min_zscore = float(current_season["z_score"].min())
        mean_zscore = float(current_season["z_score"].mean())

        # Detecção de anomalia de quebra de safra:
        # Z-scores severamente negativos durante a fase de floração/enchimento de grãos
        critical_window = current_season[current_season["month"].isin([12, 1, 3, 4])]
        critical_zscore = float(critical_window["z_score"].mean()) if not critical_window.empty else mean_zscore

        # Índice de Estresse Vegetativo (0.0 = Saudável/Vigoroso, 1.0 = Quebra Severa)
        # Z-score de 0 ou positivo -> stress = 0. Z-score de -3 -> stress = 1.0
        stress_index = float(np.clip(-critical_zscore / 2.5, 0.0, 1.0))

        return {
            "land_id": land_id,
            "current_year": int(current_year),
            "ndvi_peak": round(peak_ndvi, 3),
            "ndvi_mean": round(mean_ndvi, 3),
            "zscore_mean": round(mean_zscore, 2),
            "zscore_min": round(min_zscore, 2),
            "critical_window_zscore": round(critical_zscore, 2),
            "vegetative_stress_index": round(stress_index, 3),
            "timeseries_data": merged[["date", "ndvi_observed", "mean", "z_score"]].tail(36).to_dict(orient="records")
        }
