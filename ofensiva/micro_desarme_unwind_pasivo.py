# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #11: Gobernador Elastico de Cosecha por Estancamiento (MFE Stall)
y Desarme Pasivo en Ganancia ([MAKER_UNWIND]) Acoplado a Vacio L2 y Wald SPRT
para HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
import config_parametros as cfg
import core_estado_ram as ram
from ofensiva import micro_motor_wald_exit as mmw


def evaluar_cosecha_estancamiento_mfe(
    direccion: str,
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    piso_ganancia_neta_pct: float = 0.00065,
    vacio_l2_ratio: float = 1.0,
    lambda_wald: float = 0.0,
) -> bool:
    """
    Si la operacion ya alcanzo el umbral mfe_stall_harvest_pct y sigue en ganancia
    neta pero el flujo OFI perdio traccion, autoriza cobrar como Maker antes de que
    el precio regrese a la entrada.
    """
    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    umbral_stall = float(ctrl.get("mfe_stall_harvest_pct", cfg.COSECHA_ESTANCAMIENTO_MFE_PCT))
    piso_efectivo = max(float(cfg.TRINQUETE_BE_OFFSET_PCT), float(piso_ganancia_neta_pct))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    lam_w = float(lambda_wald or 0.0)

    edad_min = 12.0 if (v_l2 < 0.65 and lam_w <= -0.40) else 16.0
    if edad_seg < edad_min or mfe_pct < umbral_stall or pnl_pct < piso_efectivo:
        return False

    es_long = str(direccion).upper() in ("BUY", "LONG")
    ofi_dir = float(ofi_5s) if es_long else -float(ofi_5s)
    if v_l2 >= 1.40 and lam_w >= 1.20:
        umbral_ofi_stall = -0.02
    elif v_l2 < 0.65:
        umbral_ofi_stall = 0.10
    else:
        umbral_ofi_stall = 0.05
    return bool(ofi_dir <= umbral_ofi_stall)


def evaluar_desarme_maker_unwind_42s(
    direccion: str,
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    cosecha_activa: bool = False,
    symbol: str = "",
    vacio_l2_ratio: float = 1.0,
    lambda_wald: float = 0.0,
) -> bool:
    """
    Gobierna la activacion de [MAKER_UNWIND] al cumplirse la ventana elastica
    modulada desde w4_unwind_seg (42.0s), exigiendo cubrir al menos
    TRINQUETE_BE_OFFSET_PCT e inhibiendo el cierre si la posicion va en rally
    con soporte de vacio L2.
    """
    piso_min = max(0.00055, float(cfg.TRINQUETE_BE_OFFSET_PCT))
    if cosecha_activa or pnl_pct < piso_min:
        return False

    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    unwind_base = float(ctrl.get("w4_unwind_seg", 42.0))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    lam_w = float(lambda_wald or 0.0)

    if symbol and v_l2 == 1.0 and not cfg.es_modo_test():
        m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
        if m_live is not None:
            v_l2 = float(getattr(m_live, "vacio_l2_ratio", 1.0) or 1.0)

    if not cfg.es_modo_test() and (v_l2 != 1.0 or lam_w != 0.0):
        mod_t = max(0.78, min(1.15, 0.92 + (0.08 * v_l2) + (0.025 * max(-2.0, min(2.0, lam_w)))))
        unwind_seg = max(26.0, unwind_base * mod_t)
    else:
        unwind_seg = unwind_base

    if edad_seg < unwind_seg:
        return False
    if mmw.debe_inhibir_maker_unwind_en_rally(
        direccion,
        pnl_pct,
        mfe_pct,
        ofi_5s,
        symbol=symbol,
        vacio_l2_ratio=v_l2,
        lambda_wald=lam_w,
    ):
        return False
    return True
