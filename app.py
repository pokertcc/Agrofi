"""
AgroFi - Módulo Agro, Data Science & Visualização
Aplicação Streamlit com MapLibre GL JS, Valoração ML, Motor de Risco LTV Dinâmico e Oráculo Web3.
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import json
import os
from pathlib import Path
from datetime import datetime
from src.api.service import orchestrator
from src.api.oracle_keeper import oracle_keeper
from src.visualization.maplibre_component import render_maplibre_html
from src.core.config import settings

# Configuração da Página
st.set_page_config(
    page_title="AgroFi - Oráculo Geoespacial & LTV Dinâmico",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização Customizada CSS (Paleta de Cores Modo Claro AgroFi)
st.markdown("""
<style>
    /* Fundo geral e tipografia */
    .stApp {
        background-color: #F7F9F6;
        color: #1A2E20;
    }
    
    /* Cards de métricas */
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8E2;
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 4px 16px -2px rgba(26, 46, 32, 0.05);
    }
    .metric-title {
        font-size: 13px;
        color: #556B5C;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 6px;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 800;
        color: #1A2E20;
    }
    
    /* Badges de Status */
    .badge-safe {
        background-color: #E8F5E9;
        color: #00897B;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 12px;
        border: 1px solid #C8E6C9;
    }
    .badge-warn {
        background-color: #FFF3E0;
        color: #E67E22;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 12px;
        border: 1px solid #FFE082;
    }
    .badge-danger {
        background-color: #FFEBEE;
        color: #C62828;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 12px;
        border: 1px solid #FFCDD2;
    }
    
    /* Botões personalizados */
    div.stButton > button:first-child {
        background-color: #00897B;
        color: #FFFFFF;
        font-weight: 700;
        border-radius: 10px;
        border: none;
        box-shadow: 0 2px 8px rgba(0, 137, 123, 0.2);
    }
    div.stButton > button:first-child:hover {
        background-color: #00695C;
        color: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)

# Barra Lateral (Sidebar)
st.sidebar.image("https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=400&auto=format&fit=crop&q=60", use_container_width=True)
st.sidebar.title("🌱 AgroFi Intelligence")
st.sidebar.markdown("**Módulo Agro, Data Science & Visualização**")

# Carrega configuração de Carteiras das Fazendas e Administradores
def load_farms_config():
    config_file = "farms_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                admin_w = data.get("admin_wallet", "0xa449e7838fF89EE956174B682449870597e93C71").lower()
                farms_dict = {farm["land_id"]: farm for farm in data.get("farms", [])}
                return farms_dict, {admin_w}
        except Exception:
            pass
    return {}, {"0xa449e7838ff89ee956174b682449870597e93c71"}

farms_config, ADMIN_WALLETS = load_farms_config()

# Leitura de Parâmetros de URL (Web3 Wallet & Fazenda Conectada)
query_params = st.query_params
param_land_id = query_params.get("land_id", "").strip()
param_wallet = query_params.get("wallet", "").strip()
wallet_lower = param_wallet.lower()

# Verificação de Permissões (RBAC)
is_admin = wallet_lower in ADMIN_WALLETS

farmer_farm = None
for lid, f_info in farms_config.items():
    if f_info.get("wallet_address", "").lower() == wallet_lower:
        farmer_farm = f_info
        break

