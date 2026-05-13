import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ═════════════════════════════════════════════════════
# CONFIG STREAMLIT
# ═════════════════════════════════════════════════════

st.set_page_config(
    page_title="Modelo Financiero CAUCETE",
    layout="wide"
)

# ═════════════════════════════════════════════════════
# CONSTANTES BASE
# ═════════════════════════════════════════════════════

YEARS = 20

TARIFA_BASE = 3000
UTEQ_ARRANQUE = 1_000_000

TRAFICO_CRECIMIENTO_BASE = 0.03

AL_IVA_BASE = 0.21
AL_GANANCIAS_BASE = 0.35
AL_IB_BASE = 0.03
AL_MUNICIPAL_BASE = 0.01
AL_SELLOS_BASE = 0.01
AL_DBCR_BASE = 0.006

TASA_VAN_BASE = 0.12

# ═════════════════════════════════════════════════════
# BASES FINANCIERAS
# ═════════════════════════════════════════════════════

INGRESO_CREDITO = np.array(
    [15_000_000_000] + [0] * YEARS,
    dtype=float
)

OPEX_BASE = np.array(
    [0] + [2_000_000_000] * YEARS,
    dtype=float
)

AMORT_DEUDA_BASE = np.array(
    [0] + [1_000_000_000] * YEARS,
    dtype=float
)

GARANTIAS = np.array(
    [0] + [150_000_000] * YEARS,
    dtype=float
)

IMP_IVA_BASE = np.array(
    [0] + [600_000_000] * YEARS,
    dtype=float
)

IMP_GANANCIAS_BASE = np.array(
    [0] + [500_000_000] * YEARS,
    dtype=float
)

IMP_IB_BASE = np.array(
    [0] + [120_000_000] * YEARS,
    dtype=float
)

IMP_MUNICIPAL_BASE = np.array(
    [0] + [50_000_000] * YEARS,
    dtype=float
)

IMP_SELLOS_BASE = np.array(
    [0] + [40_000_000] * YEARS,
    dtype=float
)

IMP_DBCR_BASE = np.array(
    [0] + [30_000_000] * YEARS,
    dtype=float
)

# ═════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═════════════════════════════════════════════════════

def _npv(rate, cashflows):
    return sum(
        cf / ((1 + rate) ** i)
        for i, cf in enumerate(cashflows)
    )

def _mirr(cashflows, finance_rate):
    positivos = []
    negativos = []

    for i, cf in enumerate(cashflows):
        if cf > 0:
            positivos.append(cf * ((1 + finance_rate) ** (YEARS - i)))
        elif cf < 0:
            negativos.append(cf / ((1 + finance_rate) ** i))

    pv_neg = abs(sum(negativos))
    fv_pos = sum(positivos)

    if pv_neg == 0:
        return np.nan

    return (fv_pos / pv_neg) ** (1 / YEARS) - 1

# ═════════════════════════════════════════════════════
# MODELO PRINCIPAL
# ═════════════════════════════════════════════════════

