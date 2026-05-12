import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ══════════════════════════════════════════════════════════════
# 1. FUNCIONES FINANCIERAS (Sin librerías externas)
# ══════════════════════════════════════════════════════════════

def _npv(rate, cf):
    t = np.arange(len(cf))
    return np.sum(cf / (1 + rate)**t)

def _mirr(cf, rate):
    pos = cf[cf > 0]
    neg = cf[cf < 0]
    if len(pos) == 0 or len(neg) == 0: return 0
    n = len(cf) - 1
    fv_pos = np.sum(pos * (1 + rate)**(n - np.where(cf > 0)[0]))
    pv_neg = np.sum(neg / (1 + rate)**np.where(cf < 0)[0])
    return (fv_pos / -pv_neg)**(1/n) - 1

# ══════════════════════════════════════════════════════════════
# 2. CONFIGURACIÓN Y ESTILOS
# ══════════════════════════════════════════════════════════════

st.set_page_config(page_title="Caucete IA - Modelo Financiero", layout="wide")

# Diccionario de estilos para Plotly (evitando duplicados)
PL_STYLE = dict(
    template="plotly_white",
    font=dict(family="Arial", size=12),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

# ══════════════════════════════════════════════════════════════
# 3. SIDEBAR - SENSIBILIDADES
# ══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("🎛️ Parámetros de Simulación")
    
    tarifa = st.number_input("Tarifa Base (Sin IVA)", value=6000)
    d_trafico = st.slider("Δ Tránsito Anual (%)", -5.0, 5.0, 0.0) / 100
    
    st.subheader("Costos (CAPEX / OPEX)")
    d_obras = st.slider("Δ Obras Obligatorias (%)", -50, 50, 0) / 100
    d_repav = st.slider("Δ Repavimentación (%)", -50, 50, 0) / 100
    d_opex = st.slider("Δ OPEX (%)", -50, 50, 0) / 100
    
    st.subheader("Financiero")
    tasa_d = st.number_input("Tasa Descuento (WACC)", value=0.10)
    ali_gan = st.number_input("Alícuota Ganancias", value=0.35)

# ══════════════════════════════════════════════════════════════
# 4. MOTOR DE CÁLCULO (Réplica de Caucete IA.xlsx)
# ══════════════════════════════════════════════════════════════

# Vectores base (21 años: 2025-2045)
años = np.arange(2025, 2046)

# Ingresos: Basado en Hoja FLUJO (Y2 arranque peaje)
ingresos_base_y2 = 24541041681.62
factores = np.zeros(21)
factores[2] = 1.0 * (tarifa / 6000)
for i in range(3, 21):
    factores[i] = factores[i-1] * (1 + 0.03 + d_trafico)

ingresos = ingresos_base_y2 * factores
ingresos[0] = 2023250250.0  # Crédito Inicial

# CAPEX: Desglose por tipo para aplicar sensibilidad correcta
pv_inicial = 2890357500.0
obras_vector = np.array([0,0,0,0,0,0,5702,11405,11405,11405,11405,17108,11405,11405,11405,5702,5702,0,0,0,0]) * 1e6
repav_vector = np.array([0,0,0,4335,4335,4335,8671,8671,8671,1734,0,0,0,4335,4335,4335,4335,8671,8671,8671,8671]) * 1e6

capex_total = np.zeros(21)
capex_total[0] = pv_inicial
capex_total += obras_vector * (1 + d_obras)
capex_total += repav_vector * (1 + d_repav)

# OPEX y Otros Egresos
opex_anual = 3853810000.0 * (1 + d_opex)
opex_vector = np.array([0] + [opex_anual]*20)

# Impuestos y Amortización Deuda (Fijo del modelo)
impuestos = np.where(ingresos > 2e9, ingresos * 0.12 * (ali_gan / 0.35), 0)
amort_deuda = np.array([0, 464552590, 444320087, 444320087, 444320087, 444320087, 444320087] + [0]*14)

egresos_totales = capex_total + opex_vector + impuestos + amort_deuda
flujo_neto = ingresos - egresos_totales

# Métricas
van = _npv(tasa_d, flujo_neto)
mirr = _mirr(flujo_neto, tasa_d)
vaff_vae = van / _npv(tasa_d, egresos_totales) if _npv(tasa_d, egresos_totales) != 0 else 0

# ══════════════════════════════════════════════════════════════
# 5. DASHBOARD VISUAL
# ══════════════════════════════════════════════════════════════

st.title("🛣️ Dashboard Financiero: Proyecto Caucete")

m1, m2, m3 = st.columns(3)
m1.metric("VAN (NPV)", f"$ {van:,.0f}")
m2.metric("MIRR", f"{mirr:.2%}")
m3.metric("VAFF / VAE", f"{vaff_vae:.4f}")

# Gráfico Principal
fig = go.Figure()
fig.add_trace(go.Bar(x=años, y=flujo_neto, name="Flujo Neto", marker_color="#2E91E5"))
fig.add_trace(go.Scatter(x=años, y=np.cumsum(flujo_neto), name="Acumulado", line=dict(color="#E15F41", width=3)))

# FIJADO: Aquí estaba el error. Separamos update_layout en dos para no duplicar 'margin'.
fig.update_layout(**PL_STYLE)
fig.update_layout(
    title="Flujo de Fondos y Recuperación de Inversión",
    yaxis_title="Pesos ($ ARS)",
    height=500,
    margin=dict(l=50, r=50, t=80, b=50) # Definido una sola vez aquí
)

st.plotly_chart(fig, width='stretch')

# Tabla de Datos
with st.expander("Ver Cuadro de Flujo Detallado"):
    df = pd.DataFrame({
        "Año": años,
        "Ingresos": ingresos,
        "CAPEX": capex_total,
        "OPEX": opex_vector,
        "Impuestos": impuestos,
        "Flujo Neto": flujo_neto
    }).set_index("Año")
    st.dataframe(df.style.format("{:,.0f}"), height=400)