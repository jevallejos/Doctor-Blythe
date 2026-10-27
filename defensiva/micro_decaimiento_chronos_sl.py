# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #7: Compresion Temporal Estocastica del Stop-Loss Interno
(CHRONOS Time-Decay SL) para Posiciones Estancadas.
"""
import config_parametros as cfg
import core_estado_ram as ram
from ofensiva import micro_cotizador_stoikov as mcs


def calcular_sl_interno_chronos(
    precio_entrada: float,
    direccion: str,
    sl_actual: float,
    edad_seg: float,
    mfe_pct: float,
    tick_size: float,
    trinquete_be_activo: bool = False,
) -> float:
    """
    Si una posicion supera w4_unwind_seg (42s) sin haber activado el trinquete
    Break-Even y con MFE < +0.10%, comprime el Stop-Loss interno desde -0.45%
    hacia -w4_sl_decay_pct (-0.32%), cuantizado al tick_size.
    """
    if trinquete_be_activo or precio_entrada <= 0.0:
        return sl_actual

    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    unwind_seg = float(ctrl.get("w4_unwind_seg", 42.0))
    if edad_seg < unwind_seg or mfe_pct >= 0.0010:
        return sl_actual

    sl_decay_pct = float(ctrl.get("w4_sl_decay_pct", 0.0032))
    sl_base_pct = float(cfg.SL_INTERNO_PCT)
    progreso = min(1.0, max(0.0, (edad_seg - unwind_seg) / 30.0))
    dist_pct = sl_base_pct - progreso * max(0.0, sl_base_pct - sl_decay_pct)

    t_sz = max(1e-8, float(tick_size))
    if str(direccion).upper() in ("BUY", "LONG"):
        candidato = mcs.cuantizar_tick(precio_entrada * (1.0 - dist_pct), t_sz, modo="floor")
        return max(sl_actual, candidato)
    else:
        candidato = mcs.cuantizar_tick(precio_entrada * (1.0 + dist_pct), t_sz, modo="ceil")
        return min(sl_actual, candidato) if sl_actual > 0.0 else candidato
