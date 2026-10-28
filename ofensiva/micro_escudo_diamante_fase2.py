# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #9: Motor [DIAMOND] Phase 2 Maker Shield PostOnly con
Proyeccion en Cresta para Impulsos Fuertes (Lambda >= 2.80), Expansion en Vacio
de Liquidez L2 (orderbook.50) y Front-Running Quirurgico de Muros Institucionales.
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
    muro_opuesto_px: float = 0.0,
    vacio_l2_ratio: float = 1.0,
) -> Tuple[bool, float]:
    """
    Gobierna el [DIAMOND] Phase 2 Maker Shield PostOnly:
    1. Si existe un Vacio de Liquidez L2 (vacio_l2_ratio >= 1.45) con impulso positivo
       (lambda_wald >= 1.40) o si lambda_wald >= 2.80, proyecta la orden PostOnly en
       la cresta (+0.185% a +0.215%) para no cortar runners como ZEREBRO Trades #6/#7.
    2. Si el escaner L2 detecta un Muro Institucional (muro_opuesto_px > 0) dentro de
       la zona de ganancia, coloca la orden PostOnly exactamente 1 tick delante del muro.
    """
    if fase2_ya_ejecutada or edad_seg < 18.0 or precio_entrada <= 0.0:
        return False, 0.0
    if pnl_pct < 0.00135 or lambda_wald < 0.60:
        return False, 0.0

    t_sz = max(1e-8, float(tick_size))
    es_long = str(direccion).upper() in ("BUY", "LONG")
    vacio_runner = (float(vacio_l2_ratio) >= 1.45) and (lambda_wald >= 1.40) and (edad_seg < 38.0)
    impulso_fuerte_en_curso = ((lambda_wald >= 2.80) or vacio_runner) and (pnl_pct < 0.00195) and (edad_seg < 38.0)
    target_cresta_pct = 0.00210 if vacio_runner else 0.00185

    if es_long:
        if impulso_fuerte_en_curso:
            px_cresta = precio_entrada * (1.0 + target_cresta_pct)
            px_obj = mcs.cuantizar_tick(max(best_ask + t_sz, precio_actual + (2.0 * t_sz), px_cresta), t_sz, modo="ceil")
        else:
            px_obj = mcs.cuantizar_tick(max(best_ask, precio_actual + t_sz), t_sz, modo="ceil")

        if muro_opuesto_px > 0.0:
            px_front_wall = mcs.cuantizar_tick(muro_opuesto_px - t_sz, t_sz, modo="floor")
            piso_min_wall = precio_entrada * (1.0 + max(0.00115, float(cfg.TRINQUETE_BE_OFFSET_PCT) + 0.0004))
            if px_front_wall >= max(best_ask, piso_min_wall):
                px_obj = min(px_obj, px_front_wall) if px_obj > px_front_wall else px_obj

        if px_obj <= precio_entrada:
            return False, 0.0
        return True, px_obj
    else:
        if impulso_fuerte_en_curso:
            px_cresta = precio_entrada * (1.0 - target_cresta_pct)
            px_obj = mcs.cuantizar_tick(min(best_bid - t_sz, precio_actual - (2.0 * t_sz), px_cresta), t_sz, modo="floor")
        else:
            px_obj = mcs.cuantizar_tick(min(best_bid, precio_actual - t_sz), t_sz, modo="floor")

        if muro_opuesto_px > 0.0:
            px_front_wall = mcs.cuantizar_tick(muro_opuesto_px + t_sz, t_sz, modo="ceil")
            techo_max_wall = precio_entrada * (1.0 - max(0.00115, float(cfg.TRINQUETE_BE_OFFSET_PCT) + 0.0004))
            if px_front_wall <= min(best_bid, techo_max_wall):
                px_obj = max(px_obj, px_front_wall) if px_obj < px_front_wall else px_obj

        if px_obj >= precio_entrada:
            return False, 0.0
        return True, px_obj


def calcular_intervalo_repeg_salida_maker(motivo: str) -> float:
    m_up = str(motivo).upper()
    if "UNWIND" in m_up or "HARVEST" in m_up or "TRAILING" in m_up or "WALD" in m_up:
        return float(cfg.COSECHA_REPEG_INTERVALO_SEG)
    return 1.80


def verificar_disparo_fisico_trinquete_be(
    side: str,
    trinquete_be_armado: bool,
    sl_actual: float,
    entry_price: float,
    current_price: float,
    be_offset_pct: float = 0.00065,
) -> tuple[bool, float]:
    if not trinquete_be_armado or current_price <= 0.0 or entry_price <= 0.0:
        return False, float(sl_actual)
    side_u = str(side).upper()
    if side_u in ("LONG", "BUY"):
        piso_be = round(entry_price * (1.0 + be_offset_pct), 8)
        sl_efectivo = max(float(sl_actual), piso_be) if sl_actual > 0 else piso_be
        return bool(current_price <= sl_efectivo), sl_efectivo
    else:
        techo_be = round(entry_price * (1.0 - be_offset_pct), 8)
        sl_efectivo = min(float(sl_actual), techo_be) if sl_actual > 0 else techo_be
        return bool(current_price >= sl_efectivo), sl_efectivo
