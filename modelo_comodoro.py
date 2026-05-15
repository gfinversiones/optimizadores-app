"""
COMODORO RADA TILLI – Panel de Sensibilidades Financieras
==========================================================
Replicación fiel del modelo COMODORO_-_RADA_-_TILLI.xlsx.

El modelo NO recalcula el préstamo ni usa WACC.
Los flujos base se toman directamente del xlsx y se
escalan con los factores de sensibilidad ingresados.

Instalación:
    pip install streamlit pandas plotly

Ejecución:
    streamlit run modelo_comodoro.py
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ══════════════════════════════════════════════════════════════
# 0.  FUNCIONES FINANCIERAS PURAS (sin librerías externas)
# ══════════════════════════════════════════════════════════════

def _npv(rate: float, cf: np.ndarray) -> float:
    t = np.arange(len(cf), dtype=float)
    return float(np.sum(cf / (1.0 + rate) ** t))


def _mirr(cf: np.ndarray, reinvest_rate: float) -> float:
    """
    MIRR según la definición del xlsx:
      - flujos negativos descontados a la tasa de reinversión (tasa de descuento)
      - flujos positivos llevados al valor futuro a la misma tasa
    (no hay tasa de financiamiento separada)
    """
    n = len(cf) - 1
    neg = np.where(cf < 0, cf, 0.0)
    pos = np.where(cf > 0, cf, 0.0)
    pv_neg = sum(neg[t] / (1 + reinvest_rate) ** t for t in range(n + 1))
    fv_pos = sum(pos[t] * (1 + reinvest_rate) ** (n - t) for t in range(n + 1))
    if pv_neg >= 0 or fv_pos <= 0:
        return float("nan")
    return (fv_pos / (-pv_neg)) ** (1.0 / n) - 1.0


# ══════════════════════════════════════════════════════════════
# 1.  DATOS BASE  (extraídos del xlsx COMODORO RADA TILLI)
# ══════════════════════════════════════════════════════════════
#
# Años de concesión: 1-20 (2026-2045).
# Índice 0 = año inicio concesión (Y0: puesta en valor + crédito).
# Los arrays tienen 21 elementos [0..20].

YEARS = 20

# ── Ingresos de peaje con IVA (del sheet FLUJO, fila "Peajes") ──
# Y0: sin ingresos (puesta en valor). Y1..Y20: valores del xlsx.
PEAJE_BASE = np.array([
    0,                       # Y0
    33_992_053_051.20,       # Y1  2026
    35_011_814_642.73,       # Y2  2027
    36_062_169_082.02,       # Y3  2028
    37_144_034_154.48,       # Y4  2029
    38_258_355_179.11,       # Y5  2030
    39_406_105_834.48,       # Y6  2031
    40_588_289_009.52,       # Y7  2032
    41_805_937_679.80,       # Y8  2033
    43_060_115_810.20,       # Y9  2034
    44_351_919_284.50,       # Y10 2035
    45_682_476_863.04,       # Y11 2036
    47_052_951_168.93,       # Y12 2037
    48_464_539_703.00,       # Y13 2038
    49_918_475_895.12,       # Y14 2039
    51_416_030_171.97,       # Y15 2040
    52_958_511_077.13,       # Y16 2041
    54_547_266_409.44,       # Y17 2042
    56_183_684_401.73,       # Y18 2043
    57_869_194_933.78,       # Y19 2044
    57_869_194_933.78,       # Y20 2045 (extrap. igual a Y19)
], dtype=float)

# ── Tarifa base y tránsito ──────────────────────────────────────
# Tarifa base sin IVA: $6.000 por UTEQ (del xlsx, fila 111)
TARIFA_BASE = 6_000.0          # ARS por UTEQ, sin IVA
TARIFA_IVA  = TARIFA_BASE * 1.21

# UTEQ arranque: tránsito real del xlsx año 1 (5 categorías)
UTEQ_ARRANQUE = 5_500_332.21   # UTEQs (del xlsx, fila "UTEQUIS 5 Cat")

# Crecimiento base: 5% Y1→Y2, luego 3% anual (del xlsx fila "Tránsitos Crecimiento Anual")
TRAFICO_CRECIMIENTO_BASE = 0.03

# ── CAPEX (del sheet FLUJO, filas de CAPEX) ────────────────────
# Puesta en valor solo Y0; Obras Obligatorias Y6-Y16; Repavimentación varios años
PUESTA_VALOR_BASE = np.array([
    5_565_607_500.00, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

OBRAS_OBLIG_BASE = np.array([
    0, 0, 0, 0, 0, 0,
    9_773_217_500.00,   # Y6
    19_546_435_000.00,  # Y7
    19_546_435_000.00,  # Y8
    19_546_435_000.00,  # Y9
    19_546_435_000.00,  # Y10
    29_319_652_500.00,  # Y11
    19_546_435_000.00,  # Y12
    19_546_435_000.00,  # Y13
    19_546_435_000.00,  # Y14
    9_773_217_500.00,   # Y15
    9_773_217_500.00,   # Y16
    0, 0, 0, 0,
], dtype=float)

REPAV_BASE = np.array([
    0, 0, 0,
    8_348_411_250.00,   # Y3
    8_348_411_250.00,   # Y4
    8_348_411_250.00,   # Y5
    16_696_822_500.00,  # Y6
    16_696_822_500.00,  # Y7
    16_696_822_500.00,  # Y8
    3_339_364_500.00,   # Y9
    0, 0, 0,
    8_348_411_250.00,   # Y13
    8_348_411_250.00,   # Y14
    8_348_411_250.00,   # Y15
    8_348_411_250.00,   # Y16
    16_696_822_500.00,  # Y17
    16_696_822_500.00,  # Y18
    16_696_822_500.00,  # Y19
    16_696_822_500.00,  # Y20
], dtype=float)

CAPEX_BASE = PUESTA_VALOR_BASE + OBRAS_OBLIG_BASE + REPAV_BASE

# ── OPEX con IVA – Conservación y Mantenimiento ────────────────
OPEX_BASE = np.full(YEARS + 1, 7_420_810_000.00)

# ── Amortización deuda (del sheet FLUJO) ────────────────────────
AMORT_DEUDA_BASE = np.array([
    0,                    # Y0
    894_532_036.10,       # Y1
    855_572_783.60,       # Y2
    855_572_783.60,       # Y3
    855_572_783.60,       # Y4
    855_572_783.60,       # Y5
    855_572_783.60,       # Y6
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# ── Garantías anuales ──────────────────────────────────────────
GARANTIAS = np.full(YEARS + 1, 51_000_000.0)

# ── Impuestos BASE por componente (del sheet FLUJO detallado) ──

IMP_IVA_BASE = np.array([
    0,
    2_815_266_811.17,   # Y1
    5_008_568_147.89,   # Y2
    3_759_464_420.72,   # Y3
    3_966_214_901.16,   # Y4
    4_180_212_278.56,   # Y5
    1_256_686_668.30,   # Y6
    0,                  # Y7
    0,                  # Y8
    2_290_498_898.23,   # Y9
    3_328_301_070.58,   # Y10
    1_863_046_042.88,   # Y11
    3_797_075_199.28,   # Y12
    2_593_163_819.00,   # Y13
    2_845_499_852.17,   # Y14
    4_801_584_210.14,   # Y15
    5_069_287_507.73,   # Y16
    5_592_302_327.80,   # Y17
    5_876_308_756.21,   # Y18
    6_168_835_377.48,   # Y19
    6_168_835_377.48,   # Y20 (extrap.)
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,
    3_881_942_740.83,   # Y1
    6_885_979_114.15,   # Y2
    6_710_236_165.71,   # Y3
    6_544_640_924.71,   # Y4
    6_641_569_416.74,   # Y5
    5_812_546_605.93,   # Y6
    5_196_804_006.80,   # Y7
    5_050_369_994.83,   # Y8
    5_686_777_444.84,   # Y9
    6_526_770_107.46,   # Y10
    7_860_439_511.84,   # Y11
    9_205_141_041.95,   # Y12
    10_078_239_721.47,  # Y13
    10_190_296_879.04,  # Y14
    10_121_222_762.23,  # Y15
    9_943_823_915.09,   # Y16
    8_773_035_283.46,   # Y17
    7_293_442_293.49,   # Y18
    3_412_587_726.23,   # Y19
    3_412_587_726.23,   # Y20 (extrap.)
], dtype=float)

IMP_IB_BASE = np.array([
    0,
    702_315_145.69,     # Y1
    723_384_600.06,     # Y2
    745_086_138.06,     # Y3
    767_438_722.20,     # Y4
    790_461_883.87,     # Y5
    814_175_740.38,     # Y6
    838_601_012.59,     # Y7
    863_759_042.97,     # Y8
    889_671_814.26,     # Y9
    916_361_968.69,     # Y10
    943_852_827.75,     # Y11
    972_168_412.58,     # Y12
    1_001_333_464.96,   # Y13
    1_031_373_468.91,   # Y14
    1_062_314_672.97,   # Y15
    1_094_184_113.16,   # Y16
    1_127_009_636.56,   # Y17
    1_160_819_925.66,   # Y18
    1_195_644_523.43,   # Y19
    1_195_644_523.43,   # Y20 (extrap.)
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,
    140_463_029.14,     # Y1
    144_676_920.01,     # Y2
    149_017_227.61,     # Y3
    153_487_744.44,     # Y4
    158_092_376.77,     # Y5
    162_835_148.08,     # Y6
    167_720_202.52,     # Y7
    172_751_808.59,     # Y8
    177_934_362.85,     # Y9
    183_272_393.74,     # Y10
    188_770_565.55,     # Y11
    194_433_682.52,     # Y12
    200_266_692.99,     # Y13
    206_274_693.78,     # Y14
    212_462_934.59,     # Y15
    218_836_822.63,     # Y16
    225_401_927.31,     # Y17
    232_163_985.13,     # Y18
    239_128_904.69,     # Y19
    239_128_904.69,     # Y20 (extrap.)
], dtype=float)

IMP_SELLOS_BASE = np.array([
    719_978_451.07,   # Y0
    719_978_451.07,   # Y1
    719_978_451.07,   # Y2
    719_978_451.07,   # Y3
    719_978_451.07,   # Y4
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

IMP_DBCR_BASE = np.array([
    46_751_103.00,      # Y0
    407_904_636.61,     # Y1
    420_141_775.71,     # Y2
    432_746_028.98,     # Y3
    445_728_409.85,     # Y4
    459_100_262.15,     # Y5
    472_873_270.01,     # Y6
    487_059_468.11,     # Y7
    501_671_252.16,     # Y8
    516_721_389.72,     # Y9
    532_223_031.41,     # Y10
    548_189_722.36,     # Y11
    564_635_414.03,     # Y12
    581_574_476.45,     # Y13
    599_021_710.74,     # Y14
    616_992_362.06,     # Y15
    635_502_132.93,     # Y16
    654_567_196.91,     # Y17
    674_204_212.82,     # Y18
    694_430_339.21,     # Y19
    694_430_339.21,     # Y20 (extrap.)
], dtype=float)

# Alícuotas base (para escalar proporcionalmente)
AL_GANANCIAS_BASE = 0.35
AL_IB_BASE        = 0.025
AL_MUNICIPAL_BASE = 0.005
AL_SELLOS_BASE    = 0.012
AL_DBCR_BASE      = 0.012
AL_IVA_BASE       = 0.21     # IVA del peaje (21%)

# Ingresos crédito LP (solo Y0) – del xlsx fila "Ingresos Crédito LP"
INGRESO_CREDITO = np.zeros(YEARS + 1)
INGRESO_CREDITO[0] = 3_895_925_250.0

# KPIs del xlsx (para mostrar delta vs base)
# TIR nominal = 143.1%, VAN al 10% = 35.39 MM, VAN/VAE = 0.1250
MIRR_BASE     = 1.43106        # TIR nominal del xlsx (usada como referencia)
VAN_BASE      = 35_389_864_510.02
VAFF_VAE_BASE = 0.1250
TASA_VAN_BASE = 0.10


# ══════════════════════════════════════════════════════════════
# 2.  MODELO DE SENSIBILIDAD
# ══════════════════════════════════════════════════════════════

def run_model(
    delta_capex_obras   = 0.0,   # % variación obras obligatorias
    delta_capex_repav   = 0.0,   # % variación repavimentación
    delta_opex          = 0.0,   # % variación OPEX total
    delta_trafico       = 0.0,   # delta pp sobre tasa crecimiento base (Y3+)
    tarifa              = TARIFA_BASE,   # tarifa sin IVA (ARS por UTEQ)
    al_ganancias        = AL_GANANCIAS_BASE,
    al_ib               = AL_IB_BASE,
    al_municipal        = AL_MUNICIPAL_BASE,
    al_sellos           = AL_SELLOS_BASE,
    al_dbcr             = AL_DBCR_BASE,
    al_iva_peaje        = AL_IVA_BASE,
    tasa_van            = TASA_VAN_BASE,
):
    # ── Tráfico ─────────────────────────────────────────────────
    # Y0: 0 (puesta en valor, sin operación)
    # Y1: tránsito de arranque (5.500.332 UTEQs) → SÍ genera ingresos
    # Y2: Y1 × 1.05 (crecimiento fijo del 5%)
    # Y3+: crece a tasa_base 3% + delta_trafico cada año
    uteq = np.zeros(YEARS + 1)
    uteq[0] = 0.0
    uteq[1] = UTEQ_ARRANQUE                       # Y1: arranque con cobro
    uteq[2] = UTEQ_ARRANQUE * 1.05                # Y2: +5% fijo
    tasa_eff = TRAFICO_CRECIMIENTO_BASE + delta_trafico
    tasa_eff = max(tasa_eff, -0.50)
    for y in range(3, YEARS + 1):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    # ── Ingresos de peaje ───────────────────────────────────────
    # Ingreso = UTEQ × tarifa × (1 + IVA)
    # Y0: 0 (sin operación). Y1+: con cobro de peaje.
    tarifa_con_iva = tarifa * (1 + al_iva_peaje)
    peaje = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        peaje[y] = uteq[y] * tarifa_con_iva

    # Factor de tráfico vs base (para escalar impuestos proporcionales)
    # Referencia: UTEQ_ARRANQUE (año 1 base)
    uteq_ref_for_tax = np.zeros(YEARS + 1)
    uteq_ref_for_tax[0] = 0.0
    for y in range(1, YEARS + 1):
        uteq_ref_for_tax[y] = uteq[y] / UTEQ_ARRANQUE if UTEQ_ARRANQUE > 0 else 1.0

    total_ingresos = peaje + INGRESO_CREDITO

    # ── CAPEX escalado ──────────────────────────────────────────
    # Puesta en valor (Y0) sin sensibilidad.
    # Obras obligatorias y repavimentación escaladas por sus deltas.
    OBRAS_OBLIG = OBRAS_OBLIG_BASE
    REPAV       = REPAV_BASE
    PUESTA_VALOR = PUESTA_VALOR_BASE

    capex = (PUESTA_VALOR
             + OBRAS_OBLIG * (1 + delta_capex_obras)
             + REPAV       * (1 + delta_capex_repav))

    # ── OPEX escalado ───────────────────────────────────────────
    opex = OPEX_BASE * (1 + delta_opex)

    # ── Impuestos escalados ─────────────────────────────────────
    # factor_trafico: variación de volumen respecto al año base de cobro (Y2).
    # Para Y0 y Y1: 0 (sin ingresos de peaje → sin impuestos sobre peaje).
    # La tarifa también modifica la base imponible: factor_tarifa = tarifa / TARIFA_BASE.
    factor_tarifa   = tarifa / TARIFA_BASE
    factor_trafico_avg = uteq_ref_for_tax * factor_tarifa
    # Para IVA el ingreso base cambia tanto por tráfico como por alícuota
    imp_iva      = IMP_IVA_BASE * factor_trafico_avg * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ganancias = IMP_GANANCIAS_BASE * factor_trafico_avg * (al_ganancias / AL_GANANCIAS_BASE)
    imp_ib        = IMP_IB_BASE        * factor_trafico_avg * (al_ib        / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE * factor_trafico_avg * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos    = IMP_SELLOS_BASE    * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr      = IMP_DBCR_BASE      * factor_trafico_avg * (al_dbcr     / AL_DBCR_BASE)

    total_impuestos = imp_iva + imp_ganancias + imp_ib + imp_municipal + imp_sellos + imp_dbcr

    # ── Egresos totales ─────────────────────────────────────────
    total_egresos = capex + opex + AMORT_DEUDA_BASE + total_impuestos + GARANTIAS

    # ── Flujo neto ──────────────────────────────────────────────
    flujo = total_ingresos - total_egresos

    # ── Métricas ────────────────────────────────────────────────
    van       = _npv(tasa_van, flujo)
    van_egr   = _npv(tasa_van, total_egresos)
    van_ing   = _npv(tasa_van, total_ingresos)
    vaff_vae  = van / van_egr if van_egr != 0 else float("nan")
    mirr_val  = _mirr(flujo, tasa_van)
    acum      = np.cumsum(flujo)

    # Payback de obras: año en que el flujo acumulado cubre
    # la inversión total en obras (puesta en valor + obras obligatorias).
    # La repavimentación NO se incluye por definición del indicador.
    inversion_obras = float(np.sum(PUESTA_VALOR) + np.sum(OBRAS_OBLIG * (1 + delta_capex_obras)))
    payback   = next((y for y, v in enumerate(acum) if v >= inversion_obras), None)

    return dict(
        flujo         = flujo,
        total_ing     = total_ingresos,
        total_egr     = total_egresos,
        peaje         = peaje,
        capex         = capex,
        opex          = opex,
        amort_deuda   = AMORT_DEUDA_BASE.copy(),
        imp_iva       = imp_iva,
        imp_ganancias = imp_ganancias,
        imp_ib        = imp_ib,
        imp_municipal = imp_municipal,
        imp_sellos    = imp_sellos,
        imp_dbcr      = imp_dbcr,
        total_imp     = total_impuestos,
        acum          = acum,
        van           = van,
        van_ing       = van_ing,
        van_egr       = van_egr,
        vaff_vae      = vaff_vae,
        mirr            = mirr_val,
        payback         = payback,
        inversion_obras = inversion_obras,
        uteq            = uteq,
    )


# ══════════════════════════════════════════════════════════════
# 3.  APP STREAMLIT
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="COMODORO RADA TILLI – Sensibilidades",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main { background: #0e1117; }
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; }

/* KPI cards */
.kpi {
  background: linear-gradient(135deg, #1c2230, #222a3c);
  border: 1px solid #2d3650;
  border-radius: 12px;
  padding: 16px 20px;
  text-align: center;
  margin-bottom: 6px;
}
.kpi .lbl  { color: #7a869a; font-size: .72rem; text-transform: uppercase;
             letter-spacing: .09em; margin-bottom: 3px; }
.kpi .val  { color: #dce4f0; font-size: 1.55rem; font-weight: 700; }
.kpi .dlt  { font-size: .76rem; margin-top: 2px; }
.kpi .pos  { color: #3ecf8e; }
.kpi .neg  { color: #f76e6e; }
.kpi .neu  { color: #7a869a; }

/* Sidebar section headers */
.sh {
  color: #6c7fe8; font-size: .76rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .1em;
  margin: 12px 0 4px;
  padding-bottom: 3px;
  border-bottom: 1px solid #2d3650;
}

div[data-testid="stSidebar"] { background: #131720; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛣️ COMODORO RADA TILLI")
    st.markdown("**Concesión 20 años · 2026–2045**")
    st.markdown("---")

    # ── Tránsito y Tarifa ──────────────────────────────────────
    st.markdown('<div class="sh">🚗 Tránsito y Tarifa</div>', unsafe_allow_html=True)

    tarifa_input = st.number_input(
        "Tarifa base (ARS/UTEQ, sin IVA)",
        min_value=1_000, max_value=50_000,
        value=int(TARIFA_BASE), step=500,
        help=f"Tarifa base del xlsx: $ {TARIFA_BASE:,.0f}. Se aplica desde el Año 1."
    )

    st.caption(
        "📌 **Regla de ingresos:**  \n"
        "**Año 1** → tránsito arranque ≈ 5.5M UTEQs (cobro desde el primer año).  \n"
        "**Año 2** → tránsito arranque × **+5%** fijo.  \n"
        "**Año 3+** → crece a tasa base 3% + Δ abajo."
    )

    delta_trafico_pp = st.slider(
        "Δ tasa crecimiento anual Año 3+ (±pp sobre base 3%)",
        min_value=-3.0, max_value=5.0, value=0.0, step=0.5,
        format="%.1f pp",
        help="Solo afecta al Año 3 en adelante. El +5% de Y1→Y2 es siempre fijo."
    )
    delta_trafico = delta_trafico_pp / 100

    # ── CAPEX ──────────────────────────────────────────────────
    st.markdown('<div class="sh">🏗️ CAPEX – sensibilidades</div>', unsafe_allow_html=True)
    delta_obras = st.slider(
        "Obras obligatorias (%)",
        min_value=-40, max_value=100, value=0, step=5,
        help="Variación % sobre el monto base de obras obligatorias"
    ) / 100
    delta_repav = st.slider(
        "Repavimentación (%)",
        min_value=-40, max_value=100, value=0, step=5,
        help="Variación % sobre el monto base de repavimentaciones"
    ) / 100

    # ── OPEX ──────────────────────────────────────────────────
    st.markdown('<div class="sh">⚙️ OPEX – Conservación y Mantenimiento</div>', unsafe_allow_html=True)
    delta_opex = st.slider(
        "Variación OPEX (%)",
        min_value=-40, max_value=100, value=0, step=5
    ) / 100

    # ── Impuestos ─────────────────────────────────────────────
    st.markdown('<div class="sh">💰 Alícuotas impositivas</div>', unsafe_allow_html=True)
    al_ganancias = st.slider(
        "Ganancias (%)",      0, 55, 35, 5,
        help="Base: 35%"
    ) / 100
    al_ib = st.slider(
        "Ingresos Brutos (%)", 0, 10, 3, 1,
        help="Base: 2.5% — slider en enteros, base redondeada a 3%"
    ) / 100
    al_municipal = st.slider(
        "Tasas Municipales (%)", 0, 3, 1, 1,
        help="Base: 0.5%"
    ) / 100
    al_sellos = st.slider(
        "Impuesto de Sellos (%)", 0, 5, 1, 1,
        help="Base: 1.2% (primeros 5 años)"
    ) / 100
    al_dbcr = st.slider(
        "Débitos y Créditos Bancarios (%)", 0, 5, 1, 1,
        help="Base: 1.2%"
    ) / 100
    al_iva_peaje = st.slider(
        "IVA sobre peaje (%)", 0, 27, 21, 1,
        help="Base: 21%"
    ) / 100

    # ── Tasa de descuento ─────────────────────────────────────
    st.markdown('<div class="sh">📐 Tasa de descuento VAN</div>', unsafe_allow_html=True)
    tasa_van = st.slider(
        "Tasa de descuento (%)", 5, 25, 10, 1
    ) / 100

    st.markdown("---")
    if st.button("↺  Resetear todo al base", use_container_width=True):
        st.rerun()

# ── EJECUTAR MODELO ───────────────────────────────────────────
sc = run_model(
    delta_capex_obras = delta_obras,
    delta_capex_repav = delta_repav,
    delta_opex        = delta_opex,
    delta_trafico     = delta_trafico,
    tarifa            = float(tarifa_input),
    al_ganancias      = al_ganancias,
    al_ib             = al_ib,
    al_municipal      = al_municipal,
    al_sellos         = al_sellos,
    al_dbcr           = al_dbcr,
    al_iva_peaje      = al_iva_peaje,
    tasa_van          = tasa_van,
)

YEARS_RANGE = list(range(2026, 2026 + YEARS + 1))   # 2026..2046 (Y0=2026, Y20=2045)


# ── HELPERS ───────────────────────────────────────────────────
def fmt_ars(v):
    if abs(v) >= 1e12: return f"$ {v/1e12:.2f} B"
    if abs(v) >= 1e9:  return f"$ {v/1e9:.2f} MM"
    return f"$ {v:,.0f}"

def delta_html(new, base, flip=False):
    if base == 0 or (isinstance(new, float) and np.isnan(new)):
        return '<span class="neu">—</span>'
    d = (new - base) / abs(base)
    good = (d >= 0) if not flip else (d <= 0)
    cls  = "pos" if good else "neg"
    sgn  = "+" if d > 0 else ""
    return f'<span class="{cls}">{sgn}{d:.1%} vs base</span>'

def kpi(label, value_str, new, base, flip=False):
    return f"""<div class="kpi">
  <div class="lbl">{label}</div>
  <div class="val">{value_str}</div>
  <div class="dlt">{delta_html(new, base, flip)}</div>
