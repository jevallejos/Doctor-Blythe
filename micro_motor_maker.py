# -*- coding: utf-8 -*-
"""
Micro-Modulo Independiente de Ejecucion y Cosecha Maker (Moallemi & Bybit PostOnly).
Aisla la matematica de supervivencia en cola L1, Penny-Jump controlado y
cosecha ganadora Maker-to-Maker sin tocar los modulos troncales.
"""
from typing import Tuple
import config_parametros as cfg


def evaluar_aborto_cola_moallemi(
    direccion: str,
    q_l1_inicial: float,
    q_l1_actual: float,
    ofi_actual: float,
    h_actual: float,
    edad_orden_seg: float,
) -> Tuple[bool, str]:
    grace_seg = float(getattr(cfg, "MOALLEMI_MIN_AGE_ABORT_SEG", 0.32))
    if edad_orden_seg < grace_seg:
        return False, "GRACE_WINDOW"

    ratio_min = float(getattr(cfg, "MOALLEMI_QUEUE_DEPLETION_ABORT_RATIO", 0.32))
    ofi_flip = float(getattr(cfg, "MOALLEMI_OFI_ADVERSE_ABORT_THRESHOLD", 0.18))
    h_abort = float(getattr(cfg, "MOALLEMI_HURST_ABORT_THRESHOLD", 0.54))

    ratio_cola = (q_l1_actual / q_l1_inicial) if q_l1_inicial > 0.0 else 1.0
    cola_erosionada = (q_l1_inicial > 0.0) and (ratio_cola < ratio_min)

    ofi_adverso = (
        (direccion == "LONG" and ofi_actual < -ofi_flip)
        or (direccion == "SHORT" and ofi_actual > ofi_flip)
    )

    flujo_a_favor_fuerte = (
        (direccion == "LONG" and ofi_actual >= 0.10)
        or (direccion == "SHORT" and ofi_actual <= -0.10)
    )
    hurst_toxico = (h_actual > h_abort) and (not flujo_a_favor_fuerte)

    if cola_erosionada or ofi_adverso or hurst_toxico:
        return (
            True,
            f"Q_L1={q_l1_actual:.1f}/{q_l1_inicial:.1f}, H={h_actual:.2f}, OFI={ofi_actual:+.2f}",
        )
    return False, "OK"


def evaluar_salto_punta_penny(
    direccion: str,
    precio_orden: float,
    bid_actual: float,
    ask_actual: float,
    tick_size: float,
    ofi_actual: float,
    h_actual: float,
    re_pegs_realizados: int,
    edad_en_nivel_seg: float = 1.0,
) -> Tuple[bool, float]:
    if not bool(getattr(cfg, "PENNY_JUMP_HABILITADO", True)):
        return False, precio_orden

    max_pegs_efectivo = min(int(getattr(cfg, "PENNY_JUMP_MAX_REPEGS", 2)), 1)
    if re_pegs_realizados >= max_pegs_efectivo or tick_size <= 0.0:
        return False, precio_orden

    if edad_en_nivel_seg < 0.90:
        return False, precio_orden

    h_max = float(getattr(cfg, "MOALLEMI_HURST_ABORT_THRESHOLD", 0.54))
    if h_actual >= h_max:
        return False, precio_orden

    spread = ask_actual - bid_actual
    if spread <= 0.0:
        return False, precio_orden

    if direccion == "LONG":
        if bid_actual > (precio_orden + 0.5 * tick_size) and ofi_actual >= 0.35:
            nuevo_px = min(bid_actual, ask_actual - tick_size)
            if nuevo_px > precio_orden:
                return True, round(nuevo_px, 8)
    else:
        if ask_actual < (precio_orden - 0.5 * tick_size) and ofi_actual <= -0.35:
            nuevo_px = max(ask_actual, bid_actual + tick_size)
            if nuevo_px < precio_orden:
                return True, round(nuevo_px, 8)

    return False, precio_orden
