"""
SICAR (Cadastro Ambiental Rural) Ingestion & Geoprocessing Module
Using GeoPandas and Shapely for boundary, land use and compliance analysis.
"""
from typing import Dict, Any, List, Optional
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, mapping
from shapely.ops import transform
import pyproj
from src.core.config import RAW_DATA_DIR, PROCESSED_DATA_DIR


class SICARIngestor:
    """
    Processador espacial de cadastros ambientais rurais (SICAR).
    Lida com polígonos de Área do Imóvel, Área Consolidada, APP e Reserva Legal.
    """

    def __init__(self, geojson_path: Optional[Path] = None):
        self.geojson_path = geojson_path or (RAW_DATA_DIR / "sicar_car_polygons.geojson")
        self.gdf: Optional[gpd.GeoDataFrame] = None

    def generate_benchmark_car_features(self) -> gpd.GeoDataFrame:
        """
        Cria feições GeoJSON de imóveis rurais com geometrias vetoriais realistas
        no Mato Grosso (Sorriso, Sapezal) e Goiás (Rio Verde).
        Projeção WGS84 (EPSG:4326).
        """
        features = [
            {
                "land_id": "TALHAO-MT-001",
                "car_code": "MT-5107925-8A4F1D9C3E2B4A1F8C2D3E4F5A6B7C8D",
                "farm_name": "Fazenda Santa Helena",
                "municipality": "Sorriso",
                "state": "MT",
                "biome": "Amazônia",
                "legal_reserve_req_pct": 80.0,
                # Coordenadas aproximadas em Sorriso/MT (~ -12.54, -55.72)
                "center_lon": -55.7250,
                "center_lat": -12.5450,
                "delta_lon": 0.045, # ~5 km
                "delta_lat": 0.035,
                "total_area_ha": 1850.0,
                "productive_area_ha": 1420.0,
                "legal_reserve_ha": 330.0,
                "app_ha": 100.0,
                "aptitude": "Lavoura - Aptidão Boa"
            },
            {
                "land_id": "TALHAO-GO-002",
                "car_code": "GO-5218805-4B8C1D2E3F4A5B6C7D8E9F0A1B2C3D4E",
                "farm_name": "Fazenda Boa Esperança",
                "municipality": "Rio Verde",
                "state": "GO",
                "biome": "Cerrado",
                "legal_reserve_req_pct": 20.0,
                # Coordenadas em Rio Verde/GO (~ -17.79, -50.92)
                "center_lon": -50.9250,
                "center_lat": -17.7950,
                "delta_lon": 0.038,
                "delta_lat": 0.032,
                "total_area_ha": 1320.0,
                "productive_area_ha": 1040.0,
                "legal_reserve_ha": 210.0,
                "app_ha": 70.0,
                "aptitude": "Lavoura - Aptidão Boa"
            },
            {
                "land_id": "TALHAO-MT-003",
                "car_code": "MT-5107875-9C0D1E2F3A4B5C6D7E8F9A0B1C2D3E4F",
                "farm_name": "Agropecuária Chapadão",
                "municipality": "Sapezal",
                "state": "MT",
                "biome": "Cerrado",
                "legal_reserve_req_pct": 35.0,
                # Sapezal/MT (~ -13.55, -58.81)
                "center_lon": -58.8150,
                "center_lat": -13.5500,
                "delta_lon": 0.052,
                "delta_lat": 0.040,
                "total_area_ha": 2400.0,
                "productive_area_ha": 1520.0,
                "legal_reserve_ha": 740.0,
                "app_ha": 140.0,
                "aptitude": "Lavoura - Aptidão Boa"
            },
            {
                "land_id": "TALHAO-BA-004",
                "car_code": "BA-2919553-7A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D",
                "farm_name": "Fazenda Ouro Verde",
                "municipality": "Luís Eduardo Magalhães",
                "state": "BA",
                "biome": "Cerrado",
                "legal_reserve_req_pct": 20.0,
                # LEM/BA (~ -12.09, -45.79)
                "center_lon": -45.7950,
                "center_lat": -12.0950,
                "delta_lon": 0.040,
                "delta_lat": 0.035,
                "total_area_ha": 1600.0,
                "productive_area_ha": 1220.0,
                "legal_reserve_ha": 310.0,
                "app_ha": 70.0,
                "aptitude": "Lavoura - Aptidão Regular"
            }
        ]

        geoms = []
        rows = []

        for f in features:
            cx, cy = f["center_lon"], f["center_lat"]
            dx, dy = f["delta_lon"], f["delta_lat"]
            
            # Polígono do perímetro do imóvel
            coords = [
                (cx - dx/2, cy - dy/2),
                (cx + dx/2, cy - dy/2),
                (cx + dx/2 + 0.003, cy + dy/4),
                (cx + dx/2, cy + dy/2),
                (cx - dx/2, cy + dy/2),
                (cx - dx/2, cy - dy/2),
            ]
            poly = Polygon(coords)
            geoms.append(poly)
            
            # Cálculo de conformidade ambiental (Código Florestal)
            reserve_actual_pct = (f["legal_reserve_ha"] / f["total_area_ha"]) * 100
            reserve_deficit_pct = max(0.0, f["legal_reserve_req_pct"] - reserve_actual_pct)
            compliance_score = max(0.0, min(1.0, 1.0 - (reserve_deficit_pct / 50.0)))
            
            rows.append({
                "land_id": f["land_id"],
                "car_code": f["car_code"],
                "farm_name": f["farm_name"],
                "municipality": f["municipality"],
                "state": f["state"],
                "biome": f["biome"],
                "total_area_ha": f["total_area_ha"],
                "productive_area_ha": f["productive_area_ha"],
                "legal_reserve_ha": f["legal_reserve_ha"],
                "app_ha": f["app_ha"],
                "aptitude": f["aptitude"],
                "reserve_req_pct": f["legal_reserve_req_pct"],
                "reserve_actual_pct": round(reserve_actual_pct, 2),
                "reserve_deficit_pct": round(reserve_deficit_pct, 2),
                "compliance_score": round(compliance_score, 3),
                "centroid_lon": cx,
                "centroid_lat": cy
            })

        gdf = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326")
        self.gdf = gdf
        return gdf

    def save_raw(self) -> Path:
        if self.gdf is None:
            self.generate_benchmark_car_features()
        self.geojson_path.parent.mkdir(parents=True, exist_ok=True)
        self.gdf.to_file(self.geojson_path, driver="GeoJSON")
        return self.geojson_path

    def load_data(self) -> gpd.GeoDataFrame:
        if self.geojson_path.exists():
            self.gdf = gpd.read_file(self.geojson_path)
        else:
            self.generate_benchmark_car_features()
            self.save_raw()
        return self.gdf

    def get_parcel(self, land_id: str) -> Optional[Dict[str, Any]]:
        if self.gdf is None:
            self.load_data()
        subset = self.gdf[self.gdf["land_id"] == land_id]
        if subset.empty:
            return None
        row = subset.iloc[0]
        data = row.to_dict()
        if "geometry" in data and hasattr(data["geometry"], "__geo_interface__"):
            data["geometry"] = mapping(data["geometry"])
        return data

    def get_geojson_dict(self) -> Dict[str, Any]:
        """
        Retorna dicionário GeoJSON pronto para injeção no frontend MapLibre GL JS.
        """
        if self.gdf is None:
            self.load_data()
        return json.loads(self.gdf.to_json())
