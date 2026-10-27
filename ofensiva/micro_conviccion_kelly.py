# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #6: Motor de Conviccion Asimetrica Kelly, Acelerador
Compuesto House-Money y Expansion Convexa de Outliers (|Z| >= 6.0 -> gamma <= 1.15).
"""
import math
from typing import Tuple
import config_parametros as cfg
import core_estado_ram as ram


def calcular_bono_house_money() -> float:
    """
    Si el capital total UTA supera la semilla base, reinvierte una fraccion suave
    de la ganancia acumulada (+1% a +6% extra de conviccion) sin arriesgar el capital base.
    """
    total = float(getattr(ram.ESTADO_GLOBAL, "capital_total_uta", 0.0) or 0.0)
    base = float(cfg.CAPITAL_BASE_HISTORICO_USDT)
    if total <= base or base <= 0.0:
        return 0.0
    ganancia_pct = (total - base) / base
    return round(min(0.06, ganancia_pct * 0.45), 4)


def calcular_fraccion_kelly_antifragil(
    z_score: float,
    ofi: float,
    hurst: float = 0.42,
    side: str = "LONG",
    symbol: str = "",
) -> float:
    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
    if dir_norm == "SHORT":
        base_k = float(ctrl.get("w5_kelly_short", cfg.KELLY_SHORT_SNIPER_FRACCION))
    else:
        if symbol and cfg.obtener_clase_activo(symbol) == cfg.CLASE_TIER1_LIQUIDO:
            base_k = float(ctrl.get("w5_kelly_long", cfg.KELLY_LONG_TIER1_FRACCION))
        else:
            base_k = float(cfg.KELLY_FRACCION_BASE)
    z_abs = abs(float(z_score))
    ofi_abs = abs(float(ofi))
    h_val = max(0.15, min(0.80, float(hurst)))
    exceso_z = max(0.0, z_abs - 2.50)
    bono_conviccion = min(0.12, exceso_z * 0.028 + max(0.0, ofi_abs - 0.18) * 0.08)
    bono_hm = calcular_bono_house_money()
    penalizacion_hurst = max(0.0, (h_val - 0.44) * 0.35)
    mult_ia = max(
        cfg.MULTIPLICADOR_IA_MIN,
        min(cfg.MULTIPLICADOR_IA_MAX, float(ram.ESTADO_GLOBAL.multiplicador_kelly_ia)),
    )
    kelly_bruto = (base_k + bono_conviccion + bono_hm - penalizacion_hurst) * mult_ia
    return round(max(cfg.KELLY_FRACCION_MIN, min(cfg.KELLY_FRACCION_MAX, kelly_bruto)), 4)


def calcular_dimension_kelly(
    capital_libre_usdt: float,
    z_score: float,
    ofi: float,
    hurst: float = 0.42,
    side: str = "LONG",
    symbol: str = "",
) -> Tuple[float, float, float]:
    frac = calcular_fraccion_kelly_antifragil(
        z_score=z_score,
        ofi=ofi,
        hurst=hurst,
        side=side,
        symbol=symbol,
    )
    z_abs = abs(float(z_score))
    ofi_abs = abs(float(ofi))
    gamma_outlier = 1.0
    if z_abs >= 6.0 and ofi_abs >= 0.25 and float(hurst) <= 0.485:
        gamma_outlier = 1.0 + (0.15 * math.tanh((z_abs - 6.0) / 5.0))
    cap_utilizable = max(0.0, float(capital_libre_usdt) * (1.0 - cfg.MARGEN_SEGURIDAD_LIQUIDACION))
    margen_usdt = round(float(capital_libre_usdt) * frac * gamma_outlier, 4)
    if cap_utilizable > 0.0:
        margen_usdt = min(margen_usdt, round(cap_utilizable, 4))
    nocional_usdt = round(margen_usdt * float(cfg.APALANCAMIENTO_OPERATIVO), 4)
    return frac, margen_usdt, nocional_usdt
