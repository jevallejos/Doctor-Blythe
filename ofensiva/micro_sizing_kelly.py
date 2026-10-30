# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #3: Dimensionamiento Kelly 3x, Conviccion Bayesiana por Par,
Regulacion Concava C1 de Huella de Liquidez L1 y Proteccion Anti-110007 UTA.
"""
import inspect
import math
import sys
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


def acotar_nocional_por_liquidez_l1_y_racha(
    nocional_kelly_usdt: float,
    liquidez_l1_usdt: float,
    edge_ratio_par: float = 1.0,
    pnl_neto_ultimos_10: float = 0.0,
    map_historico_usdt: float = 14.0,
) -> float:
    """Acota de forma continua C1 el nocional de disparo segun la liquidez en punta L1 y el PnL reciente."""
    noc_base = float(nocional_kelly_usdt)
    if float(liquidez_l1_usdt) <= 0.0:
        return noc_base
    factor_edge = math.tanh(max(0.35, float(edge_ratio_par)))
    cota_l1 = max(float(cfg.ORDEN_MINIMA_BYBIT_USDT), 0.18 * float(liquidez_l1_usdt) * factor_edge)
    escala_pnl = max(0.02, 0.0035 * float(map_historico_usdt))
    sig_racha = 1.0 / (1.0 + math.exp(-float(pnl_neto_ultimos_10) / escala_pnl))
    cota_racha = max(float(cfg.ORDEN_MINIMA_BYBIT_USDT), float(map_historico_usdt) * (0.85 + 0.65 * sig_racha))
    return round(min(noc_base, max(noc_base * 0.55, min(cota_l1, cota_racha))), 4)


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

        if symbol_usado and not cfg.es_modo_test():
            w_par = float(mck.obtener_multiplicador_kelly_par(symbol_usado))
            if abs(w_par - 1.0) > 1e-4:
                kelly_f = round(min(tope_kelly_max, max(piso_kelly_min, float(kelly_f) * w_par)), 4)
                nocional_u = round(max(min_ord, float(nocional_u) * w_par), 4)
                margen_u = round(nocional_u / lev, 4)

            ctrl_ram = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
            edge_par = max(0.35, float(ctrl_ram.get(f"edge_post_{symbol_usado}", 1.0) or 1.0))
            m_live_k = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol_usado)
            liq_l1_real = 0.0
            vacio_r = 1.0
            if m_live_k is not None and float(getattr(m_live_k, "mid", 0.0) or 0.0) > 0.0:
                q_punta = max(float(getattr(m_live_k, "bid_qty", 0.0) or 0.0), float(getattr(m_live_k, "ask_qty", 0.0) or 0.0))
                liq_l1_real = float(m_live_k.mid) * q_punta
                vacio_r = float(getattr(m_live_k, "vacio_l2_ratio", 1.0) or 1.0)

            if cfg.obtener_clase_activo(symbol_usado) == cfg.CLASE_HIGH_BETA:
                escala_hb = 32.0 * (0.85 + 0.15 * min(1.5, vacio_r))
                nocional_u = round(escala_hb * math.tanh(float(nocional_u) / escala_hb), 4) if float(nocional_u) > escala_hb else float(nocional_u)

            pnl_10_real = 0.0
            map_hist_real = max(float(nocional_u), 12.0)
            st_mod_k = sys.modules.get("stats_tracker")
            if st_mod_k is not None and hasattr(st_mod_k, "GESTOR_ESTADISTICAS"):
                ops_k = list(getattr(st_mod_k.GESTOR_ESTADISTICAS, "operaciones", []) or [])[-10:]
                if ops_k:
                    pnl_10_real = sum(float(x.get("pnl_usdt", 0.0) or 0.0) for x in ops_k)
                    map_hist_real = max(min_ord, sum(float(x.get("map_usdt", 12.0) or 12.0) for x in ops_k) / len(ops_k))

            cota_l1_racha = acotar_nocional_por_liquidez_l1_y_racha(
                float(nocional_u),
                liq_l1_real,
                edge_ratio_par=edge_par,
                pnl_neto_ultimos_10=pnl_10_real,
                map_historico_usdt=map_hist_real,
            )
            nocional_u = round(max(min_ord, min(float(nocional_u), cota_l1_racha)), 4)
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
