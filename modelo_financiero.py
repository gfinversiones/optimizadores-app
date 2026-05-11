# ============================================================
# APP FINANCIERA PROJECT FINANCE / PPP / CONCESIONES
# STREAMLIT + PYTHON
# ============================================================

# ============================================================
# IMPORTS
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from numpy_financial import npv, irr

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Modelo Financiero PPP",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Modelo Financiero PPP / Concesión")

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("⚙️ Parámetros del Modelo")

# ============================================================
# HORIZONTE
# ============================================================

anios = st.sidebar.slider(
    "Horizonte del Proyecto (años)",
    5,
    40,
    20
)

# ============================================================
# TRANSITO
# ============================================================

st.sidebar.subheader("🚗 Tránsito")

transito_inicial = st.sidebar.number_input(
    "Tránsito Inicial",
    value=1000000
)

crecimiento_transito = st.sidebar.slider(
    "Crecimiento Tránsito %",
    -10.0,
    20.0,
    3.0
)

sens_transito = st.sidebar.slider(
    "Sensibilidad Tránsito %",
    -50.0,
    50.0,
    0.0
)

# ============================================================
# TARIFA
# ============================================================

st.sidebar.subheader("💰 Tarifas")

tarifa_base = st.sidebar.number_input(
    "Tarifa Base",
    value=1200.0
)

sens_tarifa = st.sidebar.slider(
    "Sensibilidad Tarifa %",
    -50.0,
    50.0,
    0.0
)

# ============================================================
# CAPEX
# ============================================================

st.sidebar.subheader("🏗️ CAPEX")

capex_base = st.sidebar.number_input(
    "CAPEX Inicial",
    value=250000000.0
)

sens_capex = st.sidebar.slider(
    "Sensibilidad CAPEX %",
    -50.0,
    100.0,
    0.0
)

# ============================================================
# OPEX
# ============================================================

st.sidebar.subheader("⚙️ OPEX")

opex_pct = st.sidebar.slider(
    "OPEX % sobre ingresos",
    0.0,
    100.0,
    30.0
)

sens_opex = st.sidebar.slider(
    "Sensibilidad OPEX %",
    -50.0,
    100.0,
    0.0
)

# ============================================================
# IMPUESTOS
# ============================================================

st.sidebar.subheader("🏛️ Impuestos")

impuesto_ganancias = st.sidebar.slider(
    "Ganancias %",
    0.0,
    50.0,
    35.0
)

iva = st.sidebar.slider(
    "IVA %",
    0.0,
    50.0,
    21.0
)

iibb = st.sidebar.slider(
    "Ingresos Brutos %",
    0.0,
    20.0,
    3.0
)

debitos_creditos = st.sidebar.slider(
    "Débitos y Créditos %",
    0.0,
    5.0,
    1.2
)

# ============================================================
# FINANCIAMIENTO
# ============================================================

st.sidebar.subheader("🏦 Financiamiento")

porcentaje_deuda = st.sidebar.slider(
    "% Deuda",
    0.0,
    100.0,
    70.0
)

tasa_deuda = st.sidebar.slider(
    "Tasa Deuda %",
    0.0,
    30.0,
    8.0
)

plazo_deuda = st.sidebar.slider(
    "Plazo Deuda",
    1,
    30,
    15
)

# ============================================================
# TASA DESCUENTO
# ============================================================

st.sidebar.subheader("📉 Descuento")

wacc = st.sidebar.slider(
    "WACC %",
    0.0,
    30.0,
    10.0
)

# ============================================================
# AJUSTES
# ============================================================

transito_ajustado = transito_inicial * (1 + sens_transito / 100)

tarifa_ajustada = tarifa_base * (1 + sens_tarifa / 100)

capex_ajustado = capex_base * (1 + sens_capex / 100)

opex_pct_ajustado = opex_pct * (1 + sens_opex / 100)

# ============================================================
# PROYECCIONES
# ============================================================

years = np.arange(0, anios + 1)

trafico = []
ingresos = []
opex = []
ebitda = []
impuestos = []
fcff = []

for year in years:

    traf = transito_ajustado * ((1 + crecimiento_transito / 100) ** year)

    ingreso = traf * tarifa_ajustada

    costo_opex = ingreso * (opex_pct_ajustado / 100)

    ebit = ingreso - costo_opex

    tax = max(0, ebit * (impuesto_ganancias / 100))

    flujo = ebit - tax

    trafico.append(traf)
    ingresos.append(ingreso)
    opex.append(costo_opex)
    ebitda.append(ebit)
    impuestos.append(tax)
    fcff.append(flujo)

