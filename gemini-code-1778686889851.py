"""
CAUCETE – Panel de Sensibilidades Financieras
==============================================
Replicación fiel del modelo CAUCETE.xlsx con correcciones técnicas aplicadas.
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ══════════════════════════════════════════════════════════════
# 0.  FUNCIONES FINANCIERAS PURAS
# ══════════════════════════════════════════════════════════════

def _npv(rate: float, cf: np.ndarray) -> float:
    t = np.arange(len(cf), dtype=float)
    return float(np.sum(cf / (1.0 + rate) ** t))


def _mirr(cf: np.ndarray, reinvest_rate: float) -> float:
    n = len(cf) - 1
    neg = np.where(cf < 0, cf, 0.0)
    pos = np.where(cf > 0, cf, 0.0)
    pv_neg = sum(neg[t] / (1 + reinvest_rate) ** t for t in range(n + 1))
    fv_pos = sum(pos[t] * (1 + reinvest_rate) ** (n - t) for t in range(n + 1))
    if pv_neg >= 0 or fv_pos <= 0:
        return float("nan")
    return (fv_pos / (-pv_neg)) ** (1.0 / n) - 1.0


# ══════════════════════════════════════════════════════════════
# 1.  DATOS BASE (Extraídos del xlsx)
# ══════════════════════════════════════════════════════════════

YEARS = 20
PEAJE_BASE = np.array([0, 24541041681.62, 25277272932.07, 26035591120.03, 26816658853.63, 27621158619.24, 
                       28449793377.82, 29303287179.15, 30182385794.53, 31087857368.36, 32020493089.41, 
                       32981107882.10, 33970541118.56, 34989657352.12, 36039347072.68, 37120527484.86, 
                       38234143309.40, 39381167608.69, 40562602636.95, 41779480716.06, 41779480716.06], dtype=float)

TARIFA_BASE = 6000.0
UTEQ_ARRANQUE = PEAJE_BASE[1] / TARIFA_BASE
TRAFICO_CRECIMIENTO_BASE = 0.03

CAPEX_BASE = np.array([2890357500.0, 0, 0, 4335536250.0, 4335536250.0, 4335536250.0, 14373922500.0, 20076772500.0, 
                       20076772500.0, 13139914500.0, 11405700000.0, 17108550000.0, 11405700000.0, 15741236250.0, 
                       15741236250.0, 10038386250.0, 10038386250.0, 8671072500.0, 8671072500.0, 8671072500.0, 8671072500.0], dtype=float)

OPEX_BASE = np.full(YEARS + 1, 3853810000.0)
AMORT_DEUDA_BASE = np.zeros(YEARS + 1)
AMORT_DEUDA_BASE[1] = 464552590.09
AMORT_DEUDA_BASE[2:7] = 444320087.59
GARANTIAS = np.full(YEARS + 1, 28000000.0)

# Impuestos Base
IMP_IVA_BASE = np.array([0, 2656972281.01, 3832134507.98, 3220383801.65, 3365802350.98, 3516125830.45, 1929348223.21, 
                         1093765562.35, 1246336396.43, 2607401859.65, 3070243633.56, 2247211076.91, 3408681721.26, 
                         2833104693.61, 3015282248.42, 4192675956.32, 4385948124.22, 4822320843.51, 5027363286.43, 
                         5238557002.64, 5238557002.64], dtype=float)

IMP_GANANCIAS_BASE = np.array([0, 3901238045.30, 5527661023.34, 5495218647.32, 5469810984.91, 5591266769.29, 5212052382.37, 
                               4958490406.28, 4950638227.15, 5351380801.76, 5859957421.65, 6627083002.42, 7402173381.82, 
                               7934651357.11, 8074273352.54, 8122272239.79, 8116531541.40, 7597490588.60, 6920749257.43, 
                               4999722890.45, 4999722890.45], dtype=float)

IMP_IB_BASE = np.array([0, 507046315.74, 522257705.21, 537925436.36, 554063199.46, 570685095.44, 587805648.30, 
                        605439817.75, 623603012.28, 642311102.65, 661580435.73, 681427848.80, 701870684.27, 
                        722926804.80, 744614608.94, 766953047.21, 789961638.62, 813660487.78, 838070302.42, 
                        863212411.49, 863212411.49], dtype=float)

IMP_MUNICIPAL_BASE = IMP_IB_BASE * 0.2 # Proporción simplificada basada en alícuotas

IMP_SELLOS_BASE = np.array([398790269.26]*5 + [0]*16, dtype=float)
IMP_DBCR_BASE = np.array([24279003.00, 294492500.18, 303327275.18, 312427093.44, 321799906.24, 331453903.43, 341397520.53, 
                          351639446.15, 362188629.53, 373054288.42, 384245917.07, 395773294.59, 407646493.42, 
                          419875888.23, 432472164.87, 445446329.82, 458809719.71, 472574011.30, 486751231.64, 
                          501353768.59, 501353768.59], dtype=float)

AL_GANANCIAS_BASE, AL_IB_BASE, AL_MUNICIPAL_BASE = 0.35, 0.025, 0.005
AL_SELLOS_BASE, AL_DBCR_BASE, AL_IVA_BASE = 0.012, 0.012, 0.21
AL_IVA_GASTOS_BASE = 0.11

INGRESO_CREDITO = np.zeros(YEARS + 1)
INGRESO_CREDITO[0] = 2023250250.0

MIRR_BASE, VAN_BASE, VAFF_VAE_BASE, TASA_VAN_BASE = 0.2330, 47639480891.0, 0.2624, 0.10


# ══════════════════════════════════════════════════════════════
# 2.  MODELO DE SENSIBILIDAD
# ══════════════════════════════════════════════════════════════

def run_model(delta_capex_obras=0.0, delta_capex_repav=0.0, delta_opex=0.0, delta_trafico=0.0, 
              tarifa=TARIFA_BASE, al_ganancias=AL_GANANCIAS_BASE, al_ib=AL_IB_BASE, 
              al_municipal=AL_MUNICIPAL_BASE, al_sellos=AL_SELLOS_BASE, al_dbcr=AL_DBCR_BASE, 
              al_iva_peaje=AL_IVA_BASE, tasa_van=TASA_VAN_BASE):
    
    uteq = np.zeros(YEARS + 1)
    tasa_eff = max(TRAFICO_CRECIMIENTO_BASE + delta_trafico, -0.50)
    uteq[1] = UTEQ_ARRANQUE
    for y in range(2, YEARS + 1):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    peaje = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        peaje[y] = uteq[y] * tarifa

    uteq_ref_for_tax = np.where(UTEQ_ARRANQUE > 0, uteq / UTEQ_ARRANQUE, 1.0)
    total_ingresos = peaje + INGRESO_CREDITO

    OBRAS_OBLIG = np.array([0,0,0,0,0,0, 5702850000, 11405700000, 11405700000, 11405700000, 
                            11405700000, 17108550000, 11405700000, 11405700000, 11405700000, 
                            5702850000, 5702850000, 0,0,0,0], dtype=float)
    REPAV = np.array([0,0,0, 4335536250, 4335536250, 4335536250, 8671072500, 8671072500, 
                      8671072500, 1734214500, 0,0,0, 4335536250, 4335536250, 4335536250, 
                      4335536250, 8671072500, 8671072500, 8671072500, 8671072500], dtype=float)
    PUESTA_VALOR = np.array([2890357500.0] + [0]*20, dtype=float)

    capex = PUESTA_VALOR + OBRAS_OBLIG * (1 + delta_capex_obras) + REPAV * (1 + delta_capex_repav)
    opex = OPEX_BASE * (1 + delta_opex)

    factor_tarifa = tarifa / TARIFA_BASE
    factor_trafico_avg = uteq_ref_for_tax * factor_tarifa
    
    imp_iva = IMP_IVA_BASE * factor_trafico_avg * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib = IMP_IB_BASE * factor_trafico_avg * (al_ib / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE * factor_trafico_avg * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos = IMP_SELLOS_BASE * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr = IMP_DBCR_BASE * factor_trafico_avg * (al_dbcr / AL_DBCR_BASE)

    # Cálculo Impuesto Ganancias
    bi_base = np.where(AL_GANANCIAS_BASE > 0, IMP_GANANCIAS_BASE / AL_GANANCIAS_BASE, 0.0)
    bi_var_base = bi_base + (OPEX_BASE / (1 + AL_IVA_GASTOS_BASE) + GARANTIAS)

    factor_traf_base = np.zeros(YEARS + 1)
    factor_traf_base[1] = 1.0
    for y in range(2, YEARS + 1):
        factor_traf_base[y] = factor_traf_base[y - 1] * (1 + TRAFICO_CRECIMIENTO_BASE)

    # Corrección RuntimeWarning: Usamos np.divide con where
    fi_rel = np.divide(factor_trafico_avg, factor_traf_base, out=np.ones_like(factor_trafico_avg), where=factor_traf_base != 0)

    base_imponible = bi_var_base * fi_rel - (opex / (1 + AL_IVA_GASTOS_BASE) + GARANTIAS)
    quebranto_acum, imp_ganancias = np.zeros(YEARS + 1), np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        base_y = base_imponible[y] + quebranto_acum[y - 1]
        if base_y <= 0:
            quebranto_acum[y] = base_y
        else:
            imp_ganancias[y] = base_y * al_ganancias

    total_impuestos = imp_iva + imp_ganancias + imp_ib + imp_municipal + imp_sellos + imp_dbcr
    total_egresos = capex + opex + AMORT_DEUDA_BASE + total_impuestos + GARANTIAS
    flujo = total_ingresos - total_egresos

    van = _npv(tasa_van, flujo)
    van_egr = _npv(tasa_van, total_egresos)
    van_ing = _npv(tasa_van, total_ingresos)
    vaff_vae = van / van_egr if van_egr != 0 else float("nan")
    mirr_val = _mirr(flujo, tasa_van)
    acum = np.cumsum(flujo)
    inversion_obras = float(np.sum(PUESTA_VALOR) + np.sum(OBRAS_OBLIG * (1 + delta_capex_obras)))
    payback = next((y for y, v in enumerate(acum) if v >= inversion_obras), None)

    return locals()


# ══════════════════════════════════════════════════════════════
# 3.  APP STREAMLIT
# ══════════════════════════════════════════════════════════════

st.set_page_config(page_title="CAUCETE – Sensibilidades", page_icon="🛣️", layout="wide")

st.markdown("""
<style>
.kpi { background: #1c2230; border: 1px solid #2d3650; border-radius: 12px; padding: 15px; text-align: center; }
.val { color: #dce4f0; font-size: 1.5rem; font-weight: 700; }
.pos { color: #3ecf8e; } .neg { color: #f76e6e; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🛣️ Parámetros")
    tarifa_input = st.number_input("Tarifa (sin IVA)", value=int(TARIFA_BASE), step=500)
    delta_trafico_pp = st.slider("Δ Tránsito (±pp)", -3.0, 5.0, 0.0, 0.5) / 100
    delta_obras = st.slider("Obras (%)", -40, 100, 0, 5) / 100
    delta_repav = st.slider("Repavim. (%)", -40, 100, 0, 5) / 100
    delta_opex = st.slider("OPEX (%)", -40, 100, 0, 5) / 100
    al_ganancias = st.slider("Ganancias (%)", 0, 55, 35, 5) / 100
    tasa_van = st.slider("Descuento (%)", 5, 25, 10, 1) / 100

sc = run_model(delta_capex_obras=delta_obras, delta_capex_repav=delta_repav, delta_opex=delta_opex, 
               delta_trafico=delta_trafico_pp, tarifa=float(tarifa_input), al_ganancias=al_ganancias, tasa_van=tasa_van)

YEARS_RANGE = list(range(2025, 2025 + YEARS + 1))

# Configuración base de Plotly (Sin MARGIN para evitar TypeError)
PL_BASE = dict(
    plot_bgcolor="#181e2d", paper_bgcolor="#181e2d",
    font=dict(color="#c5cdd8", size=12),
    xaxis=dict(gridcolor="#252f45", zeroline=False),
    yaxis=dict(gridcolor="#252f45", zeroline=False),
)

st.markdown("# 🛣️ Análisis de Sensibilidades — CAUCETE")
c1, c2, c3, c4 = st.columns(4)
c1.metric("VAN", f"$ {sc['van']/1e9:.1f} MM")
c2.metric("MIRR", f"{sc['mirr']:.2%}")
c3.metric("VAFF/VAE", f"{sc['vaff_vae']:.4f}")
c4.metric("Payback", f"Año {sc['payback']}" if sc['payback'] else "N/D")

tab1, tab2, tab3 = st.tabs(["📊 Flujos", "🌪️ Tornado", "🔥 Mapas"])

with tab1:
    fig = make_subplots(rows=1, cols=2, subplot_titles=["Flujo Anual", "Acumulado"])
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["flujo"]/1e9, name="Neto"), row=1, col=1)
    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["acum"]/1e9, name="Acum", fill="tozeroy"), row=1, col=2)
    fig.update_layout(**PL_BASE, margin=dict(t=40, b=40, l=50, r=20), height=400)
    st.plotly_chart(fig, width="stretch") # Actualizado de use_container_width

