# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #4: Cotizador Zero-RTT Stoikov Micro-Price, Penny-Jump Quoting
y Cuantizacion Exacta de Ticks y Lotes para Bybit UTA V5.
"""
import math
import config_parametros as cfg


def cuantizar_tick(precio: float, tick_size: float, modo: str = "nearest") -> float:
    if tick_size <= 0.0:
        return round(precio, 6)
    decimales = max(0, int(round(-math.log10(tick_size)))) if tick_size < 1.0 else 2
    unidades = precio / tick_size
    if modo == "floor":
        val = math.floor(unidades + 1e-9) * tick_size
    elif modo == "ceil":
        val = math.ceil(unidades - 1e-9) * tick_size
    else:
        val = round(unidades) * tick_size
    return round(val, decimales)


def cuantizar_lote(cantidad: float, step_size: float) -> float:
    if step_size <= 0.0:
        return round(cantidad, 4)
    decimales = max(0, int(round(-math.log10(step_size)))) if step_size < 1.0 else 0
    val = math.floor((cantidad / step_size) + 1e-9) * step_size
    return round(val, decimales)


def calcular_precio_penny_jump(
    best_bid: float,
    best_ask: float,
    tick_size: float,
    side: str,
    micro_price: float = 0.0,
) -> float:
    t_size = max(1e-8, float(tick_size))
    spread = best_ask - best_bid
    mid = 0.5 * (best_bid + best_ask)
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
    if dir_norm == "LONG":
        pre_lead = (micro_price > (mid + 0.15 * spread)) if micro_price > 0.0 else False
        if spread >= (t_size * 1.95) or (pre_lead and spread >= (t_size * 1.50)):
            candidato = min(best_ask - t_size, best_bid + (cfg.OFFSET_PENNY_JUMP_TICKS * t_size))
        else:
            candidato = best_bid
        return cuantizar_tick(candidato, t_size, modo="floor")
    pre_lead_s = (micro_price < (mid - 0.15 * spread)) if micro_price > 0.0 else False
    if spread >= (t_size * 1.95) or (pre_lead_s and spread >= (t_size * 1.50)):
        candidato = max(best_bid + t_size, best_ask - (cfg.OFFSET_PENNY_JUMP_TICKS * t_size))
    else:
        candidato = best_ask
    return cuantizar_tick(candidato, t_size, modo="ceil")


def calcular_tp_dinamico_volatilidad(volatilidad_bv: float) -> float:
    """
    Objetivo de cosecha elastico acoplado a la volatilidad Bipower realizada:
    - En regimenes de volatilidad moderada (vol_bv ~ 0.00055 - 0.00065, como
      WAL y ZEREBRO donde el MFE natural hace techo en +0.166% a +0.190%),
      situa la activacion de cosecha en +0.168% a +0.188%.
    - En alta volatilidad (vol_bv >= 0.00076), escala hacia +0.22% - +0.32%.
    """
    vol_limpia = max(float(cfg.VOLATILIDAD_BV_PISO_MIN), float(volatilidad_bv))
    piso_elastico = max(float(cfg.COSECHA_ESTANCAMIENTO_MFE_PCT) + 0.00038, 0.00168)
    return max(piso_elastico, min(0.0032, vol_limpia * 2.90))
