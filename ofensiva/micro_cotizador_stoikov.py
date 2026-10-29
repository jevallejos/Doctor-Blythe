# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #4: Cotizador Zero-RTT Stoikov Micro-Price, Penny-Jump Quoting
con Filtro de Seleccion Adversa, Cuantizacion Exacta de Ticks y Lotes, y Objetivo
de Cosecha Elastico Acoplado al Percentil Intradia 24h y Vacio L2 (Terpsichora V7.0).
"""
import math
import config_parametros as cfg


def _contar_decimales_paso(paso: float, default_ge_1: int = 2) -> int:
    if paso <= 0.0:
        return 6
    if paso >= 1.0:
        return default_ge_1
    texto = f"{paso:.10f}".rstrip("0")
    if "." in texto:
        return max(0, len(texto.split(".")[1]))
    return max(0, int(round(-math.log10(paso))))


def cuantizar_tick(precio: float, tick_size: float, modo: str = "nearest") -> float:
    if tick_size <= 0.0:
        return round(precio, 6)
    decimales = _contar_decimales_paso(tick_size, default_ge_1=2)
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
    decimales = _contar_decimales_paso(step_size, default_ge_1=0)
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
        sesgo_adverso = (micro_price > 0.0) and (micro_price < (mid - 0.30 * spread))
        pre_lead = (micro_price > (mid + 0.15 * spread)) if micro_price > 0.0 else False
        if not sesgo_adverso and (spread >= (t_size * 1.95) or (pre_lead and spread >= (t_size * 1.50))):
            candidato = min(best_ask - t_size, best_bid + (cfg.OFFSET_PENNY_JUMP_TICKS * t_size))
        else:
            candidato = best_bid
        return cuantizar_tick(candidato, t_size, modo="floor")

    sesgo_adverso_s = (micro_price > 0.0) and (micro_price > (mid + 0.30 * spread))
    pre_lead_s = (micro_price < (mid - 0.15 * spread)) if micro_price > 0.0 else False
    if not sesgo_adverso_s and (spread >= (t_size * 1.95) or (pre_lead_s and spread >= (t_size * 1.50))):
        candidato = max(best_bid + t_size, best_ask - (cfg.OFFSET_PENNY_JUMP_TICKS * t_size))
    else:
        candidato = best_ask
    return cuantizar_tick(candidato, t_size, modo="ceil")


def calcular_tp_dinamico_volatilidad(
    volatilidad_bv: float,
    percentil_24h: float = 0.50,
    vacio_l2_ratio: float = 1.0,
    symbol: str = "",
) -> float:
    """
    Objetivo de cosecha elastico acoplado a la volatilidad Bipower relativa del par,
    al percentil intradia de 24h (P_24h) y a la razon de vacio profundo L2 (V_L2):
    - Resuelve el congelamiento de activos Tier-1 (ARB, AVAX, TAO, XRP) donde
      volatilidad_bv = 0.00055, modulando el objetivo mediante P_24h in [0.05, 0.99]
      y expandiendo cuando V_L2 >= 1.25 (ausencia de resistencia opuesta en L2..L15).
    """
    vol_limpia = max(float(cfg.VOLATILIDAD_BV_PISO_MIN), float(volatilidad_bv))
    piso_elastico = max(
        float(cfg.COSECHA_TRIZ_ACTIVACION_PCT),
        float(cfg.COSECHA_ESTANCAMIENTO_MFE_PCT) + 0.00028,
    )
    tp_base_bv = max(piso_elastico, vol_limpia * 2.65)
    p_24 = max(cfg.PERCENTIL_DIA_MIN, min(cfg.PERCENTIL_DIA_MAX, float(percentil_24h or 0.50)))
    v_l2 = max(0.20, min(3.00, float(vacio_l2_ratio or 1.0)))

    mod_percentil = 1.0 + max(-0.06, 0.48 * (p_24 - 0.50))
    mod_vacio = 1.0 + max(-0.08, min(0.22, 0.25 * (v_l2 - 1.0)))
    if symbol and hasattr(cfg, "obtener_clase_activo") and cfg.obtener_clase_activo(symbol) == cfg.CLASE_TIER1_LIQUIDO:
        tp_candidato = max(piso_elastico, tp_base_bv * mod_percentil * mod_vacio)
    else:
        tp_candidato = max(piso_elastico, tp_base_bv * (0.50 + 0.50 * mod_percentil) * mod_vacio)

    return round(max(piso_elastico, min(0.0032, tp_candidato)), 5)