def run_model(
    delta_capex_obras=0.0,
    delta_capex_repav=0.0,
    delta_opex=0.0,
    delta_trafico=0.0,
    tarifa=TARIFA_BASE,
    al_ganancias=AL_GANANCIAS_BASE,
    al_ib=AL_IB_BASE,
    al_municipal=AL_MUNICIPAL_BASE,
    al_sellos=AL_SELLOS_BASE,
    al_dbcr=AL_DBCR_BASE,
    al_iva_peaje=AL_IVA_BASE,
    tasa_van=TASA_VAN_BASE,
):

    # ════════════════════════════════════════════════
    # TRÁFICO
    # ════════════════════════════════════════════════

    uteq = np.zeros(YEARS + 1)

    uteq[0] = 0
    uteq[1] = UTEQ_ARRANQUE

    tasa_eff = TRAFICO_CRECIMIENTO_BASE + delta_trafico
    tasa_eff = max(tasa_eff, -0.50)

    for y in range(2, YEARS + 1):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    # ════════════════════════════════════════════════
    # INGRESOS PEAJE
    # ════════════════════════════════════════════════

    tarifa_con_iva = tarifa * (1 + al_iva_peaje)

    peaje = np.zeros(YEARS + 1)

    for y in range(1, YEARS + 1):
        peaje[y] = uteq[y] * tarifa_con_iva

    total_ingresos = peaje + INGRESO_CREDITO

    # ════════════════════════════════════════════════
    # CAPEX
    # ════════════════════════════════════════════════

    OBRAS_OBLIG = np.array([
        0,0,0,0,0,0,
        5_702_850_000,
        11_405_700_000,
        11_405_700_000,
        11_405_700_000,
        11_405_700_000,
        17_108_550_000,
        11_405_700_000,
        11_405_700_000,
        11_405_700_000,
        5_702_850_000,
        5_702_850_000,
        0,0,0,0
    ], dtype=float)

    REPAV = np.array([
        0,0,0,
        4_335_536_250,
        4_335_536_250,
        4_335_536_250,
        8_671_072_500,
        8_671_072_500,
        8_671_072_500,
        1_734_214_500,
        0,0,0,
        4_335_536_250,
        4_335_536_250,
        4_335_536_250,
        4_335_536_250,
        8_671_072_500,
        8_671_072_500,
        8_671_072_500,
        8_671_072_500
    ], dtype=float)

    PUESTA_VALOR = np.array(
        [2_890_357_500] + [0] * YEARS,
        dtype=float
    )

    capex = (
        PUESTA_VALOR
        + OBRAS_OBLIG * (1 + delta_capex_obras)
        + REPAV * (1 + delta_capex_repav)
    )

    # ════════════════════════════════════════════════
    # OPEX
    # ════════════════════════════════════════════════

    opex = OPEX_BASE * (1 + delta_opex)

    # ════════════════════════════════════════════════
    # FACTOR IMPUESTOS
    # ════════════════════════════════════════════════

    uteq_ref_for_tax = np.zeros(YEARS + 1)

    for y in range(1, YEARS + 1):
        uteq_ref_for_tax[y] = (
            uteq[y] / UTEQ_ARRANQUE
        )

    factor_tarifa = tarifa / TARIFA_BASE
    factor_trafico_avg = uteq_ref_for_tax * factor_tarifa

    imp_iva = (
        IMP_IVA_BASE
        * factor_trafico_avg
        * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    )

    imp_ganancias = (
        IMP_GANANCIAS_BASE
        * factor_trafico_avg
        * (al_ganancias / AL_GANANCIAS_BASE)
    )

    imp_ib = (
        IMP_IB_BASE
        * factor_trafico_avg
        * (al_ib / AL_IB_BASE)
    )

    imp_municipal = (
        IMP_MUNICIPAL_BASE
        * factor_trafico_avg
        * (al_municipal / AL_MUNICIPAL_BASE)
    )

    imp_sellos = (
        IMP_SELLOS_BASE
        * (al_sellos / AL_SELLOS_BASE)
    )

    imp_dbcr = (
        IMP_DBCR_BASE
        * factor_trafico_avg
        * (al_dbcr / AL_DBCR_BASE)
    )

    total_impuestos = (
        imp_iva
        + imp_ganancias
        + imp_ib
        + imp_municipal
        + imp_sellos
        + imp_dbcr
    )

    # ════════════════════════════════════════════════
    # EGRESOS
    # ════════════════════════════════════════════════

    total_egresos = (
        capex
        + opex
        + AMORT_DEUDA_BASE
        + total_impuestos
        + GARANTIAS
    )

    # ════════════════════════════════════════════════
    # FLUJO
    # ════════════════════════════════════════════════

    flujo = total_ingresos - total_egresos

    acum = np.cumsum(flujo)

    # ════════════════════════════════════════════════
    # KPIs
    # ════════════════════════════════════════════════

    van = _npv(tasa_van, flujo)

    mirr_val = _mirr(flujo, tasa_van)

    # ════════════════════════════════════════════════
    # DATAFRAME
    # ════════════════════════════════════════════════

    df = pd.DataFrame({
        "Año": np.arange(YEARS + 1),
        "UTEQ": uteq,
        "Peaje": peaje,
        "Ingresos": total_ingresos,
        "Capex": capex,
        "Opex": opex,
        "Impuestos": total_impuestos,
        "Egresos": total_egresos,
        "Flujo": flujo,
        "Acumulado": acum,
    })

    return df, van, mirr_val

# ═════════════════════════════════════════════════════
# RUN
# ═════════════════════════════════════════════════════

df, van, mirr_val = run_model()

# ═════════════════════════════════════════════════════
# STREAMLIT UI
# ═════════════════════════════════════════════════════

st.title("Modelo Financiero CAUCETE")

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "VAN",
        f"${van:,.0f}"
    )

with col2:
    st.metric(
        "MIRR",
        f"{mirr_val:.2%}"
    )

st.dataframe(df, use_container_width=True)

# ═════════════════════════════════════════════════════
# GRÁFICO
# ═════════════════════════════════════════════════════

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=df["Año"],
        y=df["Flujo"],
        mode="lines+markers",
        name="Flujo"
    )
)

st.plotly_chart(
    fig,
    use_container_width=True
)