# ============================================================
# CAPEX AÑO 0
# ============================================================

fcff[0] = fcff[0] - capex_ajustado

# ============================================================
# VAN
# ============================================================

van = npv(wacc / 100, fcff)

# ============================================================
# TIR
# ============================================================

tir = irr(fcff)

# ============================================================
# MIRR
# ============================================================

finance_rate = tasa_deuda / 100
reinvest_rate = wacc / 100

positive = []
negative = []

for f in fcff:

    if f > 0:
        positive.append(f)
        negative.append(0)

    else:
        positive.append(0)
        negative.append(f)

pv_neg = 0
fv_pos = 0

for i, val in enumerate(negative):
    pv_neg += val / ((1 + finance_rate) ** i)

for i, val in enumerate(positive):
    fv_pos += val * ((1 + reinvest_rate) ** (anios - i))

mirr = ((fv_pos / abs(pv_neg)) ** (1 / anios)) - 1

# ============================================================
# VAE / VAFF
# ============================================================

vae = van / anios

vaff = van + capex_ajustado

ratio_vaff_vae = vaff / vae if vae != 0 else 0

# ============================================================
# DATAFRAME
# ============================================================

df = pd.DataFrame({
    "Año": years,
    "Tráfico": trafico,
    "Ingresos": ingresos,
    "OPEX": opex,
    "EBITDA": ebitda,
    "Impuestos": impuestos,
    "FCFF": fcff
})

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard",
    "📈 Flujos",
    "🔥 Sensibilidades",
    "🏦 Financiamiento",
    "📁 Excel"
])

# ============================================================
# DASHBOARD
# ============================================================

with tab1:

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "VAN",
        f"${van:,.0f}"
    )

    col2.metric(
        "TIR",
        f"{tir*100:.2f}%"
    )

    col3.metric(
        "MIRR",
        f"{mirr*100:.2f}%"
    )

    col4.metric(
        "VAFF/VAE",
        f"{ratio_vaff_vae:.2f}"
    )

    st.subheader("FCFF")

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["Año"],
            y=df["FCFF"],
            name="FCFF"
        )
    )

    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# FLUJOS
# ============================================================

with tab2:

    st.subheader("Flujos del Proyecto")

    st.dataframe(df, use_container_width=True)

    fig2 = px.line(
        df,
        x="Año",
        y=["Ingresos", "OPEX", "EBITDA"],
        title="Evolución Financiera"
    )

    st.plotly_chart(fig2, use_container_width=True)

# ============================================================
# SENSIBILIDADES
# ============================================================

with tab3:

    st.subheader("Sensibilidad TIR")

    variables = [
        "Tránsito",
        "Tarifa",
        "CAPEX",
        "OPEX"
    ]

    impactos = [
        sens_transito,
        sens_tarifa,
        -sens_capex,
        -sens_opex
    ]

    sens_df = pd.DataFrame({
        "Variable": variables,
        "Impacto": impactos
    })

    fig3 = px.bar(
        sens_df,
        x="Impacto",
        y="Variable",
        orientation="h",
        title="Tornado Sensitivity"
    )

    st.plotly_chart(fig3, use_container_width=True)

# ============================================================
# FINANCIAMIENTO
# ============================================================

with tab4:

    deuda = capex_ajustado * (porcentaje_deuda / 100)

    equity = capex_ajustado - deuda

    st.metric(
        "Deuda",
        f"${deuda:,.0f}"
    )

    st.metric(
        "Equity",
        f"${equity:,.0f}"
    )

    deuda_anual = deuda / plazo_deuda

    deuda_df = pd.DataFrame({
        "Año": np.arange(1, plazo_deuda + 1),
        "Servicio Deuda": [deuda_anual] * plazo_deuda
    })

    fig4 = px.bar(
        deuda_df,
        x="Año",
        y="Servicio Deuda",
        title="Servicio de Deuda"
    )

    st.plotly_chart(fig4, use_container_width=True)

# ============================================================
# EXCEL
# ============================================================

with tab5:

    st.subheader("Carga Excel")

    archivo = st.file_uploader(
        "Subir Excel",
        type=["xlsx"]
    )

    if archivo is not None:

        excel_df = pd.read_excel(archivo)

        st.success("Excel cargado correctamente")

        st.dataframe(excel_df)

# ============================================================
# EXPORTAR
# ============================================================

csv = df.to_csv(index=False).encode("utf-8")

st.download_button(
    "⬇ Descargar Resultados CSV",
    csv,
    "modelo_financiero.csv",
    "text/csv"
)