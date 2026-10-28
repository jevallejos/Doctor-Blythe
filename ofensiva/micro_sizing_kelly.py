# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #3: Dimensionamiento Kelly 3x y Proteccion Anti-110007 UTA.
Acota el margen requerido por orden al 75% del balance libre real en Bybit UTA,
compensando el lag de liberacion post-cancelacion (<3.0s) cuando Slots == 0/1.
"""
import inspect
import time
from typing import Any, Tuple
import config_parametros as cfg
import core_estado_ram as ram


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
    # Si Slots == 0/1 y hubo una cancelacion reciente (< 4.0s), Bybit UTA puede tardar ~400ms en liberar free_usdt
    if len(pos_activas) == 0 and total_ram > 0.0 and 0.0 < free_ram < (total_ram * 0.75):
        ahora = time.time()
        cancel_reciente = any(isinstance(v, (int, float)) and v < 0.0 and (ahora - abs(float(v))) <= 4.0 for v in locks.values())
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
        for nombre_param, valor in list(bound.arguments.items()):
            if any(k in nombre_param.lower() for k in ("balance", "capital", "usdt", "libre", "equity")):
                if isinstance(valor, (int, float)):
                    balance_usado = sanear_balance_libre_slot_vacio(float(valor))
                    bound.arguments[nombre_param] = balance_usado
                    break
        kelly_f, margen_u, nocional_u = fn(*bound.args, **bound.kwargs)
        if balance_usado > 0.0 and not bool(getattr(cfg, "MODO_PAPER_TRADING", False)):
            lev = float(getattr(cfg, "APALANCAMIENTO_OPERATIVO", 3))
            min_ord = float(getattr(cfg, "ORDEN_MINIMA_BYBIT_USDT", 5.5))
            max_nocional_seguro = round(balance_usado * 0.75 * lev, 4)
            if max_nocional_seguro >= min_ord:
                nocional_u = min(float(nocional_u), max_nocional_seguro)
            else:
                nocional_u = min(float(nocional_u), round(balance_usado * 0.90 * lev, 4))
            margen_u = round(nocional_u / lev, 4)
        return float(kelly_f), float(margen_u), float(nocional_u)
    except Exception:
        return fn(*args, **kwargs)
