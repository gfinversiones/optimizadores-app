"""
CAUCETE – Panel de Sensibilidades Financieras
==============================================
Replicación fiel del modelo CAUCETE.xlsx.

El modelo NO recalcula el préstamo ni usa WACC.
Los flujos base se toman directamente del xlsx y se
escalan con los factores de sensibilidad ingresados.

Instalación:
    pip install streamlit pandas plotly

Ejecución:
    streamlit run caucete_sensibilidades.py
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
# 1.  DATOS BASE  (extraídos del xlsx CAUCETE)
# ══════════════════════════════════════════════════════════════
#
# Años de concesión: 1-20 (2026-2045).
# Índice 0 = año inicio concesión (2025/2026, puesta en valor + crédito).
# Los arrays tienen 21 elementos [0..20].

YEARS = 20

# ── Ingresos de peaje con IVA (del sheet FLUJO) ────────────────
PEAJE_BASE = np.array([
    0,
    24_541_041_681.62,
    25_277_272_932.07,
    26_035_591_120.03,
    26_816_658_853.63,
    27_621_158_619.24,
    28_449_793_377.82,
    29_303_287_179.15,
    30_182_385_794.53,
    31_087_857_368.36,
    32_020_493_089.41,
    32_981_107_882.10,
    33_970_541_118.56,
    34_989_657_352.12,
    36_039_347_072.68,
    37_120_527_484.86,
    38_234_143_309.40,
    39_381_167_608.69,
    40_562_602_636.95,
    41_779_480_716.06,
    0,   # año 20 ya incluido arriba; acá es el "total" → lo dejamos 0
], dtype=float)
# Corrección: en el xlsx el año 20 sí tiene ingresos
PEAJE_BASE[20] = 41_779_480_716.06   # igual al año 19 (mismo orden de magnitud base)
# Re-tomar de los datos: el último valor de la columna es el año 20
PEAJE_BASE = np.array([
    0,                       # Y0 (puesta en valor, sin ingresos peaje)
    24_541_041_681.62,       # Y1
    25_277_272_932.07,
    26_035_591_120.03,
    26_816_658_853.63,
    27_621_158_619.24,
    28_449_793_377.82,
    29_303_287_179.15,
    30_182_385_794.53,
    31_087_857_368.36,
    32_020_493_089.41,
    32_981_107_882.10,
    33_970_541_118.56,
    34_989_657_352.12,
    36_039_347_072.68,
    37_120_527_484.86,
    38_234_143_309.40,
    39_381_167_608.69,
    40_562_602_636.95,
    41_779_480_716.06,       # Y19
    41_779_480_716.06,       # Y20 (aproximado con igual valor; xlsx no lo muestra explícito)
], dtype=float)

# Tránsito base implícito (UTEQ) → lo derivamos para poder escalar con delta_trafico
# La tarifa es $6.000 y el primer ingreso con IVA (21%) es 24.541 MM
# => UTEQ_Y1 = 24.541e9 / (6000 * 1.21) ≈ 3.382 M
TARIFA_IVA = 6_000 * 1.21   # tarifa año 1 con IVA

UTEQ_BASE = np.zeros(YEARS + 1)
for y in range(1, YEARS + 1):
    UTEQ_BASE[y] = PEAJE_BASE[y] / TARIFA_IVA   # en unidades de UTEQ

# Crecimiento de tránsito base implícito entre años
# Y1→Y2: +3% (después del 5% del primer año que ya está en el base)
TRAFICO_CRECIMIENTO_BASE = 0.03

# ── CAPEX con IVA (del sheet FLUJO, TOTAL CAPEX) ────────────────
CAPEX_BASE = np.array([
    2_890_357_500.00,    # Y0  puesta en valor
    0,                   # Y1
    0,                   # Y2
    4_335_536_250.00,    # Y3
    4_335_536_250.00,    # Y4
    4_335_536_250.00,    # Y5
    14_373_922_500.00,   # Y6
    20_076_772_500.00,   # Y7
    20_076_772_500.00,   # Y8
    13_139_914_500.00,   # Y9
    11_405_700_000.00,   # Y10
    17_108_550_000.00,   # Y11
    11_405_700_000.00,   # Y12
    15_741_236_250.00,   # Y13
    15_741_236_250.00,   # Y14
    10_038_386_250.00,   # Y15
    10_038_386_250.00,   # Y16
    8_671_072_500.00,    # Y17
    8_671_072_500.00,    # Y18
    8_671_072_500.00,    # Y19
    8_671_072_500.00,    # Y20
], dtype=float)

# ── OPEX con IVA – Conservación y Mantenimiento ────────────────
OPEX_BASE = np.full(YEARS + 1, 3_853_810_000.00)

# ── Parámetros del préstamo ────────────────────────────────────
# El préstamo = 70% de la Puesta en Valor.
# Sistema francés, 6 años, TNA 8.5%, gastos admin 1% del capital.
# Año de gracia: el ingreso entra en Y1, el primer pago en Y2.
PUESTA_VALOR_MONTO = 2_890_357_500.0   # monto base puesta en valor
PRESTAMO_PCT       = 0.70              # % sobre puesta en valor
PRESTAMO_TNA       = 0.085
PRESTAMO_AÑOS      = 6
PRESTAMO_GASTOS    = 0.01              # gastos admin como % del capital


def calcular_prestamo(monto_puesta_en_valor: float):
    """
    Devuelve (ingreso_credito, amort_deuda, intereses, capital).
    Todos arrays [0..YEARS].
    - Ingreso entra en Y1 (año de gracia: no paga en Y1).
    - Cuotas francesas Y2..Y7 (6 pagos, sistema francés).
    - La cuota del Y2 incluye los gastos administrativos (1% del capital).
    - 'intereses' contiene solo el componente de interés de cada cuota
      (sin los gastos administrativos), usado para la deducción del Art. 85 IIGG.
    """
    capital = monto_puesta_en_valor * PRESTAMO_PCT
    gastos  = capital * PRESTAMO_GASTOS
    tna     = PRESTAMO_TNA
    n       = PRESTAMO_AÑOS

    # Cuota francesa pura
    cuota = capital * tna / (1 - (1 + tna) ** -n)

    ingreso    = np.zeros(YEARS + 1)
    amort      = np.zeros(YEARS + 1)
    intereses  = np.zeros(YEARS + 1)   # interés puro por año (sin gastos admin)

    ingreso[1] = capital   # el dinero entra en año 1; año de gracia: no paga

    # Año 1: durante el año de gracia se devenga interés sobre el capital total
    intereses[1] = capital * tna

    saldo = capital
    for k in range(n):            # k=0..5  ->  cuotas en Y2..Y7
        y = k + 2
        interes_k    = saldo * tna
        amort_cap_k  = cuota - interes_k
        saldo       -= amort_cap_k
        if y <= YEARS:
            amort[y]     = cuota + (gastos if k == 0 else 0.0)
            intereses[y] = interes_k

    return ingreso, amort, intereses, capital


# Arrays base (se recalculan en run_model si cambia la sensibilidad)
_ing_base, _amort_base, _int_base, _capital_base = calcular_prestamo(PUESTA_VALOR_MONTO)
INGRESO_CREDITO  = _ing_base
AMORT_DEUDA_BASE = _amort_base

# ── Garantías anuales ──────────────────────────────────────────
GARANTIAS = np.full(YEARS + 1, 28_000_000.0)

# ── Impuestos BASE por componente (del sheet FLUJO detallado) ──
# Todos con IVA / tal como aparecen en el flujo

IMP_IVA_BASE = np.array([
    0,
    2_656_972_281.01,
    3_832_134_507.98,
    3_220_383_801.65,
    3_365_802_350.98,
    3_516_125_830.45,
    1_929_348_223.21,
    1_093_765_562.35,
    1_246_336_396.43,
    2_607_401_859.65,
    3_070_243_633.56,
    2_247_211_076.91,
    3_408_681_721.26,
    2_833_104_693.61,
    3_015_282_248.42,
    4_192_675_956.32,
    4_385_948_124.22,
    4_822_320_843.51,
    5_027_363_286.43,
    5_238_557_002.64,
    0,
], dtype=float)
IMP_IVA_BASE[20] = IMP_IVA_BASE[19]  # extrapolo

IMP_GANANCIAS_BASE = np.array([
    0,
    3_901_238_045.30,
    5_527_661_023.34,
    5_495_218_647.32,
    5_469_810_984.91,
    5_591_266_769.29,
    5_212_052_382.37,
    4_958_490_406.28,
    4_950_638_227.15,
    5_351_380_801.76,
    5_859_957_421.65,
    6_627_083_002.42,
    7_402_173_381.82,
    7_934_651_357.11,
    8_074_273_352.54,
    8_122_272_239.79,
    8_116_531_541.40,
    7_597_490_588.60,
    6_920_749_257.43,
    4_999_722_890.45,
    0,
], dtype=float)
IMP_GANANCIAS_BASE[20] = IMP_GANANCIAS_BASE[19]

IMP_IB_BASE = np.array([
    0,
    507_046_315.74,
    522_257_705.21,
    537_925_436.36,
    554_063_199.46,
    570_685_095.44,
    587_805_648.30,
    605_439_817.75,
    623_603_012.28,
    642_311_102.65,
    661_580_435.73,
    681_427_848.80,
    701_870_684.27,
    722_926_804.80,
    744_614_608.94,
    766_953_047.21,
    789_961_638.62,
    813_660_487.78,
    838_070_302.42,
    863_212_411.49,
    0,
], dtype=float)
IMP_IB_BASE[20] = IMP_IB_BASE[19]

IMP_MUNICIPAL_BASE = np.array([
    0,
    101_409_263.15,
    104_451_541.04,
    107_585_087.27,
    110_812_639.89,
    114_137_019.09,
    117_561_129.66,
    121_087_963.55,
    124_720_602.46,
    128_462_220.53,
    132_316_087.15,
    136_285_569.76,
    140_374_136.85,
    144_585_360.96,
    148_922_921.79,
    153_390_609.44,
    157_992_327.72,
    162_732_097.56,
    167_614_060.48,
    172_642_482.30,
    0,
], dtype=float)
IMP_MUNICIPAL_BASE[20] = IMP_MUNICIPAL_BASE[19]

IMP_SELLOS_BASE = np.array([
    398_790_269.26,   # Y0
    398_790_269.26,   # Y1
    398_790_269.26,   # Y2
    398_790_269.26,   # Y3
    398_790_269.26,   # Y4
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

IMP_DBCR_BASE = np.array([
    24_279_003.00,
    294_492_500.18,
    303_327_275.18,
    312_427_093.44,
    321_799_906.24,
    331_453_903.43,
    341_397_520.53,
    351_639_446.15,
    362_188_629.53,
    373_054_288.42,
    384_245_917.07,
    395_773_294.59,
    407_646_493.42,
    419_875_888.23,
    432_472_164.87,
    445_446_329.82,
    458_809_719.71,
    472_574_011.30,
    486_751_231.64,
    501_353_768.59,
    0,
], dtype=float)
IMP_DBCR_BASE[20] = IMP_DBCR_BASE[19]

# Alícuotas base (para escalar proporcionalmente)
AL_GANANCIAS_BASE = 0.35
AL_IB_BASE        = 0.025
AL_MUNICIPAL_BASE = 0.005
AL_SELLOS_BASE    = 0.012
AL_DBCR_BASE      = 0.012
AL_IVA_BASE       = 0.21     # IVA del peaje (21%)

# KPIs del xlsx (para mostrar delta vs base)
MIRR_BASE    = 0.2330
VAN_BASE     = 47_639_480_891.0
VAFF_VAE_BASE = 0.2624
TASA_VAN_BASE = 0.10


# ══════════════════════════════════════════════════════════════
# 2.  MODELO DE SENSIBILIDAD
# ══════════════════════════════════════════════════════════════

def run_model(
    delta_capex_obras   = 0.0,   # % variación obras obligatorias
    delta_capex_repav   = 0.0,   # % variación repavimentación
    delta_opex          = 0.0,   # % variación OPEX total
    delta_trafico       = 0.0,   # delta sobre tasa crecimiento base (+pp)
    al_ganancias        = AL_GANANCIAS_BASE,
    al_ib               = AL_IB_BASE,
    al_municipal        = AL_MUNICIPAL_BASE,
    al_sellos           = AL_SELLOS_BASE,
    al_dbcr             = AL_DBCR_BASE,
    al_iva_peaje        = AL_IVA_BASE,
    tasa_van            = TASA_VAN_BASE,
):
    # ── Tráfico escalado ────────────────────────────────────────
    # Y1 se mantiene fijo (arranque de la concesión).
    # A partir de Y2 se aplica (tasa_base + delta_trafico).
    uteq = np.zeros(YEARS + 1)
    uteq[0] = 0
    uteq[1] = UTEQ_BASE[1]   # año 1 fijo
    tasa_eff = TRAFICO_CRECIMIENTO_BASE + delta_trafico
    tasa_eff = max(tasa_eff, -0.50)  # piso sensato
    for y in range(2, YEARS + 1):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    # ── Ingresos de peaje escalados ─────────────────────────────
    # El ingreso de peaje = UTEQ * tarifa * (1 + IVA efectivo)
    # Escalamos en dos pasos:
    #   1) factor_trafico = uteq[y] / UTEQ_BASE[y]   (variación de volumen)
    #   2) factor_iva     = (1 + al_iva_peaje) / (1 + AL_IVA_BASE)  (variación alícuota)
    peaje = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        factor_trafico = uteq[y] / UTEQ_BASE[y] if UTEQ_BASE[y] > 0 else 1.0
        factor_iva     = (1 + al_iva_peaje) / (1 + AL_IVA_BASE)
        peaje[y] = PEAJE_BASE[y] * factor_trafico * factor_iva

    # ── Préstamo recalculado según puesta en valor del escenario ──
    ingreso_credito, amort_deuda, intereses_prestamo, capital_prestamo = calcular_prestamo(PUESTA_VALOR_MONTO)

    total_ingresos = peaje + ingreso_credito

    # ── CAPEX escalado ──────────────────────────────────────────
    OBRAS_OBLIG = np.array([
        0,0,0,0,0,0,
        5_702_850_000, 11_405_700_000, 11_405_700_000, 11_405_700_000,
        11_405_700_000, 17_108_550_000, 11_405_700_000, 11_405_700_000,
        11_405_700_000, 5_702_850_000, 5_702_850_000, 0, 0, 0, 0,
    ], dtype=float)
    REPAV = np.array([
        0,0,0,
        4_335_536_250, 4_335_536_250, 4_335_536_250,
        8_671_072_500, 8_671_072_500, 8_671_072_500,
        1_734_214_500, 0, 0, 0,
        4_335_536_250, 4_335_536_250, 4_335_536_250,
        4_335_536_250, 8_671_072_500, 8_671_072_500, 8_671_072_500, 8_671_072_500,
    ], dtype=float)
    PUESTA_VALOR_ARR = np.array([PUESTA_VALOR_MONTO] + [0]*20, dtype=float)

    capex = (PUESTA_VALOR_ARR
             + OBRAS_OBLIG * (1 + delta_capex_obras)
             + REPAV       * (1 + delta_capex_repav))

    # ── OPEX escalado ───────────────────────────────────────────
    opex = OPEX_BASE * (1 + delta_opex)

    # ── Impuestos escalados ─────────────────────────────────────
    factor_trafico_avg = np.where(UTEQ_BASE > 0, uteq / UTEQ_BASE, 1.0)

    imp_iva       = IMP_IVA_BASE      * factor_trafico_avg * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib        = IMP_IB_BASE       * factor_trafico_avg * (al_ib        / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE * factor_trafico_avg * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos    = IMP_SELLOS_BASE   * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr      = IMP_DBCR_BASE     * factor_trafico_avg * (al_dbcr     / AL_DBCR_BASE)

    # ── Impuesto a las Ganancias con deducción de intereses (Art. 85 LIG) ──
    # Base imponible antes de intereses y amortizaciones fiscales:
    #   ingreso_sin_iva  - opex_sin_iva  - otros_impuestos_deducibles
    # La deducción de intereses se limita al MAYOR entre:
    #   a) 30% de la ganancia neta antes de intereses y amortizaciones
    #   b) el interés real del período
    # (en la práctica el art. 85 fija el límite en 30%; se deduce lo menor
    #  entre el interés real y ese límite, salvo que el real sea menor)
    #
    # Simplificación aplicada:
    #   - ingreso_gravado   = peaje sin IVA
    #   - opex_deducible    = opex sin IVA (mantenimiento)
    #   - amort_fiscal      = capex / vida útil restante (lineal, se escala con CAPEX)
    #   - deducción interés = min(interés_real, 30% * EBITDA_impositivo)

    # Ingreso gravado sin IVA (escalar base por tráfico)
    ing_sin_iva   = peaje / (1 + al_iva_peaje)          # peaje ya escalado por tráfico
    opex_sin_iva  = opex  / (1 + 0.15)                  # IVA OPEX mantenimiento = 15%

    # Amortización fiscal acumulada del CAPEX (lineal por tramo)
    VIDA_UTIL = YEARS
    amort_fiscal = np.zeros(YEARS + 1)
    for y0 in range(YEARS + 1):
        if capex[y0] > 0:
            capex_sin_iva_y0 = capex[y0] / (1 + AL_IVA_BASE)
            vida_rem = max(VIDA_UTIL - y0, 1)
            cuota_am = capex_sin_iva_y0 / vida_rem
            for yf in range(y0, YEARS + 1):
                amort_fiscal[yf] += cuota_am

    imp_ganancias = np.zeros(YEARS + 1)
    for y in range(YEARS + 1):
        # EBITDA impositivo (antes de intereses y amortizaciones fiscales)
        ebitda_imp = max(0.0, ing_sin_iva[y] - opex_sin_iva[y])

        # Límite de deducción: 30% del EBITDA impositivo
        limite_30  = 0.30 * ebitda_imp

        # Interés real del período (del cuadro del préstamo)
        interes_real = intereses_prestamo[y]

        # Deducción efectiva: no puede superar el 30% del EBITDA
        # (si el interés real es menor al límite, se deduce el real)
        deduccion_intereses = min(interes_real, limite_30)

        # Base imponible neta
        base_iigg = max(0.0,
            ebitda_imp - amort_fiscal[y] - deduccion_intereses
        )
        imp_ganancias[y] = base_iigg * al_ganancias

    total_impuestos = imp_iva + imp_ganancias + imp_ib + imp_municipal + imp_sellos + imp_dbcr

    # ── Egresos totales ─────────────────────────────────────────
    total_egresos = capex + opex + amort_deuda + total_impuestos + GARANTIAS

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
    inversion_obras = float(np.sum(PUESTA_VALOR_ARR) + np.sum(OBRAS_OBLIG * (1 + delta_capex_obras)))
    payback   = next((y for y, v in enumerate(acum) if v >= inversion_obras), None)

    return dict(
        flujo         = flujo,
        total_ing     = total_ingresos,
        total_egr     = total_egresos,
        peaje         = peaje,
        capex         = capex,
        opex          = opex,
        amort_deuda      = amort_deuda,
        capital_prestamo = capital_prestamo,
        imp_iva       = imp_iva,
        imp_ganancias       = imp_ganancias,
        intereses_prestamo = intereses_prestamo,
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
    page_title="CAUCETE – Sensibilidades",
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
    st.markdown("## 🛣️ CAUCETE")
    st.markdown("**GESTIÓN – COAC · 2026–2045**")
    st.markdown("---")

    # ── Tránsito ───────────────────────────────────────────────
    st.markdown('<div class="sh">🚗 Crecimiento de tránsito</div>', unsafe_allow_html=True)
    delta_trafico_pp = st.slider(
        "Δ tasa crecimiento anual (±pp sobre base 3%)",
        min_value=-3.0, max_value=5.0, value=0.0, step=0.5,
        format="%.1f pp",
        help="El tránsito crece a 3% base. Con +1pp crecería al 4%."
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
    al_ganancias      = al_ganancias,
    al_ib             = al_ib,
    al_municipal      = al_municipal,
    al_sellos         = al_sellos,
    al_dbcr           = al_dbcr,
    al_iva_peaje      = al_iva_peaje,
    tasa_van          = tasa_van,
)

YEARS_RANGE = list(range(2025, 2025 + YEARS + 1))   # 2025..2045


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
st.markdown("# 🛣️ CAUCETE — Análisis de Sensibilidades")
st.markdown(
    "Concesión vial 20 años · 2026–2045 &nbsp;|&nbsp; "
    "Modificá los parámetros en el panel ← para ver el impacto en tiempo real"
)
st.divider()

c1, c2, c3, c4 = st.columns(4)
mirr_s   = f"{sc['mirr']:.2%}"   if not np.isnan(sc["mirr"]) else "n/d"
vaff_s   = f"{sc['vaff_vae']:.4f}" if not np.isnan(sc["vaff_vae"]) else "n/d"
pb_año   = sc["payback"]
pb_s     = f"Año {pb_año}  ({2025 + pb_año})" if pb_año is not None else "No recupera"
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
        "Ganancias (+pp)":lambda p: dict(al_ganancias=max(0, al_ganancias + p/100)),
    }
    cols_spider = [C["neg"], C["warn"], C["pur"], C["pos"], C["acc"]]

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
    rows = []
    for y in range(YEARS + 1):
        rows.append({
            "Año cal.":           YEARS_RANGE[y],
            "Año conc.":          y,
            "UTEQUIs":            f"{sc['uteq'][y]:,.0f}",
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
    "CAUCETE (GESTIÓN–COAC) · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)
