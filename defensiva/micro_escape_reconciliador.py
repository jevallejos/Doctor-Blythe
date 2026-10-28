# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #5: Gobernador de [ESCAPE_TEMPORAL] (90s),
Pre-Escape Pasivo Maker (72s) y Reconciliador [ESCAPE_HUERFANA_BOOT] con Gracia Post-Lock.
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
) -> Tuple[bool, bool, str]:
    """
    Retorna (forzar_escape_mercado_90s, activar_pre_escape_maker_72s, motivo).
    - A los 72.0s (PRE_ESCAPE_MAKER_SEG): si la posicion no va en rally Runner,
      inicia evacuacion pasiva PostOnly para ahorrar comision Taker.
    - A los 90.0s (TIEMPO_MAX_HOLD_SEG): dispara cierre de seguridad ESCAPE_TEMPORAL.
    """
    tope_hold = float(max_hold_seg if max_hold_seg > 0.0 else cfg.TIEMPO_MAX_HOLD_SEG)
    pre_escape_seg = float(cfg.obtener_aux("PRE_ESCAPE_MAKER_SEG", max(60.0, tope_hold - 18.0)))
    if edad_seg >= tope_hold:
        return True, False, "ESCAPE_TEMPORAL"
    es_long = str(direccion).upper() in ("BUY", "LONG")
    flujo_runner_fuerte = (
        (es_long and ofi_5s >= 0.25 and pnl_pct >= 0.0015)
        or ((not es_long) and ofi_5s <= -0.25 and pnl_pct >= 0.0015)
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
    """
    Evalua la posicion detectada en Bybit UTA durante el arranque para
    registrar y ejecutar [ESCAPE_HUERFANA_BOOT] con trazabilidad completa.
    """
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
    """
    Impide que el reconciliador liquide a mercado como ESCAPE_HUERFANA_BOOT
    una posicion que acaba de ser abierta por el Sniper:
    - Si lock_ts > 0: orden en vuelo (expira en lock_ts) o recien expirada.
    - Si lock_ts < 0: lock liberado en abs(lock_ts); protege durante grace_seg (5.0s).
    """
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
