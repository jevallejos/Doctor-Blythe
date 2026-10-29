# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #3: Dimensionamiento Kelly 3x, Conviccion Bayesiana por Par,
Regulacion Concava Automatica de Huella de Liquidez L1 en High-Beta y Proteccion
Anti-110007 UTA (75% Margen Libre + Compensacion de Lag Post-Cancelacion).
"""
import inspect
import math
import time
from typing import Any, Tuple
import config_parametros as cfg
import core_estado_ram as ram
from ofensiva import micro_conviccion_kelly as mck


def resolver_capital_base_uta(balance_libre_crudo: float) -> float:
    libre = float(balance_libre_crudo or 0.0)
    est = getattr(ram, "ESTADO_GLOBAL", None)
    if est is None:
        return round(libre, 4)
    free_ram = float(getattr(est, "free_usdt", 0.0) or 0.0)
    total_ram = float(getattr(est, "total_usdt", 0.0) or 0.0)
    pos_activas = getattr(est, "posiciones_activas", {}) or {}
    locks = getattr(est, "locks_pre_fill", {}) or {}
    if libre > 0.0 and abs(libre - float(cfg.CAPITAL_BASE_HISTORICO_USDT)) > 1e-4 and libre != free_ram:
        return round(libre, 4)
    if len(pos_activas) == 0 and total_ram > 0.0 and 0.0 < free_ram < (total_ram * 0.75):
        ahora = time.time()
        cancel_reciente = any(
            isinstance(v, (int, float)) and v < 0.0 and (ahora - abs(float(v))) <= 4.0
            for v in locks.values()
        )
        if cancel_reciente:
            return round(total_ram * 0.95, 4)
    if free_ram > 0.0:
        return round(free_ram, 4)
    return round(libre, 4)


def sanear_balance_libre_slot_vacio(balance_libre_crudo: float) -> float:
    return resolver_capital_base_uta(balance_libre_crudo)


def calcular_dimension_kelly_uta(
    tri_mod: Any,
    *args: Any,
    **kwargs: Any,
) -> Tuple[float, float, float]:
    fn = tri_mod.calcular_dimension_kelly
    try:
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        balance_usado = 0.0
        symbol_usado = ""
        for nombre_param, valor in list(bound.arguments.items()):
            nl = nombre_param.lower()
            if any(k in nl for k in ("balance", "capital", "usdt", "libre", "equity")):
                if isinstance(valor, (int, float)):
                    balance_usado = sanear_balance_libre_slot_vacio(float(valor))
                    bound.arguments[nombre_param] = balance_usado
            elif any(k in nl for k in ("symbol", "par", "asset")) and isinstance(valor, str):
                symbol_usado = valor

        kelly_f, margen_u, nocional_u = fn(*bound.args, **bound.kwargs)

        tope_kelly_max = float(getattr(cfg, "KELLY_FRACCION_MAX", 0.62))
        piso_kelly_min = float(getattr(cfg, "KELLY_FRACCION_MIN", 0.35))
        lev = float(getattr(cfg, "APALANCAMIENTO_OPERATIVO", 3))
        min_ord = float(getattr(cfg, "ORDEN_MINIMA_BYBIT_USDT", 5.5))

        if symbol_usado and not cfg.es_modo_test() and hasattr(mck, "obtener_multiplicador_kelly_par"):
            w_par = float(mck.obtener_multiplicador_kelly_par(symbol_usado))
            if abs(w_par - 1.0) > 1e-4:
                kelly_f = round(min(tope_kelly_max, max(piso_kelly_min, float(kelly_f) * w_par)), 4)
                nocional_u = round(max(min_ord, float(nocional_u) * w_par), 4)
                margen_u = round(nocional_u / lev, 4)

        # Amortiguacion concava de huella L1 para CLASE_HIGH_BETA cuando el capital crece
        if (
            symbol_usado
            and not cfg.es_modo_test()
            and cfg.obtener_clase_activo(symbol_usado) == cfg.CLASE_HIGH_BETA
            and float(nocional_u) > 30.0
        ):
            vacio_r = 1.0
            m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol_usado)
            if m_live is not None:
                vacio_r = float(getattr(m_live, "vacio_l2_ratio", 1.0) or 1.0)
            techo_hb = 55.0 if vacio_r >= 1.10 else (42.0 if vacio_r < 0.85 else 48.0)
            nocional_amortiguado = min(
                techo_hb,
                30.0 + (4.5 * math.sqrt(max(0.0, float(nocional_u) - 30.0))),
            )
            nocional_u = round(max(min_ord, min(float(nocional_u), nocional_amortiguado)), 4)
            margen_u = round(nocional_u / lev, 4)

        if balance_usado > 0.0 and not bool(getattr(cfg, "MODO_PAPER_TRADING", False)):
            max_nocional_seguro = round(balance_usado * 0.75 * lev, 4)
            if max_nocional_seguro >= min_ord:
                nocional_u = min(float(nocional_u), max_nocional_seguro)
            else:
                nocional_u = min(float(nocional_u), round(balance_usado * 0.90 * lev, 4))
            margen_u = round(nocional_u / lev, 4)
        return float(kelly_f), float(margen_u), float(nocional_u)
    except Exception:
        return fn(*args, **kwargs)
