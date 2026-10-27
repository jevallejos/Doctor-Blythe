# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #9: Motor [DIAMOND] Phase 2 Maker Shield PostOnly
y Persecucion Pasiva de Cosecha Ganadora (Active Maker Chase).
"""
from typing import Tuple
import config_parametros as cfg
from ofensiva import micro_cotizador_stoikov as mcs


def evaluar_activacion_escudo_diamante_fase2(
    direccion: str,
    precio_entrada: float,
    precio_actual: float,
    best_bid: float,
    best_ask: float,
    edad_seg: float,
    pnl_pct: float,
    lambda_wald: float,
    tick_size: float,
    fase2_ya_ejecutada: bool = False,
) -> Tuple[bool, float]:
    """
    Evalua si la posicion ganadora califica para armar el [DIAMOND] Phase 2
    Maker Shield PostOnly (como en el Trade #5 de ZEREBRO +0.16%, Lambda=+4.58).
    Retorna (activar: bool, precio_postonly_objetivo: float).
    """
    if fase2_ya_ejecutada or edad_seg < 15.0:
        return False, 0.0

    if pnl_pct < 0.0012 or lambda_wald < 2.0:
        return False, 0.0

    t_sz = max(1e-8, float(tick_size))
    if str(direccion).upper() in ("BUY", "LONG"):
        px_obj = mcs.cuantizar_tick(max(best_ask, precio_actual + t_sz), t_sz, modo="ceil")
        if px_obj <= precio_entrada:
            return False, 0.0
        return True, px_obj
    else:
        px_obj = mcs.cuantizar_tick(min(best_bid, precio_actual - t_sz), t_sz, modo="floor")
        if px_obj >= precio_entrada and precio_entrada > 0.0:
            return False, 0.0
        return True, px_obj


def calcular_intervalo_repeg_salida_maker(motivo: str) -> float:
    m_up = str(motivo).upper()
    if "UNWIND" in m_up or "HARVEST" in m_up or "TRAILING" in m_up or "WALD" in m_up:
        return float(cfg.COSECHA_REPEG_INTERVALO_SEG)
    return 1.80