with tab2:
    shocks = {"Obras +20%": {"delta_capex_obras": delta_obras+0.2}, "Tarifa -20%": {"tarifa": tarifa_input*0.8}}
    t_rows = []
    for label, v in shocks.items():
        base_kw = {"delta_capex_obras": delta_obras, "tarifa": float(tarifa_input), "tasa_van": tasa_van}
        r = run_model(**{**base_kw, **v})
        t_rows.append({"Variable": label, "ΔVAN": (r["van"] - sc["van"])/1e9})
    
    df_t = pd.DataFrame(t_rows).sort_values("ΔVAN")
    fig2 = go.Figure(go.Bar(x=df_t["ΔVAN"], y=df_t["Variable"], orientation="h"))
    # Corrección TypeError: margin definido solo una vez
    fig2.update_layout(**PL_BASE, height=400, margin=dict(l=150, r=20, t=30, b=30))
    st.plotly_chart(fig2, width="stretch")

with tab3:
    # Ejemplo de Mapa de Calor con corrección de margen
    st.markdown("#### Sensibilidad MIRR: Tránsito vs CAPEX")
    tr_rng = np.arange(-0.02, 0.03, 0.01)
    cp_rng = np.arange(-0.2, 0.3, 0.1)
    mat = [[run_model(delta_trafico=t, delta_capex_obras=c)["mirr"]*100 for c in cp_rng] for t in tr_rng]
    
    fig4 = go.Figure(go.Heatmap(z=mat, x=cp_rng, y=tr_rng, colorscale="RdYlGn"))
    fig4.update_layout(**PL_BASE, margin=dict(t=30, b=60, l=100, r=20), height=350,
                       xaxis_title="Var. CAPEX", yaxis_title="Δ Tránsito")
    st.plotly_chart(fig4, width="stretch")