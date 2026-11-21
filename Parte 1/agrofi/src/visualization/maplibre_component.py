"""
MapLibre GL JS Interactive Component for Streamlit
Renders SICAR GeoJSON polygons, NDVI thematic layers, and interactive popups.
"""
import json
from typing import Dict, Any, Optional


def render_maplibre_html(
    geojson_data: Dict[str, Any],
    selected_land_id: Optional[str] = None,
    center_lon: float = -55.7250,
    center_lat: float = -12.5450,
    zoom: float = 12.0,
    height_px: int = 500
) -> str:
    """
    Gera o código HTML/JS completo para embutir um mapa interativo MapLibre GL JS
    com polígonos vetoriais do CAR, popup de informações e controles de navegação.
    """
    geojson_str = json.dumps(geojson_data)
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <title>AgroFi MapLibre GL JS Map</title>
        <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
        <!-- MapLibre GL JS CSS and JS -->
        <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
        <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
        <style>
            body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
            #map {{ position: absolute; top: 0; bottom: 0; width: 100%; height: {height_px}px; border-radius: 8px; }}
            .map-overlay {{
                position: absolute;
                top: 10px;
                left: 10px;
                background: rgba(255, 255, 255, 0.94);
                padding: 10px 14px;
                border-radius: 6px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.25);
                font-size: 12px;
                max-width: 250px;
                z-index: 1;
            }}
            .map-overlay h4 {{ margin: 0 0 6px 0; color: #1e293b; font-size: 14px; }}
            .legend-item {{ display: flex; align-items: center; margin-bottom: 4px; }}
            .legend-color {{ width: 14px; height: 14px; border-radius: 3px; margin-right: 8px; }}
            .basemap-switch {{ margin-top: 10px; padding-top: 8px; border-top: 1px solid #cbd5e1; font-weight: 600; }}
            .basemap-btn {{
                background: #f1f5f9; border: 1px solid #94a3b8; border-radius: 4px; padding: 3px 8px; font-size: 11px; cursor: pointer; margin-right: 4px; margin-top: 4px;
            }}
            .basemap-btn.active {{ background: #0284c7; color: #ffffff; border-color: #0369a1; }}
            .maplibregl-popup-content {{
                padding: 12px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                font-size: 13px;
                line-height: 1.4;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div class="map-overlay">
            <h4>Camadas Territoriais CAR</h4>
            <div class="legend-item">
                <div class="legend-color" style="background: rgba(16, 185, 129, 0.55); border: 1.5px solid #059669;"></div>
                <span>Área Consolidada / Lavoura</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: rgba(59, 130, 246, 0.2); border: 2px solid #2563eb;"></div>
                <span>Perímetro do Imóvel (CAR)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: rgba(13, 148, 136, 0.5); border: 1.5px solid #0f766e;"></div>
                <span>Reserva Legal / APP</span>
            </div>
            <div class="basemap-switch">
                <span>Modo de Exibição:</span><br/>
                <button type="button" class="basemap-btn active" id="btn-carto" onclick="switchBasemap('carto')">Mapa Vetorial</button>
                <button type="button" class="basemap-btn" id="btn-sat" onclick="switchBasemap('satellite')">Satélite RGB</button>
            </div>
        </div>

        <script>
            const geojsonData = {geojson_str};
            const selectedLandId = "{selected_land_id or ''}";

            const map = new maplibregl.Map({{
                container: 'map',
                style: {{
                    version: 8,
                    sources: {{
                        'carto-voyager': {{
                            type: 'raster',
                            tiles: [
                                'https://basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}@2x.png'
                            ],
                            tileSize: 256,
                            attribution: '&copy; OpenStreetMap contributors, &copy; CARTO'
                        }},
                        'esri-satellite': {{
                            type: 'raster',
                            tiles: [
                                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}'
                            ],
                            tileSize: 256,
                            attribution: '&copy; Esri, Maxar, Earthstar Geographics'
                        }}
                    }},
                    layers: [
                        {{
                            id: 'satellite-basemap',
                            type: 'raster',
                            source: 'esri-satellite',
                            layout: {{ 'visibility': 'none' }},
                            minzoom: 0,
                            maxzoom: 19
                        }},
                        {{
                            id: 'carto-basemap',
                            type: 'raster',
                            source: 'carto-voyager',
                            layout: {{ 'visibility': 'visible' }},
                            minzoom: 0,
                            maxzoom: 19
                        }}
                    ]
                }},
                center: [{center_lon}, {center_lat}],
                zoom: {zoom}
            }});

            map.addControl(new maplibregl.NavigationControl(), 'top-right');
            map.addControl(new maplibregl.FullscreenControl(), 'top-right');

            map.on('load', () => {{
                // Fonte GeoJSON do SICAR
                map.addSource('sicar-parcels', {{
                    type: 'geojson',
                    data: geojsonData
                }});

                // Camada de preenchimento dos polígonos
                map.addLayer({{
                    id: 'car-fill',
                    type: 'fill',
                    source: 'sicar-parcels',
                    paint: {{
                        'fill-color': [
                            'case',
                            ['==', ['get', 'land_id'], selectedLandId],
                            '#10b981',
                            '#3b82f6'
                        ],
                        'fill-opacity': 0.45
                    }}
                }});

                // Camada de contorno
                map.addLayer({{
                    id: 'car-line',
                    type: 'line',
                    source: 'sicar-parcels',
                    paint: {{
                        'line-color': [
                            'case',
                            ['==', ['get', 'land_id'], selectedLandId],
                            '#047857',
                            '#1d4ed8'
                        ],
                        'line-width': 2.5
                    }}
                }});

                // Ajustar visualização priorizando o talhão selecionado
                if (selectedLandId && geojsonData.features && geojsonData.features.length > 0) {{
                    const selectedFeature = geojsonData.features.find(f => f.properties && f.properties.land_id === selectedLandId);
                    if (selectedFeature && selectedFeature.geometry && selectedFeature.geometry.coordinates) {{
                        const bounds = new maplibregl.LngLatBounds();
                        const coords = selectedFeature.geometry.coordinates[0];
                        coords.forEach(coord => bounds.extend(coord));
                        map.fitBounds(bounds, {{ padding: 60, maxZoom: 14.5 }});
                    }}
                }} else if (geojsonData.features && geojsonData.features.length > 0) {{
                    const bounds = new maplibregl.LngLatBounds();
                    geojsonData.features.forEach(f => {{
                        if (f.geometry && f.geometry.coordinates) {{
                            const coords = f.geometry.coordinates[0];
                            coords.forEach(coord => bounds.extend(coord));
                        }}
                    }});
                    map.fitBounds(bounds, {{ padding: 40, maxZoom: 13.5 }});
                }}

                // Popup interativo no clique
                map.on('click', 'car-fill', (e) => {{
                    const props = e.features[0].properties;
                    const coords = e.lngLat;

                    new maplibregl.Popup()
                        .setLngLat(coords)
                        .setHTML(`
                            <strong>${{props.farm_name || 'Imóvel Rural'}}</strong><br/>
                            <span style="color:#64748b; font-size:11px;">CAR: ${{props.car_code || 'N/A'}}</span><br/>
                            <b>Município:</b> ${{props.municipality}} - ${{props.state}}<br/>
                            <b>Área Total:</b> ${{props.total_area_ha}} ha<br/>
                            <b>Área Produtiva:</b> ${{props.productive_area_ha}} ha<br/>
                            <b>Conformidade CAR:</b> ${{(props.compliance_score * 100).toFixed(1)}}%<br/>
                            <b>Aptidão:</b> ${{props.aptitude}}
                        `)
                        .addTo(map);
                }});

                // Cursor pointer ao passar o mouse
                map.on('mouseenter', 'car-fill', () => {{
                    map.getCanvas().style.cursor = 'pointer';
                }});
                map.on('mouseleave', 'car-fill', () => {{
                    map.getCanvas().style.cursor = '';
                }});
            }});

            function switchBasemap(mode) {{
                if (!map) return;
                const btnCarto = document.getElementById('btn-carto');
                const btnSat = document.getElementById('btn-sat');
                if (mode === 'satellite') {{
                    map.setLayoutProperty('satellite-basemap', 'visibility', 'visible');
                    map.setLayoutProperty('carto-basemap', 'visibility', 'none');
                    btnSat.classList.add('active');
                    btnCarto.classList.remove('active');
                }} else {{
                    map.setLayoutProperty('satellite-basemap', 'visibility', 'none');
                    map.setLayoutProperty('carto-basemap', 'visibility', 'visible');
                    btnCarto.classList.add('active');
                    btnSat.classList.remove('active');
                }}
            }}
        </script>
    </body>
    </html>
    """
    return html_code
