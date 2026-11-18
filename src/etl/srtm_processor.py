"""
SRTM / DEM (Digital Elevation Model) & Topographic Slope Processor
Using Rasterio, NumPy and geospatial slope algorithms.
"""
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from src.core.config import RAW_DATA_DIR, PROCESSED_DATA_DIR


class SRTMProcessor:
    """
    Processador de Modelos Digitais de Elevação (DEM/SRTM) e cálculo de declividade.
    Avalia a aptidão mecânica para colheitadeiras e tratores agrícolas.
    """

    def __init__(self, raster_path: Optional[Path] = None):
        self.raster_path = raster_path or (RAW_DATA_DIR / "srtm_dem_sample.tif")

    def generate_benchmark_dem(
        self,
        base_elevation: float = 385.0,
        slope_tendency: float = 0.02, # 2% slope
        width: int = 150,
        height: int = 150,
        pixel_size_deg: float = 0.000277777777778, # ~30m resolution (SRTM 1 arc-second)
        west: float = -55.75,
        north: float = -12.52
    ) -> Path:
        """
        Gera um GeoTIFF sintético georreferenciado representativo de um platô agrícola
        em Mato Grosso (SRTM ~30m resolution).
        """
        x = np.linspace(0, 1, width)
        y = np.linspace(0, 1, height)
        xx, yy = np.meshgrid(x, y)

        # Superfície com ondulação suave e ruído natural
        surface = (
            base_elevation +
            (xx * slope_tendency * 1000) +
            (np.sin(yy * np.pi * 3) * 4.5) +
            (np.random.normal(0, 0.6, (height, width)))
        ).astype(np.float32)

        transform = from_origin(west, north, pixel_size_deg, pixel_size_deg)
        self.raster_path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(
            self.raster_path,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=surface.dtype,
            crs='EPSG:4326',
            transform=transform,
        ) as dst:
            dst.write(surface, 1)

        return self.raster_path

    def compute_slope_from_elevation(self, elevation_array: np.ndarray, cell_size_meters: float = 30.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calcula o gradiente topográfico e a declividade em graus e percentual (%)
        utilizando método de diferenças finitas (Horn / Fleming).
        """
        dy, dx = np.gradient(elevation_array, cell_size_meters, cell_size_meters)
        gradient = np.sqrt(dx**2 + dy**2)
        slope_deg = np.degrees(np.arctan(gradient))
        slope_pct = np.tan(np.radians(slope_deg)) * 100.0
        return slope_deg, slope_pct

    def extract_topographic_metrics(
        self,
        land_id: str,
        dem_file: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Extrai métricas topográficas e classifica a aptidão de mecanização agrícola:
        - 0% a 3%: Relevo Plano (Aptidão Máxima)
        - 3% a 8%: Suave Ondulado (Aptidão Alta)
        - 8% a 13%: Moderadamente Ondulado (Aptidão Moderada)
        - 13% a 20%: Ondulado (Aptidão Restrita)
        - > 20%: Forte Ondulado / Montanhoso (Inapto para grãos)
        """
        target_path = dem_file or self.raster_path
        if not target_path.exists():
            self.generate_benchmark_dem()

        with rasterio.open(target_path) as src:
            elevation = src.read(1)
            nodata = src.nodata
            if nodata is not None:
                elevation = np.where(elevation == nodata, np.nan, elevation)

        # Resolução média aproximada em metros para EPSG:4326 no Brasil equatorial/tropical
        cell_size_m = 30.8
        slope_deg, slope_pct = self.compute_slope_from_elevation(elevation, cell_size_meters=cell_size_m)

        mean_elevation = float(np.nanmean(elevation))
        std_elevation = float(np.nanstd(elevation))
        min_elevation = float(np.nanmin(elevation))
        max_elevation = float(np.nanmax(elevation))

        mean_slope_pct = float(np.nanmean(slope_pct))
        max_slope_pct = float(np.nanpercentile(slope_pct, 95))

        # Classificação Embrapa de mecanização
        if mean_slope_pct <= 3.0:
            relief_class = "Plano"
            suitability_score = 1.00
        elif mean_slope_pct <= 8.0:
            relief_class = "Suave Ondulado"
            suitability_score = 0.92
        elif mean_slope_pct <= 13.0:
            relief_class = "Moderadamente Ondulado"
            suitability_score = 0.75
        elif mean_slope_pct <= 20.0:
            relief_class = "Ondulado (Restrito)"
            suitability_score = 0.45
        else:
            relief_class = "Forte Ondulado (Inapto)"
            suitability_score = 0.15

        return {
            "land_id": land_id,
            "elevation_mean_m": round(mean_elevation, 1),
            "elevation_std_m": round(std_elevation, 1),
            "elevation_min_m": round(min_elevation, 1),
            "elevation_max_m": round(max_elevation, 1),
            "slope_mean_pct": round(mean_slope_pct, 2),
            "slope_max_pct": round(max_slope_pct, 2),
            "relief_classification": relief_class,
            "mechanization_suitability_score": round(suitability_score, 2),
        }
