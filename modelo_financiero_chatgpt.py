def run_model(
    delta_capex_obras   = 0.0,
    delta_capex_repav   = 0.0,
    delta_opex          = 0.0,
    delta_trafico       = 0.0,
    tarifa              = TARIFA_BASE,
    al_ganancias        = AL_GANANCIAS_BASE,
    al_ib               = AL_IB_BASE,
    al_municipal        = AL_MUNICIPAL_BASE,
    al_sellos           = AL_SELLOS_BASE,
    al_dbcr             = AL_DBCR_BASE,
    al_iva_peaje        = AL_IVA_BASE,
    tasa_van            = TASA_VAN_BASE,
):

    uteq = np.zeros(YEARS + 1)

    uteq[0] = 0.0
    uteq[1] = UTEQ_ARRANQUE

    tasa_eff = TRAFICO_CRECIMIENTO_BASE + delta_trafico
    tasa_eff = max(tasa_eff, -0.50)

    for y in range(2, YEARS + 1):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    tarifa_con_iva = tarifa * (1 + al_iva_peaje)

    peaje = np.zeros(YEARS + 1)

    for y in range(1, YEARS + 1):
        peaje[y] = uteq[y] * tarifa_con_iva

    uteq_ref_for_tax = np.zeros(YEARS + 1)
    uteq_ref_for_tax[0] = 0.0

    for y in range(1, YEARS + 1):
        uteq_ref_for_tax[y] = (
            uteq[y] / UTEQ_ARRANQUE
            if UTEQ_ARRANQUE > 0
            else 1.0
        )

    total_ingresos = peaje + INGRESO_CREDITO

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
        0,0,0,0,
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
        8_671_072_500,
    ], dtype=float)

    PUESTA_VALOR = np.array([2_890_357_500.0] + [0] * 20, dtype=float)

    capex = (
        PUESTA_VALOR
        + OBRAS_OBLIG * (1 + delta_capex_obras)
        + REPAV * (1 + delta_capex_repav)
    )

    opex = OPEX_BASE * (1 + delta_opex)

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

    total_egresos = (
        capex
        + opex
        + AMORT_DEUDA_BASE
        + total_impuestos
        + GARANTIAS
    )

    flujo = total_ingresos - total_egresos

    van = _npv(tasa_van, flujo)

    van_egr = _npv(tasa_van, total_egresos)
    van_ing = _npv(tasa_van, total_ingresos)

    vaff_vae = (
        van / van_egr
        if van_egr != 0
        else float("nan")
    )

    mirr_val = _mirr(flujo, tasa_van)

    acum = np.cumsum(flujo)

    inversion_obras = float(
        np.sum(PUESTA_VALOR)
        + np.sum(OBRAS_OBLIG * (1 + delta_capex_obras))
    )

    payback = next(
        (
            y
            for y, v in enumerate(acum)
            if v >= inversion_obras
        ),
        None,
    )

    return dict(
        flujo=flujo,
        total_ing=total_ingresos,
        total_egr=total_egresos,
        peaje=peaje,
        capex=capex,
        opex=opex,
        amort_deuda=AMORT_DEUDA_BASE.copy(),
        imp_iva=imp_iva,
        imp_ganancias=imp_ganancias,
        imp_ib=imp_ib,
        imp_municipal=imp_municipal,
        imp_sellos=imp_sellos,
        imp_dbcr=imp_dbcr,
        total_imp=total_impuestos,
        acum=acum,
        van=van,
        van_ing=van_ing,
        van_egr=van_egr,
        vaff_vae=vaff_vae,
        mirr=mirr_val,
        payback=payback,
        inversion_obras=inversion_obras,
        uteq=uteq,
    )

