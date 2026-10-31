# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #5: Gobernador de [ESCAPE_TEMPORAL] (90s), Extension Elastica
para Contratos Runner Post-Cosecha Parcial, Pre-Escape Elastico Pasivo Maker (54s-72s)
y Reconciliador [ESCAPE_HUERFANA_BOOT] con Gracia Post-Lock para Terpsichora V7.0.
"""
from typing import Any, Dict, Tuple

import config_parametros as cfg


def evaluar_escape_temporal_posicion(
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    direccion: str,
    en_proceso_cierre: bool = False,
    max_hold_seg: float = 0.0,
    lambda_wald: float = 0.0,
    vacio_l2_ratio: float = 1.0,
    cosecha_parcial_ejecutada: bool = False,
) -> Tuple[bool, bool, str]:
    tope_hold = float(max_hold_seg if max_hold_seg > 0.0 else cfg.TIEMPO_MAX_HOLD_SEG)
    lam_w = float(lambda_wald or 0.0)
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    es_long = str(direccion).upper() in ("BUY", "LONG")
    ofi_dir = float(ofi_5s) if es_long else -float(ofi_5s)

    runner_protegido = (
        not cfg.es_modo_test()
        and cosecha_parcial_ejecutada
        and pnl_pct >= (2.0 * float(cfg.COMISION_MAKER_PCT))
        and lam_w >= -0.20
        and ofi_dir >= -0.10
    )
    if runner_protegido:
        tope_hold = tope_hold * 1.50

    pre_escape_base = float(cfg.obtener_aux("PRE_ESCAPE_MAKER_SEG", max(60.0, tope_hold - 18.0)))
    if runner_protegido:
        pre_escape_base = tope_hold - 18.0

    if edad_seg >= tope_hold:
        return True, False, "ESCAPE_TEMPORAL"

    adelanto_wald = 8.0 if lam_w <= -2.00 else (4.0 if lam_w <= -1.00 else 0.0)
    adelanto_vacio = 6.0 if v_l2 < 0.65 else 0.0
    adelanto_inerte = 4.0 if (mfe_pct < 0.0005 and pnl_pct <= -0.0008) else 0.0
    pre_escape_seg = max(54.0, pre_escape_base - (adelanto_wald + adelanto_vacio + adelanto_inerte))

    flujo_runner_fuerte = (
        (ofi_dir >= 0.25 and pnl_pct >= 0.0015 and lam_w >= 0.50)
        or (runner_protegido and ofi_dir >= 0.05 and lam_w >= 0.25)
    )
    if edad_seg >= pre_escape_seg and (not en_proceso_cierre) and (not flujo_runner_fuerte):
        return False, True, "PRE_ESCAPE_MAKER_72S"
    return False, False, "OK"


def clasificar_posicion_huerfana_arranque(
    symbol: str,
    side: str,
    contratos: float,
    entry_price: float,
    mark_price: float,
) -> Dict[str, Any]:
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
    px_in = float(entry_price if entry_price > 0.0 else mark_price)
    px_out = float(mark_price if mark_price > 0.0 else px_in)
    if px_in > 0.0:
        pnl_bruto_pct = ((px_out - px_in) / px_in) if dir_norm == "LONG" else ((px_in - px_out) / px_in)
    else:
        pnl_bruto_pct = 0.0
    return {
        "symbol": symbol,
        "direccion": dir_norm,
        "contratos": abs(float(contratos)),
        "precio_entrada": px_in,
        "precio_salida": px_out,
        "pnl_bruto_pct": pnl_bruto_pct,
        "motivo": "ESCAPE_HUERFANA_BOOT",
    }


def debe_adoptar_en_lugar_de_liquidar_huerfana(
    symbol: str,
    locks_pre_fill: dict,
    posiciones_activas: dict,
    now_ts: float,
    grace_seg: float = 5.0,
) -> bool:
    if symbol in posiciones_activas:
        return True
    lock_ts = locks_pre_fill.get(symbol)
    if lock_ts is True:
        return True
    if isinstance(lock_ts, (int, float)):
        val = float(lock_ts)
        if val > 0.0:
            if now_ts <= (val + grace_seg) or abs(now_ts - val) <= grace_seg:
                return True
        elif val < 0.0:
            if (now_ts - abs(val)) <= grace_seg:
                return True
    return False
