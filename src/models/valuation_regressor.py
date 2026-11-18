"""
Asset Valuation Regressor: LightGBM, XGBoost & Stacking Ensemble Benchmark
Predicts rural land valuation from VTN, CAR, SRTM and NDVI features with Quantile Regression.
"""
from typing import Dict, Any, Tuple, Optional, List
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, cross_validate
from sklearn.metrics import r2_score, root_mean_squared_error, mean_absolute_error
from sklearn.ensemble import StackingRegressor, RandomForestRegressor
from sklearn.linear_model import RidgeCV
import lightgbm as lgb
import xgboost as xgb
from src.core.config import MODELS_DIR, settings


class ValuationModelEngine:
    """
    Motor de precificação patrimonial de imóveis rurais.
    Compara e treina LightGBM, XGBoost e Stacking Ensemble, oferecendo:
    1. Estimativa média e mediana (R$)
    2. Regressão Quantílica (Q10 Conservador, Q50 Mediana, Q90 Otimista)
    3. Validação Cruzada 5-Fold K-Fold
    """

    FEATURE_COLS = [
        "total_area_ha",
        "productive_area_ha",
        "productive_ratio",
        "vtn_reference_price_ha",
        "aptitude_score",
        "slope_mean_pct",
        "slope_max_pct",
        "elevation_mean_m",
        "mechanization_suitability_score",
        "compliance_score",
        "soil_organic_matter",
        "historical_ndvi_mean",
        "historical_ndvi_peak",
    ]

    TARGET_COL = "total_asset_value_brl"

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = models_dir or MODELS_DIR
        self.lgb_model: Optional[lgb.LGBMRegressor] = None
        self.xgb_model: Optional[xgb.XGBRegressor] = None
        self.stacking_model: Optional[StackingRegressor] = None
        
        # Modelos Quantílicos (Piso Conservador Q10 e Teto Q90)
        self.q10_model: Optional[lgb.LGBMRegressor] = None
        self.q50_model: Optional[lgb.LGBMRegressor] = None
        self.q90_model: Optional[lgb.LGBMRegressor] = None

        self.champion_model_name: str = "StackingEnsemble"
        self.benchmark_metrics: Dict[str, Dict[str, float]] = {}
        self.is_trained: bool = False

    def generate_synthetic_training_dataset(self, n_samples: int = 1500) -> pd.DataFrame:
        """
        Gera base de treinamento representativa com covariâncias realistas do agronegócio brasileiro
        (VTN Receita Federal, Declividade SRTM, Produtividade NDVI e Reserva Legal CAR).
        """
        np.random.seed(settings.random_state)
        
        total_area = np.random.uniform(200.0, 5000.0, n_samples)
        biome_prob = np.random.choice(["Cerrado", "Amazonia"], p=[0.65, 0.35], size=n_samples)
        
        req_res_ratio = np.where(biome_prob == "Amazonia", 0.80, 0.20)
        actual_res_ratio = req_res_ratio * np.random.uniform(0.70, 1.05, n_samples)
        compliance_score = np.clip(actual_res_ratio / req_res_ratio, 0.50, 1.00)
        
        productive_ratio = np.clip(1.0 - actual_res_ratio - np.random.uniform(0.03, 0.08, n_samples), 0.15, 0.85)
        productive_area = total_area * productive_ratio

        elevation = np.random.uniform(250.0, 950.0, n_samples)
        slope_mean = np.random.exponential(scale=4.5, size=n_samples) + 1.0
        slope_max = slope_mean * np.random.uniform(1.4, 2.2, n_samples)
        
        mech_suitability = np.clip(1.0 - (slope_mean / 22.0), 0.15, 1.0)
        aptitude_scores = np.random.choice([5.0, 4.0, 3.0, 2.0], p=[0.45, 0.30, 0.15, 0.10], size=n_samples)
        
        base_vtn = 65000.0 * (aptitude_scores / 5.0) * np.random.normal(1.0, 0.12, n_samples)
        vtn_ref = np.clip(base_vtn, 15000.0, 95000.0)

        hist_ndvi_mean = np.clip(0.60 + (aptitude_scores / 25.0) + np.random.normal(0, 0.04, n_samples), 0.40, 0.88)
        hist_ndvi_peak = np.clip(hist_ndvi_mean + np.random.uniform(0.08, 0.16, n_samples), 0.65, 0.95)
        
        soil_om = np.random.uniform(18.0, 48.0, n_samples)

        price_per_ha = (
            vtn_ref *
            (mech_suitability ** 0.45) *
            (compliance_score ** 0.30) *
            (hist_ndvi_peak / 0.85) *
            (1.0 + (soil_om - 30.0) * 0.005) *
            np.random.normal(1.0, 0.03, n_samples)
        )

        total_value = (productive_area * price_per_ha) + ((total_area - productive_area) * (vtn_ref * 0.18))

        df = pd.DataFrame({
            "total_area_ha": total_area,
            "productive_area_ha": productive_area,
            "productive_ratio": productive_ratio,
            "vtn_reference_price_ha": vtn_ref,
            "aptitude_score": aptitude_scores,
            "slope_mean_pct": slope_mean,
            "slope_max_pct": slope_max,
            "elevation_mean_m": elevation,
            "mechanization_suitability_score": mech_suitability,
            "compliance_score": compliance_score,
            "soil_organic_matter": soil_om,
            "historical_ndvi_mean": hist_ndvi_mean,
            "historical_ndvi_peak": hist_ndvi_peak,
            "price_per_ha": price_per_ha,
            "total_asset_value_brl": total_value,
        })
        return df

    def train_and_benchmark(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Treina e avalia LightGBM, XGBoost e Stacking Ensemble com 5-Fold CV.
        Também treina os regressores quantílicos Q10, Q50 e Q90.
        """
        if df is None:
            df = self.generate_synthetic_training_dataset(n_samples=1500)

        X = df[self.FEATURE_COLS]
        y = df[self.TARGET_COL]

        kf = KFold(n_splits=5, shuffle=True, random_state=settings.random_state)

        # 1. LightGBM
        self.lgb_model = lgb.LGBMRegressor(
            n_estimators=200,
            learning_rate=0.04,
            num_leaves=31,
            max_depth=6,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=settings.random_state,
            verbose=-1
        )

        # 2. XGBoost
        self.xgb_model = xgb.XGBRegressor(
            n_estimators=200,
            learning_rate=0.04,
            max_depth=5,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=settings.random_state,
            n_jobs=2
        )

        # 3. Stacking Ensemble
        estimators = [
            ('lgb', lgb.LGBMRegressor(n_estimators=100, learning_rate=0.05, num_leaves=25, verbose=-1, random_state=settings.random_state)),
            ('xgb', xgb.XGBRegressor(n_estimators=100, learning_rate=0.05, max_depth=4, random_state=settings.random_state, n_jobs=2))
        ]
        self.stacking_model = StackingRegressor(
            estimators=estimators,
            final_estimator=RidgeCV(),
            cv=3
        )

        # Cross Validation
        scoring = ["r2", "neg_root_mean_squared_error", "neg_mean_absolute_error"]
        lgb_cv = cross_validate(self.lgb_model, X, y, cv=kf, scoring=scoring)
        xgb_cv = cross_validate(self.xgb_model, X, y, cv=kf, scoring=scoring)
        stack_cv = cross_validate(self.stacking_model, X, y, cv=kf, scoring=scoring)

        self.benchmark_metrics = {
            "LightGBM": {
                "r2": float(np.mean(lgb_cv["test_r2"])),
                "rmse": float(-np.mean(lgb_cv["test_neg_root_mean_squared_error"])),
                "mae": float(-np.mean(lgb_cv["test_neg_mean_absolute_error"])),
            },
            "XGBoost": {
                "r2": float(np.mean(xgb_cv["test_r2"])),
                "rmse": float(-np.mean(xgb_cv["test_neg_root_mean_squared_error"])),
                "mae": float(-np.mean(xgb_cv["test_neg_mean_absolute_error"])),
            },
            "StackingEnsemble": {
                "r2": float(np.mean(stack_cv["test_r2"])),
                "rmse": float(-np.mean(stack_cv["test_neg_root_mean_squared_error"])),
                "mae": float(-np.mean(stack_cv["test_neg_mean_absolute_error"])),
            }
        }

        # Fit completo dos regressores principais
        self.lgb_model.fit(X, y)
        self.xgb_model.fit(X, y)
        self.stacking_model.fit(X, y)

        # 4. Treinar Regressores Quantílicos (LightGBM Quantile Objective)
        # Q10 (Piso de liquidação forçada / estresse)
        self.q10_model = lgb.LGBMRegressor(
            objective="quantile", alpha=0.10, n_estimators=150, learning_rate=0.05, verbose=-1, random_state=settings.random_state
        ).fit(X, y)

        # Q50 (Mediana)
        self.q50_model = lgb.LGBMRegressor(
            objective="quantile", alpha=0.50, n_estimators=150, learning_rate=0.05, verbose=-1, random_state=settings.random_state
        ).fit(X, y)

        # Q90 (Teto otimista)
        self.q90_model = lgb.LGBMRegressor(
            objective="quantile", alpha=0.90, n_estimators=150, learning_rate=0.05, verbose=-1, random_state=settings.random_state
        ).fit(X, y)

        # Seleção do modelo campeão
        best_name = min(
            self.benchmark_metrics.keys(),
            key=lambda k: self.benchmark_metrics[k]["rmse"]
        )
        self.champion_model_name = best_name
        self.is_trained = True

        return self.benchmark_metrics

    def predict_land_value(
        self,
        features: Dict[str, float],
        model_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa inferência de precificação do talhão, entregando estimativa pontual,
        intervalos de confiança e limites quantílicos (Q10, Q50, Q90).
        """
        if not self.is_trained:
            self.train_and_benchmark()

        model_name = model_choice or self.champion_model_name
        if model_name == "LightGBM":
            active_model = self.lgb_model
        elif model_name == "XGBoost":
            active_model = self.xgb_model
        else:
            active_model = self.stacking_model

        input_df = pd.DataFrame([{col: features.get(col, 0.0) for col in self.FEATURE_COLS}])
        
        predicted_val = float(active_model.predict(input_df)[0])

        # Previsões Quantílicas Rigorosas
        q10_val = float(self.q10_model.predict(input_df)[0])
        q50_val = float(self.q50_model.predict(input_df)[0])
        q90_val = float(self.q90_model.predict(input_df)[0])

        # Fallback de ordenação quantílica caso haja cruzamento pontual
        q10_val = min(q10_val, predicted_val)
        q90_val = max(q90_val, predicted_val)

        total_area = features.get("total_area_ha", 1.0)
        price_per_ha = predicted_val / total_area if total_area > 0 else 0.0

        return {
            "predicted_value": round(predicted_val, 2),
            "price_per_ha": round(price_per_ha, 2),
            "q10_conservative_floor": round(q10_val, 2),
            "q50_median": round(q50_val, 2),
            "q90_optimistic_cap": round(q90_val, 2),
            "ci_low": round(q10_val, 2),
            "ci_high": round(q90_val, 2),
            "model_used": model_name,
            "r2_benchmark": self.benchmark_metrics.get(model_name, {}).get("r2", 0.98),
            "rmse_benchmark": self.benchmark_metrics.get(model_name, {}).get("rmse", 6000000.0),
        }

    def get_feature_importances(self, model_name: str = "LightGBM") -> Dict[str, float]:
        if not self.is_trained:
            self.train_and_benchmark()
            
        if model_name == "XGBoost":
            importances = self.xgb_model.feature_importances_
        else:
            importances = self.lgb_model.feature_importances_

        total = float(np.sum(importances))
        normalized = (importances / total) * 100.0 if total > 0 else importances
        
        return {
            col: round(float(imp), 2)
            for col, imp in sorted(zip(self.FEATURE_COLS, normalized), key=lambda x: x[1], reverse=True)
        }
