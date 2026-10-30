# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #6: Motor de Conviccion Asimetrica Kelly, Acelerador
Compuesto House-Money Inmune a Depositos Externos (PARITY_SYNC), Penalizacion
Termodinamica por Entropia/Cancelacion L1 y Expansion Convexa de Outliers.
"""
import math
import sys
from typing import Tuple

import config_parametros as cfg
import core_estado_ram as ram


def calcular_bono_house_money() -> float:
    total = float(getattr(ram.ESTADO_GLOBAL, "capital_total_uta", 0.0) or 0.0)
    base_depositada = float(cfg.CAPITAL_BASE_HISTORICO_USDT)
    if not cfg.es_modo_test():
        try:
            st_mod = sys.modules.get("stats_tracker")
            if st_mod is not None and hasattr(st_mod, "GESTOR_ESTADISTICAS"):
                gestor = getattr(st_mod, "GESTOR_ESTADISTICAS")
                base_st = float(getattr(gestor, "base_balance_usdt", base_depositada) or base_depositada)
                ajuste_paridad = float(getattr(gestor, "ajuste_paridad_usdt", 0.0) or 0.0)
                base_depositada = max(0.01, base_st + ajuste_paridad)
        except Exception:
            pass
    if total <= base_depositada or base_depositada <= 0.0:
        return 0.0
    ganancia_pct = (total - base_depositada) / base_depositada
    return round(min(0.06, ganancia_pct * 0.45), 4)


def obtener_multiplicador_kelly_par(symbol: str) -> float:
    if cfg.es_modo_test() or not symbol:
        return 1.0
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    w = float(ctrl.get(f"w_kelly_{symbol}", 1.0) or 1.0)
    return max(0.72, min(1.12, w))


def calcular_fraccion_kelly_antifragil(
    z_score: float,
    ofi: float,
    hurst: float = 0.42,
    side: str = "LONG",
    symbol: str = "",
    irrev_lob: float = 0.0,
    cancel_net_l1: float = 0.0,
    vacio_l2_ratio: float = 1.0,
) -> float:
    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
    es_t1 = bool(symbol and cfg.obtener_clase_activo(symbol) == cfg.CLASE_TIER1_LIQUIDO)

    if dir_norm == "SHORT":
        base_k = float(ctrl.get("w5_kelly_short", cfg.KELLY_SHORT_SNIPER_FRACCION))
        z_ref = float(cfg.Z_SCORE_SHORT_UMBRAL)
    elif es_t1:
        base_k = float(ctrl.get("w5_kelly_long", cfg.KELLY_LONG_TIER1_FRACCION))
        z_ref = abs(float(cfg.Z_SCORE_UMBRAL_TIER1))
    else:
        base_k = float(cfg.KELLY_FRACCION_BASE)
        z_ref = abs(float(cfg.Z_SCORE_UMBRAL_HIGH_BETA))

    if symbol and not cfg.es_modo_test():
        m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
        if m_live is not None:
            if irrev_lob == 0.0:
                irrev_lob = float(getattr(m_live, "irrev_lob", 0.0) or 0.0)
            if cancel_net_l1 == 0.0:
                cancel_net_l1 = float(getattr(m_live, "cancel_net_l1", 0.0) or 0.0)
            if vacio_l2_ratio == 1.0:
                vacio_l2_ratio = float(getattr(m_live, "vacio_l2_ratio", 1.0) or 1.0)

    z_abs = abs(float(z_score))
    ofi_abs = abs(float(ofi))
    h_val = max(0.15, min(0.80, float(hurst)))

    exceso_z = max(0.0, z_abs - max(1.80, z_ref))
    bono_conviccion = min(0.12, exceso_z * 0.028 + max(0.0, ofi_abs - 0.18) * 0.08)
    bono_hm = calcular_bono_house_money()
    penalizacion_hurst = max(0.0, (h_val - 0.44) * 0.35)

    signo_dir = 1.0 if dir_norm == "LONG" else -1.0
    cancel_dir = signo_dir * float(cancel_net_l1)
    penal_entropia = 0.16 * max(0.0, float(irrev_lob) - 0.72)
    penal_cancel = 0.08 * max(0.0, -cancel_dir - 0.45) if cancel_dir < -0.45 else 0.0
    bono_vacio = min(0.025, 0.04 * max(0.0, float(vacio_l2_ratio) - 1.25))

    mult_ia = max(
        cfg.MULTIPLICADOR_IA_MIN,
        min(cfg.MULTIPLICADOR_IA_MAX, float(ram.ESTADO_GLOBAL.multiplicador_kelly_ia)),
    )
    kelly_bruto = (
        base_k + bono_conviccion + bono_hm + bono_vacio
        - penalizacion_hurst - penal_entropia - penal_cancel
    ) * mult_ia
    return round(max(cfg.KELLY_FRACCION_MIN, min(cfg.KELLY_FRACCION_MAX, kelly_bruto)), 4)


def calcular_dimension_kelly(
    capital_libre_usdt: float,
    z_score: float,
    ofi: float,
    hurst: float = 0.42,
    side: str = "LONG",
    symbol: str = "",
    irrev_lob: float = 0.0,
    cancel_net_l1: float = 0.0,
    vacio_l2_ratio: float = 1.0,
) -> Tuple[float, float, float]:
    frac = calcular_fraccion_kelly_antifragil(
        z_score=z_score,
        ofi=ofi,
        hurst=hurst,
        side=side,
        symbol=symbol,
        irrev_lob=irrev_lob,
        cancel_net_l1=cancel_net_l1,
        vacio_l2_ratio=vacio_l2_ratio,
    )
    z_abs = abs(float(z_score))
    ofi_abs = abs(float(ofi))
    gamma_outlier = 1.0
    if z_abs >= 6.0 and ofi_abs >= 0.25 and float(hurst) <= 0.485:
        gamma_outlier = 1.0 + (0.15 * math.tanh((z_abs - 6.0) / 5.0))

    cap_utilizable = max(0.0, float(capital_libre_usdt) * (1.0 - cfg.MARGEN_SEGURIDAD_LIQUIDACION))
    margen_usdt = round(float(capital_libre_usdt) * min(0.68, frac * gamma_outlier), 4)
    if cap_utilizable > 0.0:
        margen_usdt = min(margen_usdt, round(cap_utilizable, 4))
    nocional_usdt = round(margen_usdt * float(cfg.APALANCAMIENTO_OPERATIVO), 4)
    return frac, margen_usdt, nocional_usdt