</div>"""

PL = dict(
    plot_bgcolor="#181e2d", paper_bgcolor="#181e2d",
    font=dict(color="#c5cdd8", size=12),
    margin=dict(t=40, b=50, l=60, r=20),
    xaxis=dict(gridcolor="#252f45", zeroline=False),
    yaxis=dict(gridcolor="#252f45", zeroline=False),
)
C = dict(
    pos="#3ecf8e", neg="#f76e6e",
    acc="#6c7fe8", warn="#f0a742",
    pur="#a855f7", gry="#64748b",
)


# ══════════════════════════════════════════════════════════════
# 4.  ENCABEZADO Y KPIs
# ══════════════════════════════════════════════════════════════
st.markdown("# 🛣️ COMODORO RADA TILLI — Análisis de Sensibilidades")
st.markdown(
    "Concesión vial 20 años · 2026–2045 &nbsp;|&nbsp; "
    "Modificá los parámetros en el panel ← para ver el impacto en tiempo real"
)
st.divider()

c1, c2, c3, c4 = st.columns(4)
mirr_s   = f"{sc['mirr']:.2%}"   if not np.isnan(sc["mirr"]) else "n/d"
vaff_s   = f"{sc['vaff_vae']:.4f}" if not np.isnan(sc["vaff_vae"]) else "n/d"
pb_año   = sc["payback"]
pb_s     = f"Año {pb_año}  ({2026 + pb_año})" if pb_año is not None else "No recupera"
inv_obras_s = fmt_ars(sc["inversion_obras"])

c1.markdown(kpi("TIR Modificada (MIRR)", mirr_s,
                sc["mirr"], MIRR_BASE), unsafe_allow_html=True)
c2.markdown(kpi(f"VAN  (tasa {tasa_van:.0%})", fmt_ars(sc["van"]),
                sc["van"], VAN_BASE), unsafe_allow_html=True)
c3.markdown(kpi("VAFF / VAE", vaff_s,
                sc["vaff_vae"], VAFF_VAE_BASE), unsafe_allow_html=True)
c4.markdown(kpi(f"Payback obras · {inv_obras_s}", pb_s, 0, 0),
            unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 5.  TABS
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Flujo de Fondos",
    "🌪️ Tornado & Spider",
    "📋 Tabla detallada",
    "🔥 Mapas de calor",
])


# ─────────────────────────────────────────────────────────────
# TAB 1 – FLUJO DE FONDOS
# ─────────────────────────────────────────────────────────────
with tab1:
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Flujo Neto Anual  ($ MM ARS)",
            "Flujo Acumulado  ($ MM ARS)",
            "Composición de Egresos por año  ($ MM ARS)",
            "Ingresos vs Egresos  ($ MM ARS)",
        ],
        vertical_spacing=0.16, horizontal_spacing=0.10,
    )

    bc = [C["pos"] if v >= 0 else C["neg"] for v in sc["flujo"]]
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["flujo"]/1e9,
                         marker_color=bc, name="Flujo Neto"),
                  row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=1)

    fig.add_trace(go.Scatter(
        x=YEARS_RANGE, y=sc["acum"]/1e9, mode="lines+markers",
        line=dict(color=C["acc"], width=2.5), marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(108,127,232,.12)", name="Acumulado"),
        row=1, col=2)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=2)

    # Egresos apilados
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["capex"]/1e9,
                         name="CAPEX", marker_color=C["neg"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["opex"]/1e9,
                         name="OPEX", marker_color=C["warn"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["total_imp"]/1e9,
                         name="Impuestos", marker_color=C["pur"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["amort_deuda"]/1e9,
                         name="Deuda LP", marker_color=C["gry"]), row=2, col=1)

    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_ing"]/1e9,
                              mode="lines", line=dict(color=C["pos"], width=2.5),
                              name="Ingresos"), row=2, col=2)
    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_egr"]/1e9,
                              mode="lines", line=dict(color=C["neg"], width=2.5),
                              name="Egresos"), row=2, col=2)

    fig.update_layout(**PL, barmode="stack", height=640, showlegend=True,
                      legend=dict(orientation="h", y=-0.07,
                                  bgcolor="rgba(0,0,0,0)"))
    for ax in ["xaxis","xaxis2","xaxis3","xaxis4",
               "yaxis","yaxis2","yaxis3","yaxis4"]:
        fig.update_layout(**{ax: dict(gridcolor="#252f45", zeroline=False)})

    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TAB 2 – TORNADO + SPIDER
# ─────────────────────────────────────────────────────────────
with tab2:
    st.markdown("#### Gráfico Tornado — impacto individual sobre el VAN")
    st.caption("Cada barra aplica un shock de ±20% a UNA sola variable, manteniendo el resto en el valor del panel.")

    BASE_KW = dict(
        delta_capex_obras=delta_obras, delta_capex_repav=delta_repav,
        delta_opex=delta_opex, delta_trafico=delta_trafico,
        tarifa=float(tarifa_input),
        al_ganancias=al_ganancias, al_ib=al_ib,
        al_municipal=al_municipal, al_sellos=al_sellos,
        al_dbcr=al_dbcr, al_iva_peaje=al_iva_peaje, tasa_van=tasa_van,
    )

    shocks = {
        "Obras +20%":         dict(delta_capex_obras=delta_obras+0.20),
        "Obras –20%":         dict(delta_capex_obras=delta_obras-0.20),
        "Repavim. +20%":      dict(delta_capex_repav=delta_repav+0.20),
        "Repavim. –20%":      dict(delta_capex_repav=delta_repav-0.20),
        "OPEX +20%":          dict(delta_opex=delta_opex+0.20),
        "OPEX –20%":          dict(delta_opex=delta_opex-0.20),
        "Tránsito +1pp":      dict(delta_trafico=delta_trafico+0.01),
        "Tránsito –1pp":      dict(delta_trafico=delta_trafico-0.01),
        "Tarifa +20%":        dict(tarifa=float(tarifa_input)*1.20),
        "Tarifa –20%":        dict(tarifa=float(tarifa_input)*0.80),
        "Ganancias +10pp":    dict(al_ganancias=min(0.60, al_ganancias+0.10)),
        "Ganancias –10pp":    dict(al_ganancias=max(0.00, al_ganancias-0.10)),
        "IB +2pp":            dict(al_ib=al_ib+0.02),
        "IB –2pp":            dict(al_ib=max(0, al_ib-0.02)),
        "IVA peaje +3pp":     dict(al_iva_peaje=al_iva_peaje+0.03),
        "IVA peaje –3pp":     dict(al_iva_peaje=max(0, al_iva_peaje-0.03)),
        "Db/Cr +1pp":         dict(al_dbcr=al_dbcr+0.01),
        "Db/Cr –1pp":         dict(al_dbcr=max(0, al_dbcr-0.01)),
        "Tasa descuento +2pp":dict(tasa_van=tasa_van+0.02),
        "Tasa descuento –2pp":dict(tasa_van=max(0.01, tasa_van-0.02)),
    }

    base_van = sc["van"]
    t_rows = []
    for label, ov in shocks.items():
        r = run_model(**{**BASE_KW, **ov})
        t_rows.append({"Variable": label,
                        "ΔVAN": (r["van"] - base_van) / 1e9})
    df_t = pd.DataFrame(t_rows).sort_values("ΔVAN")

    fig2 = go.Figure(go.Bar(
        x=df_t["ΔVAN"], y=df_t["Variable"], orientation="h",
        marker_color=["#3ecf8e" if v >= 0 else "#f76e6e" for v in df_t["ΔVAN"]],
        text=[f"$ {v:+.1f} MM" for v in df_t["ΔVAN"]],
        textposition="outside",
    ))
    fig2.add_vline(x=0, line_color="#999", line_dash="dot")
    fig2.update_layout(**PL, height=540,
                       xaxis_title="Δ VAN ($ ARS MM)",
                       margin=dict(l=180, r=130, t=40, b=50))
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("#### Spider — MIRR según variación de cada variable (±40%)")

    rang = np.arange(-40, 45, 10)
    variables = {
        "CAPEX Obras":    lambda p: dict(delta_capex_obras=delta_obras + p/100),
        "CAPEX Repavim.": lambda p: dict(delta_capex_repav=delta_repav + p/100),
        "OPEX":           lambda p: dict(delta_opex=delta_opex + p/100),
        "Tránsito (+pp)": lambda p: dict(delta_trafico=delta_trafico + p/100),
        "Tarifa (+%)":    lambda p: dict(tarifa=float(tarifa_input) * (1 + p/100)),
        "Ganancias (+pp)":lambda p: dict(al_ganancias=max(0, al_ganancias + p/100)),
    }
    cols_spider = [C["neg"], C["warn"], C["pur"], C["pos"], C["acc"], "#f59e0b"]

    fig3 = go.Figure()
    for (vname, fn), col in zip(variables.items(), cols_spider):
        mirrs = []
        for p in rang:
            r = run_model(**{**BASE_KW, **fn(p)})
            mirrs.append(r["mirr"]*100 if not np.isnan(r["mirr"]) else None)
        fig3.add_trace(go.Scatter(x=list(rang), y=mirrs, name=vname,
                                   mode="lines+markers",
                                   line=dict(color=col, width=2.5),
                                   marker=dict(size=5)))

    fig3.add_hline(y=MIRR_BASE*100, line_dash="dash", line_color="#aaa",
                   annotation_text=f"Base {MIRR_BASE*100:.1f}%",
                   annotation_position="bottom right")
    fig3.update_layout(**PL, height=400,
                       xaxis_title="Variación (%)",
                       yaxis_title="MIRR (%)",
                       legend=dict(bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig3, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TAB 3 – TABLA DETALLADA
# ─────────────────────────────────────────────────────────────
with tab3:
    # ── Info box sobre la lógica de tránsito ──────────────────
    tasa_eff_display = (TRAFICO_CRECIMIENTO_BASE + delta_trafico) * 100
    uteq_y1 = sc['uteq'][1]
    uteq_y2 = sc['uteq'][2]
    uteq_y3 = sc['uteq'][3]
    st.info(
        f"**Lógica de ingresos de peaje:**  \n"
        f"- **Año 1 (2026):** {uteq_y1:,.0f} UTEQs (arranque) × tarifa $ {float(tarifa_input):,.0f} s/IVA → ingreso = **$ {sc['peaje'][1]/1e9:.2f} MM**.  \n"
        f"- **Año 2 (2027):** {uteq_y2:,.0f} UTEQs (+5% fijo) × tarifa $ {float(tarifa_input):,.0f} s/IVA → ingreso = **$ {sc['peaje'][2]/1e9:.2f} MM**.  \n"
        f"- **Año 3+ (2028→):** crece al **{tasa_eff_display:.1f}% anual** (base 3% {'+ ' if delta_trafico >= 0 else ''}{delta_trafico*100:.1f}pp).  \n"
        f"  Año 3: {uteq_y3:,.0f} UTEQs → $ {sc['peaje'][3]/1e9:.2f} MM."
    )
    tarifa_con_iva_display = float(tarifa_input) * (1 + al_iva_peaje)
    for y in range(YEARS + 1):
        rows.append({
            "Año cal.":           YEARS_RANGE[y],
            "Año conc.":          y,
            "UTEQUIs":            f"{sc['uteq'][y]:,.0f}",
            "Tarifa c/IVA (ARS)": f"$ {tarifa_con_iva_display:,.0f}" if y >= 1 else "—",
            "Peaje+IVA (MM$)":    round(sc["peaje"][y]/1e6, 1),
            "CAPEX (MM$)":        round(sc["capex"][y]/1e6, 1),
            "OPEX (MM$)":         round(sc["opex"][y]/1e6, 1),
            "Ganancias (MM$)":    round(sc["imp_ganancias"][y]/1e6, 1),
            "IVA neto (MM$)":     round(sc["imp_iva"][y]/1e6, 1),
            "IB (MM$)":           round(sc["imp_ib"][y]/1e6, 1),
            "Db/Cr (MM$)":        round(sc["imp_dbcr"][y]/1e6, 1),
            "Sellos (MM$)":       round(sc["imp_sellos"][y]/1e6, 1),
            "Municipal (MM$)":    round(sc["imp_municipal"][y]/1e6, 1),
            "Deuda LP (MM$)":     round(sc["amort_deuda"][y]/1e6, 1),
            "Garantías (MM$)":    round(GARANTIAS[y]/1e6, 1),
            "Flujo Neto (MM$)":   round(sc["flujo"][y]/1e6, 1),
            "Acumulado (MM$)":    round(sc["acum"][y]/1e6, 1),
        })
    df_out = pd.DataFrame(rows)

    def color_num(col):
        if col.name in ("Flujo Neto (MM$)", "Acumulado (MM$)"):
            return ["color:#3ecf8e" if v >= 0 else "color:#f76e6e" for v in col]
        return ["" for _ in col]

    st.dataframe(
        df_out.style
              .apply(color_num)
              .set_properties(**{"background-color": "#181e2d", "color": "#c5cdd8"}),
        use_container_width=True, height=640,
    )

    st.divider()
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("VAN Ingresos",  fmt_ars(sc["van_ing"]))
    r2.metric("VAN Egresos",   fmt_ars(sc["van_egr"]))
    r3.metric("VAN Flujo",     fmt_ars(sc["van"]))
    r4.metric("MIRR",          f"{sc['mirr']:.2%}" if not np.isnan(sc["mirr"]) else "n/d")


# ─────────────────────────────────────────────────────────────
# TAB 4 – MAPAS DE CALOR
# ─────────────────────────────────────────────────────────────
with tab4:

    trafico_rng = np.arange(-2.0, 3.5, 0.5)   # Δpp sobre base 3%
    capex_rng   = np.arange(-30, 55, 10)        # % variación obras
    opex_rng    = np.arange(-30, 55, 10)
    gan_rng     = np.arange(15, 55, 5)
    tasa_rng    = np.arange(6, 20, 2)

    def heat(**ov):
        return run_model(**{**BASE_KW, **ov})

    # ── Mapa 1: MIRR = Δtráfico × CAPEX obras ────────────────
    st.markdown("#### MIRR (%) — Δ Tránsito (pp) × Obras CAPEX (%)")
    mat1 = np.zeros((len(trafico_rng), len(capex_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, cp in enumerate(capex_rng):
            r = heat(delta_trafico=delta_trafico+tr/100,
                     delta_capex_obras=delta_obras+cp/100)
            mat1[i, j] = r["mirr"]*100 if not np.isnan(r["mirr"]) else 0

    fig4 = go.Figure(go.Heatmap(
        z=mat1.round(1),
        x=[f"{c:+d}%" for c in capex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat1.round(1),
        texttemplate="%{text:.1f}%",
        colorbar=dict(title="MIRR (%)", tickfont=dict(color="#c5cdd8")),
    ))
    fig4.update_layout(**PL, xaxis_title="Variación obras CAPEX",
                        yaxis_title="Δ crecimiento tránsito",
                        height=370, margin=dict(t=30,b=60,l=100,r=20))
    st.plotly_chart(fig4, use_container_width=True)

    # ── Mapa 2: VAN = Δtráfico × OPEX ────────────────────────
    st.markdown("#### VAN ($ MM) — Δ Tránsito × OPEX (%)")
    mat2 = np.zeros((len(trafico_rng), len(opex_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, op in enumerate(opex_rng):
            r = heat(delta_trafico=delta_trafico+tr/100,
                     delta_opex=delta_opex+op/100)
            mat2[i, j] = r["van"] / 1e9

    fig5 = go.Figure(go.Heatmap(
        z=mat2.round(1),
        x=[f"{o:+d}%" for o in opex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat2.round(1),
        texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig5.update_layout(**PL, xaxis_title="Variación OPEX",
                        yaxis_title="Δ crecimiento tránsito",
                        height=370, margin=dict(t=30,b=60,l=100,r=20))
    st.plotly_chart(fig5, use_container_width=True)

    # ── Mapa 3: VAN = tasa descuento × obras CAPEX ───────────
    st.markdown("#### VAN ($ MM) — Tasa de descuento × Obras CAPEX (%)")
    mat3 = np.zeros((len(tasa_rng), len(capex_rng)))
    for i, td in enumerate(tasa_rng):
        for j, cp in enumerate(capex_rng):
            r = heat(tasa_van=td/100, delta_capex_obras=delta_obras+cp/100)
            mat3[i, j] = r["van"] / 1e9

    fig6 = go.Figure(go.Heatmap(
        z=mat3.round(1),
        x=[f"{c:+d}%" for c in capex_rng],
        y=[f"{t}%" for t in tasa_rng],
        colorscale="RdYlGn", text=mat3.round(1),
        texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig6.update_layout(**PL, xaxis_title="Variación obras CAPEX",
                        yaxis_title="Tasa de descuento",
                        height=370, margin=dict(t=30,b=60,l=80,r=20))
    st.plotly_chart(fig6, use_container_width=True)

    # ── Mapa 4: VAFF/VAE = Δtráfico × Ganancias ──────────────
    st.markdown("#### VAFF/VAE — Δ Tránsito × Alícuota Ganancias (%)")
    mat4 = np.zeros((len(trafico_rng), len(gan_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, ga in enumerate(gan_rng):
            r = heat(delta_trafico=delta_trafico+tr/100,
                     al_ganancias=ga/100)
            mat4[i, j] = r["vaff_vae"] if not np.isnan(r["vaff_vae"]) else 0

    fig7 = go.Figure(go.Heatmap(
        z=mat4.round(4),
        x=[f"{g}%" for g in gan_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat4.round(3),
        texttemplate="%{text:.3f}",
        colorbar=dict(title="VAFF/VAE", tickfont=dict(color="#c5cdd8")),
    ))
    fig7.update_layout(**PL, xaxis_title="Alícuota Ganancias",
                        yaxis_title="Δ crecimiento tránsito",
                        height=370, margin=dict(t=30,b=60,l=100,r=20))
    st.plotly_chart(fig7, use_container_width=True)


# ── FOOTER ────────────────────────────────────────────────────
st.divider()
st.caption(
    "COMODORO RADA TILLI · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)