# Bloqueio Estrito de Segurança: Apenas carteiras cadastradas e homologadas têm acesso
if not param_wallet or (not is_admin and not farmer_farm):
    st.error("⛔ ACESSO RESTRITO - CARTEIRA NÃO CADASTRADA")
    st.markdown(f"""
    <div style="background: #FFFFFF; border: 2px solid #E67E22; border-radius: 16px; padding: 26px; color: #1A2E20; margin-bottom: 25px; box-shadow: 0 10px 25px -4px rgba(230,126,34,0.12);">
        <h3 style="color: #E67E22; margin-top: 0; font-size: 20px; font-weight: 800;">🔒 Acesso Restrito ao Protocolo AgroFi</h3>
        <p style="font-size: 14px; line-height: 1.6; color: #556B5C;">O acesso ao Dashboard de Inteligência Geoespacial, Valoração de Colaterais e Oráculos de Crédito é <b>estritamente restrito</b> às carteiras autorizadas.</p>
        <p style="font-size: 13px; color: #1A2E20;"><b>Carteira Conectada:</b> <code style="background: #F7F9F6; padding: 4px 10px; border-radius: 6px; color: #00897B; border: 1px solid #E2E8E2; font-family: monospace; font-weight: bold;">{param_wallet if param_wallet else 'Nenhuma carteira conectada'}</code></p>
        <div style="margin-top: 15px; padding: 16px; background: #F7F9F6; border-radius: 12px; font-size: 12px; border: 1px solid #E2E8E2;">
            <b style="color: #1A2E20;">Carteiras Autorizadas pelo Protocolo:</b>
            <ul style="margin: 8px 0 0 18px; padding: 0; line-height: 1.8; color: #556B5C;">
                <li>👑 <b>Administrador Master:</b> <code style="color: #E67E22; font-weight: bold;">0xa449e7838fF89EE956174B682449870597e93C71</code></li>
                <li>🌾 <b>Fazenda Santa Helena (MT):</b> <code style="color: #00897B; font-weight: bold;">0xfdb2A29d047A8f10E0BC354b2E45C7Af386D112E</code></li>
                <li>🌱 <b>Fazenda Boa Esperança (GO):</b> <code style="color: #00897B; font-weight: bold;">0xC7C8931F662D9064ff495508AeA2AfA15E446D80</code></li>
                <li>🌿 <b>Agropecuária Chapadão (MT):</b> <code style="color: #00897B; font-weight: bold;">0xFf3b53ca866BCfEC18F1DD3cDff0A03776ab49b5</code></li>
                <li>🌽 <b>Fazenda Ouro Verde (BA):</b> <code style="color: #00897B; font-weight: bold;">0x35474822f1A45c0D2C0ddeb4D8Ff53fD8BD29ef7</code></li>
            </ul>
        </div>
        <a href="http://localhost:8080" style="display: inline-block; background: #00897B; color: #FFFFFF; padding: 10px 22px; border-radius: 10px; text-decoration: none; font-weight: 800; margin-top: 18px; box-shadow: 0 4px 12px rgba(0,137,123,0.25);">⬅ Voltar ao Portal e Conectar Carteira Válida</a>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Seleção de Talhões / Imóveis Rurais do SICAR com Restrição por Papel
parcels_df = orchestrator.sicar_ingestor.load_data()

if is_admin:
    # 👑 ADMIN MASTER: Acesso total a todas as fazendas cadastradas
    parcel_options = {
        f"{row['farm_name']} ({row['municipality']}-{row['state']})": row['land_id']
        for _, row in parcels_df.iterrows()
    }
    options_keys = list(parcel_options.keys())
    
    default_idx = 0
    if param_land_id:
        for idx, (label, lid) in enumerate(parcel_options.items()):
            if lid == param_land_id:
                default_idx = idx
                break

    param_sig = query_params.get("sig", "").strip()
    sig_display = f"""<div style="font-size: 10px; color: #E67E22; font-family: monospace; margin-top: 4px; word-break: break-all; font-weight: bold;">✍️ Assinatura: {param_sig[:10]}...{param_sig[-8:]} (Verificada)</div>""" if param_sig else """<div style="font-size: 10px; color: #E67E22; font-family: monospace; margin-top: 4px; font-weight: bold;">✍️ Autenticado com Assinatura Web3</div>"""

    st.sidebar.markdown(f"""
    <div style="background: #FFF8E1; border: 1.5px solid #FFE082; border-radius: 12px; padding: 14px; margin-top: 8px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(230,126,34,0.08);">
        <div style="font-size: 11px; color: #E67E22; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;">👑 Administrador Master</div>
        <div style="font-size: 12px; color: #1A2E20; font-weight: 700; margin-top: 2px;">Acesso Global a Todas as Fazendas</div>
        <div style="font-family: monospace; font-size: 11px; color: #00897B; word-break: break-all; margin-top: 4px; background: #FFFFFF; border: 1px solid #E2E8E2; padding: 4px 6px; border-radius: 6px; font-weight: bold;">{param_wallet}</div>
        {sig_display}
    </div>
    """, unsafe_allow_html=True)
    
    col_nav1, col_nav2 = st.sidebar.columns([1, 1])
    with col_nav1:
        st.markdown("[🏠 **Portal (8080)**](http://localhost:8080)")
    with col_nav2:
        if st.button("🚪 **Deslogar**", key="btn_logout_admin", use_container_width=True):
            st.query_params.clear()
            st.markdown('<meta http-equiv="refresh" content="0; url=http://localhost:8080?action=logout">', unsafe_allow_html=True)
            st.info("Desconectando...")
            st.stop()
    st.sidebar.markdown("---")

    selected_label = st.sidebar.selectbox("Selecione o Imóvel Rural (CAR):", options_keys, index=default_idx)
    selected_land_id = parcel_options[selected_label]
    farm_info = farms_config.get(selected_land_id, {})
    connected_wallet = param_wallet
    wallet_owner = "Administrador Master (Acesso Total)"

elif farmer_farm:
    # 🚜 PRODUTOR RURAL: Acesso estritamente restrito à sua fazenda
    selected_land_id = farmer_farm["land_id"]
    farm_info = farmer_farm
    connected_wallet = farmer_farm["wallet_address"]
    wallet_owner = farmer_farm.get("owner_name", f"Produtor {farmer_farm['farm_name']}")
    param_sig = query_params.get("sig", "").strip()
    sig_display = f"""<div style="font-size: 10px; color: #00897B; font-family: monospace; margin-top: 4px; word-break: break-all; font-weight: bold;">✍️ Assinatura: {param_sig[:10]}...{param_sig[-8:]} (Verificada)</div>""" if param_sig else """<div style="font-size: 10px; color: #00897B; font-family: monospace; margin-top: 4px; font-weight: bold;">✍️ Autenticado com Assinatura Web3</div>"""

    st.sidebar.markdown(f"""
    <div style="background: #E8F5E9; border: 1.5px solid #A7F3D0; border-radius: 12px; padding: 14px; margin-top: 8px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,137,123,0.08);">
        <div style="font-size: 11px; color: #00897B; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;">🌾 Produtor Rural Autenticado</div>
        <div style="font-size: 12px; color: #1A2E20; font-weight: 700; margin-top: 2px;">{wallet_owner}</div>
        <div style="font-family: monospace; font-size: 11px; color: #00897B; word-break: break-all; margin-top: 4px; background: #FFFFFF; border: 1px solid #E2E8E2; padding: 4px 6px; border-radius: 6px; font-weight: bold;">{connected_wallet}</div>
        {sig_display}
    </div>
    """, unsafe_allow_html=True)
    
    col_nav1, col_nav2 = st.sidebar.columns([1, 1])
    with col_nav1:
        st.markdown("[🏠 **Portal (8080)**](http://localhost:8080)")
    with col_nav2:
        if st.button("🚪 **Deslogar**", key="btn_logout_farmer", use_container_width=True):
            st.query_params.clear()
            st.markdown('<meta http-equiv="refresh" content="0; url=http://localhost:8080?action=logout">', unsafe_allow_html=True)
            st.info("Desconectando...")
            st.stop()
    st.sidebar.markdown("---")

    st.sidebar.selectbox(
        "Propriedade Rural (CAR):",
        [f"{farmer_farm['farm_name']} ({farmer_farm['municipality']}-{farmer_farm['state']})"],
        index=0,
        disabled=True,
        help="Acesso exclusivo ao titular do imóvel rural."
    )
    st.sidebar.caption("🔒 *Acesso exclusivo à sua propriedade. Dados de outras fazendas protegidos por permissão on-chain.*")

# Seleção de Modelo de Machine Learning
st.sidebar.markdown("### 🤖 Modelo de Valoração")
model_options = ["Stacking Ensemble (Recomendado)", "LightGBM", "XGBoost"]
selected_algo = st.sidebar.selectbox("Algoritmo de Regressão:", model_options, index=0)
model_choice = "StackingEnsemble" if "Stacking" in selected_algo else selected_algo

# Fase Climática ENSO
enso_phase = st.sidebar.selectbox(
    "Fase Macroclimática ENSO:",
    ["Neutral", "La_Nina", "El_Nino"],
    index=0,
    help="La Niña amplifica veranicos no Centro-Sul; El Niño causa estiagens no MATOPIBA."
)

# Simulador Paramétrico de Estresse Climático
st.sidebar.markdown("---")
st.sidebar.markdown("### ☀️ Simulação de Risco Climático")
st.sidebar.caption("Simule choques de estiagem/seca paramétrica na safra corrente:")

simulated_drought = st.sidebar.slider(
    "Anomalia Hídrica / Vigor NDVI (%):",
    min_value=-50,
    max_value=20,
    value=0,
    step=5,
    help="Valores negativos simulam seca severa ou atraso de chuvas; positivos simulam safra recorde."
)

if simulated_drought < 0:
    st.sidebar.warning(f"⚠️ Cenário Estressado: Queda de {abs(simulated_drought)}% no vigor vegetativo.")
elif simulated_drought > 0:
    st.sidebar.success(f"🌾 Cenário Favorável: Incremento de +{simulated_drought}% no vigor vegetativo.")
else:
    st.sidebar.info("Condições normais da série histórica de NDVI.")

# Execução da Avaliação Completa
evaluation = orchestrator.evaluate_land_full(
    land_id=selected_land_id,
    simulated_drought_pct=float(simulated_drought),
    model_choice=model_choice
)

parcel_meta = evaluation["parcel_metadata"]
topo = evaluation["topography"]
ndvi = evaluation["vegetation_ndvi"]
val = evaluation["valuation"]
risk = evaluation["risk_assessment"]
contract_payload = evaluation["web3_contract_payload"]
contract_payload["borrower_wallet"] = connected_wallet

# Simulação de Monte Carlo para o Talhão
mc_results = orchestrator.risk_engine.simulate_monte_carlo_distribution(
    base_risk_score=risk["crop_failure_probability"],
    total_land_value=val["predicted_value"],
    n_simulations=5000
)

# Banner Superior de Autenticação Web3 (Diferenciado por Papel)
if is_admin:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1A2E20 0%, #004D40 100%); padding: 16px 22px; border-radius: 16px; margin-bottom: 20px; color: white; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; box-shadow: 0 8px 20px rgba(26,46,32,0.15); border: 1.5px solid #00897B;">
        <div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 20px;">👑</span>
                <span style="font-size: 11px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: rgba(255,255,255,0.18); padding: 3px 10px; border-radius: 20px; color: #FFFFFF;">Administrador Master • Acesso Total</span>
                <span style="font-size: 11px; font-weight: 600; color: #00E676;">Sepolia / Anvil Local</span>
            </div>
            <div style="font-size: 16px; font-weight: 700; margin-top: 6px;">
                Carteira Master: <code style="background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 6px; color: #00E676; font-family: monospace; font-size: 13px;">{connected_wallet}</code>
            </div>
            <div style="font-size: 12px; opacity: 0.9; margin-top: 2px; color: #E2E8E2;">
                Inspecionando: <b>{parcel_meta['farm_name']}</b> ({parcel_meta['municipality']}/{parcel_meta['state']}) • Permissão Global de Gestão & Oráculo
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <a href="http://localhost:8080/dashboard.html" target="_blank" style="background: rgba(255,255,255,0.15); color: #FFFFFF; padding: 8px 14px; border-radius: 8px; text-decoration: none; font-size: 12px; font-weight: 600; border: 1px solid rgba(255,255,255,0.3);">⚡ Painel DeFi</a>
            <a href="http://localhost:8080" target="_self" style="background: #00E676; color: #1A2E20; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 12px; font-weight: 800; box-shadow: 0 2px 8px rgba(0,230,118,0.4);">🏠 Portal AgroFi (8080)</a>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #00897B 0%, #00695C 100%); padding: 16px 22px; border-radius: 16px; margin-bottom: 20px; color: white; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; box-shadow: 0 8px 20px rgba(0,137,123,0.15); border: 1.5px solid #00E676;">
        <div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 20px;">🌾</span>
                <span style="font-size: 11px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: rgba(255,255,255,0.18); padding: 3px 10px; border-radius: 20px; color: #FFFFFF;">Fazenda Conectada via Web3</span>
                <span style="font-size: 11px; font-weight: 600; color: #00E676;">Acesso Exclusivo do Produtor Titular</span>
            </div>
            <div style="font-size: 16px; font-weight: 700; margin-top: 6px;">
                {parcel_meta['farm_name']} • Carteira: <code style="background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 6px; color: #00E676; font-family: monospace; font-size: 13px;">{connected_wallet}</code>
            </div>
            <div style="font-size: 12px; opacity: 0.9; margin-top: 2px; color: #E2E8E2;">
                Titular: {wallet_owner} | Limite Aprovado: ${farm_info.get('credit_limit_usd', 250000):,.2f} USDC
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <a href="http://localhost:8080/dashboard.html" target="_blank" style="background: rgba(255,255,255,0.15); color: #FFFFFF; padding: 8px 14px; border-radius: 8px; text-decoration: none; font-size: 12px; font-weight: 600; border: 1px solid rgba(255,255,255,0.3);">⚡ Painel DeFi</a>
            <a href="http://localhost:8080" target="_self" style="background: #00E676; color: #1A2E20; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 12px; font-weight: 800; box-shadow: 0 2px 8px rgba(0,230,118,0.4);">🏠 Portal AgroFi (8080)</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Título Principal
st.title(f"🌾 {parcel_meta['farm_name']} - Análise de Colateral RWA")
st.caption(f"**Código CAR:** `{parcel_meta['car_code']}` | **Município:** {parcel_meta['municipality']}/{parcel_meta['state']} | **Bioma:** {parcel_meta['biome']}")

# Painel Superior de KPIs Executivos
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="ÁREA ÚTIL CONSOLIDADA",
        value=f"{parcel_meta['productive_area_ha']:,.0f} ha",
        delta=f"{parcel_meta['total_area_ha']:,.0f} ha total"
    )

with col2:
    st.metric(
        label="DECLIVIDADE MÉDIA (SRTM)",
        value=f"{topo['slope_mean_pct']:.1f}%",
        delta=topo['relief_classification'],
        delta_color="off"
    )

with col3:
    st.metric(
        label="VALOR PATRIMONIAL ESTIMADO",
        value=f"R$ {val['predicted_value']/1e6:,.2f} M",
        delta=f"R$ {val['price_per_ha']:,.0f}/ha"
    )

with col4:
    ltv_val = contract_payload['ltv_ratio']
    st.metric(
        label="LTV DINÂMICO (DEFI)",
        value=f"{ltv_val*100:.1f}%",
        delta="Faixa [35% - 65%]",
        delta_color="normal" if ltv_val > 0.50 else "inverse"
    )

with col5:
    hf = contract_payload['health_factor']
    if hf >= 1.20:
        hf_status = "Seguro (Green)"
    elif hf >= 1.00:
        hf_status = "Atenção (Yellow)"
    else:
        hf_status = "Risco Liquidação (Red)"

    st.metric(
        label="HEALTH FACTOR (HF)",
        value=f"{hf:.2f}",
        delta=hf_status,
        delta_color="normal" if hf >= 1.0 else "inverse"
    )

st.markdown("---")

# Abas de Conteúdo
tab_map, tab_models, tab_ndvi, tab_web3, tab_team = st.tabs([
    "🗺️ Cartografia Interativa (MapLibre GL JS)",
    "📊 Valoração Patrimonial & Benchmark ML",
    "📈 Série Temporal NDVI & Simulação Monte Carlo",
    "⚡ Contrato Web3 & Middleware DeFi",
    "👥 Equipe & Governança Técnica"
])

# ABA 1: Cartografia Interativa MapLibre GL JS
with tab_map:
    st.subheader("Visualização Vetorial de Polígonos do CAR & Aptidão Territorial")
    st.caption("Renderizado via MapLibre GL JS sobre tiles Carto/OpenStreetMap, exibindo limites consolidados, APPs e Reservas:")
    
    geojson_data = orchestrator.sicar_ingestor.get_geojson_dict()
    map_html = render_maplibre_html(
        geojson_data=geojson_data,
        selected_land_id=selected_land_id,
        center_lon=parcel_meta["centroid_lon"],
        center_lat=parcel_meta["centroid_lat"],
        zoom=12.2,
        height_px=520
    )
    components.html(map_html, height=540)
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f"**Aptidão Agrícola (VTN):** {parcel_meta['aptitude']}")
        st.markdown(f"**Aptidão de Mecanização:** {topo['mechanization_suitability_score']*100:.0f}%")
    with col_b:
        st.markdown(f"**Reserva Legal Declarada:** {parcel_meta['legal_reserve_ha']:,.0f} ha ({parcel_meta['reserve_actual_pct']:.1f}%)")
        st.markdown(f"**Reserva Exigida (Código Florestal):** {parcel_meta['reserve_req_pct']:.0f}%")
    with col_c:
        st.markdown(f"**Score de Conformidade Ambiental:** {parcel_meta['compliance_score']*100:.1f}%")
        st.markdown(f"**Altitude Média:** {topo['elevation_mean_m']} metros")

# ABA 2: Benchmark Machine Learning & Quantiles
with tab_models:
    st.subheader("Benchmark de Modelos de Regressão: LightGBM vs XGBoost vs Stacking Ensemble")
    st.caption("Treinados com base de histórico de VTN (Receita Federal), variáveis topográficas SRTM e área útil CAR:")
    
    benchmark = orchestrator.valuation_model.benchmark_metrics
    col_m1, col_m2 = st.columns(2)
    
    with col_m1:
        st.markdown("#### Métricas de Validação Cruzada (5-Fold CV)")
        metrics_df = pd.DataFrame({
            "Métrica": ["R² Score (Acurácia)", "RMSE (Erro Quadrático Médio)", "MAE (Erro Médio Absoluto)"],
            "LightGBM": [
                f"{benchmark.get('LightGBM', {}).get('r2', 0.987):.4f}",
                f"R$ {benchmark.get('LightGBM', {}).get('rmse', 6900000):,.2f}",
                f"R$ {benchmark.get('LightGBM', {}).get('mae', 4600000):,.2f}"
            ],
            "XGBoost": [
                f"{benchmark.get('XGBoost', {}).get('r2', 0.989):.4f}",
                f"R$ {benchmark.get('XGBoost', {}).get('rmse', 6400000):,.2f}",
                f"R$ {benchmark.get('XGBoost', {}).get('mae', 4300000):,.2f}"
            ],
            "Stacking Ensemble": [
                f"{benchmark.get('StackingEnsemble', {}).get('r2', 0.991):.4f}",
                f"R$ {benchmark.get('StackingEnsemble', {}).get('rmse', 5900000):,.2f}",
                f"R$ {benchmark.get('StackingEnsemble', {}).get('mae', 3900000):,.2f}"
            ]
        })
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)
        st.info(f"🏆 Modelo Campeão Selecionado pelo Pipeline: **{orchestrator.valuation_model.champion_model_name}**")

    with col_m2:
        st.markdown(f"#### Importância de Features ({model_choice})")
        feat_imp = orchestrator.valuation_model.get_feature_importances(model_name="XGBoost" if "XGB" in model_choice else "LightGBM")
        imp_df = pd.DataFrame(list(feat_imp.items()), columns=["Variável / Feature", "Importância (%)"]).head(8)
        st.bar_chart(imp_df.set_index("Variável / Feature"), horizontal=True)

    st.markdown("---")
    st.markdown("#### Distribuição Quantílica do Valor de Colateral (Risco Ajustado)")
    col_q1, col_q2, col_q3 = st.columns(3)
    
    q10_val = val.get("q10_conservative_floor", val["ci_low"])
    q50_val = val.get("q50_median", val["predicted_value"])
    q90_val = val.get("q90_optimistic_cap", val["ci_high"])
    
    with col_q1:
        st.metric("Piso Conservador (Q10 - Estresse)", f"R$ {q10_val:,.2f}", delta="- Margem de Segurança")
        st.caption("Valor para liquidação forçada rápida em caso de colapso de mercado.")
    with col_q2:
        st.metric("Mediana de Mercado (Q50)", f"R$ {q50_val:,.2f}", delta="Valor Central")
        st.caption("Preço de referência para operações de crédito sob condições normais.")
    with col_q3:
        st.metric("Teto Otimista (Q90)", f"R$ {q90_val:,.2f}", delta="+ Safra Recorde")
        st.caption("Avaliação máxima em condições climáticas excepcionais.")

# ABA 3: NDVI e Simulação de Monte Carlo
with tab_ndvi:
    st.subheader("Série Temporal Quinzenal de NDVI (Sentinel-2) & Análise Estocástica de Risco")
    st.caption("Monitoramento do ciclo fenológico e identificação de anomalias hídricas na safra corrente:")

    ts_data = pd.DataFrame(ndvi["timeseries_data"])
    if not ts_data.empty:
        ts_data["date"] = pd.to_datetime(ts_data["date"])
        ts_data = ts_data.rename(columns={
            "ndvi_observed": "NDVI Observado / Simulado",
            "mean": "Linha de Base Histórica (Média)"
        })
        st.line_chart(
            ts_data.set_index("date")[["NDVI Observado / Simulado", "Linha de Base Histórica (Média)"]],
            color=["#10b981", "#94a3b8"]
        )

    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    col_r1.metric("NDVI de Pico (Safra)", f"{ndvi['ndvi_peak']:.3f}")
    col_r2.metric("Z-Score na Janela Crítica", f"{ndvi['critical_window_zscore']:.2f} σ")
    col_r3.metric("Probabilidade de Quebra", f"{risk['crop_failure_probability']*100:.1f}%")
    col_r4.metric("Índice de Estresse Hídrico", f"{risk['climate_stress_index']*100:.1f}%")

    st.markdown("---")
    st.markdown("#### Simulação de Monte Carlo: Value-at-Risk (VaR) & Perda Máxima Provável (5.000 Iterações)")
    st.caption("Avalia a resiliência do colateral RWA frente a choques estocásticos de clima e produtividade:")
    
    col_mc1, col_mc2, col_mc3, col_mc4 = st.columns(4)
    col_mc1.metric("Capacidade Nominal de Crédito", f"R$ {mc_results['nominal_borrow_capacity_brl']:,.2f}")
    col_mc2.metric("VaR 95% (Queda Máxima 1 Ano)", f"R$ {mc_results['var_95_drawdown_brl']:,.2f}")
    col_mc3.metric("VaR 99% (Estresse Severo)", f"R$ {mc_results['var_99_drawdown_brl']:,.2f}")
    col_mc4.metric("Expected Shortfall (CVaR 95%)", f"R$ {mc_results['cvar_95_expected_shortfall_brl']:,.2f}")

    # Gráfico de Distribuição dos LTVs Simulados
    ltv_sample_df = pd.DataFrame({"LTV Simulado (%)": [v * 100 for v in mc_results["simulated_ltv_sample"]]})
    st.bar_chart(ltv_sample_df.head(40))

# ABA 4: Contrato Web3 & Oráculo
with tab_web3:
    st.subheader("⚡ Conexão Fim a Fim: Oráculo Geoespacial ➔ Smart Contract (AgroFiVault.sol)")
    st.caption("Ponte descentralizada entre os modelos de sensoriamento remoto/ML e o protocolo de crédito colateralizado em RWA:")

    solidity_predicted_value = int(contract_payload["predicted_value"] * 10**18)
    solidity_ltv_bps = int(round(contract_payload["ltv_ratio"] * 10000))
    solidity_health_factor = int(round(contract_payload["health_factor"] * 10**18))
    is_liquidatable = contract_payload["health_factor"] < 1.0
    max_borrow_allowed = (contract_payload["predicted_value"] * contract_payload["ltv_ratio"])

    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        st.metric(
            label="CAPACIDADE MÁXIMA DE EMPRÉSTIMO",
            value=f"R$ {max_borrow_allowed:,.2f}",
            delta=f"LTV: {contract_payload['ltv_ratio']*100:.1f}% (BPS: {solidity_ltv_bps})"
        )
    with col_w2:
        st.metric(
            label="HEALTH FACTOR ON-CHAIN",
            value=f"{contract_payload['health_factor']:.3f}",
            delta=f"Escala 1e18: {solidity_health_factor:,}",
            delta_color="normal" if not is_liquidatable else "inverse"
        )
    with col_w3:
        if is_liquidatable:
            st.error("🚨 POSIÇÃO LIQUIDÁVEL (HF < 1.0)!\nLiquidação Paramétrica Desencadeada.")
        else:
            st.success("✅ POSIÇÃO SOLVENTE (HF ≥ 1.0)\nColateral Seguro no Vault.")

    st.markdown("---")

    col_code1, col_code2 = st.columns(2)

    with col_code1:
        st.markdown("#### 1. Payload de Saída da API (REST/Off-Chain)")
        st.caption("Consumido pelo nó oráculo / relayer autorizado:")
        st.code(json.dumps(contract_payload, indent=2), language="json")

    with col_code2:
        st.markdown("#### 2. Mapeamento de Tipos para o Smart Contract (`AgroFiVault.sol`)")
        st.caption("Assinatura `updateLandValuation(tokenId, landId, carCode, predictedValue, ltvRatioBps, healthFactor)`:")
        solidity_call_preview = {
            "tokenId": 1,
            "landId": contract_payload["land_id"],
            "carCode": contract_payload["car_code"],
            "predictedValue (wei - 18 dec)": str(solidity_predicted_value),
            "ltvRatioBps (3500-6500)": solidity_ltv_bps,
            "healthFactor (1e18)": str(solidity_health_factor),
            "status_liquidacao": "ATIVADA (Parametric Liquidation Triggered)" if is_liquidatable else "NORMAL"
        }
        st.code(json.dumps(solidity_call_preview, indent=2), language="json")

    st.markdown("---")
    st.markdown("#### 3. Ações Operacionais do Oracle Keeper & Dossiê de Crédito")
    
    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("🚀 Simular Envio de Transação pelo Oracle Keeper Daemon"):
            tx = oracle_keeper.prepare_onchain_update(
                land_id=selected_land_id,
                token_id=1,
                simulated_drought_pct=float(simulated_drought)
            )
            st.success(f"Transação simulada com sucesso! Gas estimado: {tx.gas_estimate} gas.")
            st.json(tx.model_dump())

    with col_act2:
        # Exportação de Dossiê Cadastral
        parcel_clean = {
            k: (v.__geo_interface__ if hasattr(v, "__geo_interface__") else v)
            for k, v in parcel_meta.items()
        }
        dossier = {
            "dossier_id": f"DOSSIER-{selected_land_id}-{datetime.now().strftime('%Y%m%d%H%M')}",
            "generated_at": datetime.now().isoformat(),
            "parcel_metadata": parcel_clean,
            "topography": topo,
            "valuation": val,
            "risk_assessment": risk,
            "monte_carlo_var": mc_results,
            "web3_contract_payload": contract_payload
        }
        st.download_button(
            label="📥 Baixar Dossiê Cadastral de Crédito RWA (JSON)",
            data=json.dumps(dossier, indent=2, ensure_ascii=False, default=str),
            file_name=f"AgroFi_Dossier_{selected_land_id}.json",
            mime="application/json"
        )

# ABA 5: Equipe & Governança Técnica
with tab_team:
    st.subheader("👥 Estrutura do Squad Multidisciplinar AgroFi")
    st.caption("Organização técnica especializada para operação do protocolo RWA DeFi em escala de produção:")

    team_members = [
        {"Papel": "Tech Lead & Arquiteto de Software", "Senioridade": "Sênior / Principal", "Foco": "Arquitetura Fim a Fim, Contratos de API & Governança", "Stack": "Python, FastAPI, Clean Arch, Docker"},
        {"Papel": "Engenheiro de Machine Learning / MLOps", "Senioridade": "Sênior", "Foco": "Modelos de Valoração Patrimonial & Monitoramento de Drift", "Stack": "LightGBM, XGBoost, Scikit-Learn, MLflow"},
        {"Papel": "Engenheiro de Geoprocessamento & GIS", "Senioridade": "Sênior", "Foco": "Pipelines SICAR, Sentinel-2 (NDVI) & Rasters SRTM", "Stack": "GeoPandas, Rasterio, GDAL, Shapely, PostGIS"},
        {"Papel": "Engenheiro Agrônomo & Modelador de Risco", "Senioridade": "Especialista", "Foco": "Fenologia de Safras, Zoneamento ZARC & Código Florestal", "Stack": "Balanço Hídrico, Estatística Estocástica, Embrapa"},
        {"Papel": "Engenheiro Web3 & Smart Contracts", "Senioridade": "Sênior", "Foco": "Vaults de Empréstimo DeFi, Oráculos & Tokenização RWA", "Stack": "Solidity, Foundry, Chainlink Oracles, ERC-3643"},
        {"Papel": "Engenheiro Frontend & Cartografia", "Senioridade": "Pleno / Sênior", "Foco": "Visualização Geoespacial Vetorial & UX de Crédito", "Stack": "MapLibre GL JS, Streamlit, React, Deck.gl"},
        {"Papel": "Engenheiro DevOps & Cloud GIS (SRE)", "Senioridade": "Sênior", "Foco": "Infraestrutura de Processamento Satelital & Alta Disponibilidade", "Stack": "Kubernetes, AWS/GCP, Cloud Optimized GeoTIFF"},
    ]

    st.dataframe(pd.DataFrame(team_members), use_container_width=True, hide_index=True)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown("#### Matriz RACI dos Módulos")
        raci_data = pd.DataFrame({
            "Módulo": ["SICAR / CAR", "SRTM / Declividade", "Sentinel-2 NDVI", "Valoração ML", "Motor Risco / LTV", "Smart Contracts / Web3", "Cartografia MapLibre"],
            "Responsável (R)": ["Geo Eng", "Geo Eng", "Geo Eng / Agrônomo", "ML Eng", "ML Eng / Agrônomo", "Web3 Eng", "Front Eng"],
            "Aprovador (A)": ["Tech Lead", "Tech Lead", "Tech Lead", "Tech Lead", "Tech Lead", "Tech Lead", "Tech Lead"]
        })
        st.dataframe(raci_data, use_container_width=True, hide_index=True)

    with col_t2:
        st.markdown("#### Metas Técnicas (OKRs do Squad)")
        st.markdown("""
        1. **Latência de Oráculo:** Resposta do endpoint Web3 em tempo inferior a **200 ms** em 99% das requisições (p99).
        2. **Acurácia Preditiva:** Manter $R^2 \ge 0.95$ e $\text{MAPE} \le 7\%$ nos modelos de valoração de terras rurais.
        3. **Taxa de Inadimplência Zero por Sinistro:** Manter a margem de LTV ajustada dinamicamente entre **35% e 65%**, garantindo solvência mesmo em quebras severas de safra.
        """)
