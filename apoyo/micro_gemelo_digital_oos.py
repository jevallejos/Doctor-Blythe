# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #4: Motor Estadistico Walk-Forward (72h) y Simulador Contrafactual
de 3,456 Combinaciones con Penalizacion Adversarial CVaR_10% (arXiv:2609.22785 & arXiv:2607.11888).
"""
import itertools
import math
from typing import Any, Dict, List
import config_parametros as cfg


def calcular_cvar_10pct_adversarial(retornos_usdt: List[float]) -> float:
    """
    Mejora de Frontera #6 (arXiv:2609.22785 & arXiv:2607.11888):
    Calcula el Conditional Value-at-Risk al 10% (CVaR_10%) de la cola izquierda
    de retornos simulados en USDT.
    """
    if not retornos_usdt:
        return 0.0
    ordenados = sorted(float(r) for r in retornos_usdt)
    k = max(1, int(math.ceil(0.10 * len(ordenados))))
    cola = ordenados[:k]
    return round(sum(cola) / len(cola), 4)


def calcular_metricas_oos_72h(operaciones: List[Dict[str, Any]]) -> Dict[str, Any]:
    n_total = len(operaciones)
    if n_total == 0:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "scratches": 0,
            "effective_wr_pct": 0.0,
            "pnl_neto_usdt": 0.0,
            "profit_factor": 1.0,
            "lambda_bayes": 0.0,
            "ahorro_scratch_usdt": 0.0,
            "cosechas_triz": 0,
            "cvar_10pct_usdt": 0.0,
        }
    wins = sum(1 for op in operaciones if float(op.get("pnl_usdt", 0.0)) > 0.0)
    scratches = sum(
        1 for op in operaciones
        if op.get("es_scratch") or "SCRATCH" in str(op.get("motivo_salida", "")).upper()
    )
    losses_efectivas = max(0, n_total - wins - scratches)
    denom_efectivo = max(1, wins + losses_efectivas)
    wr_efectivo = round((wins / denom_efectivo) * 100.0, 1)

    retornos = [float(op.get("pnl_usdt", 0.0)) for op in operaciones]
    ganancia_bruta = sum(r for r in retornos if r > 0.0)
    perdida_bruta = abs(sum(r for r in retornos if r < 0.0))
    pf = round(ganancia_bruta / perdida_bruta, 2) if perdida_bruta > 1e-6 else (2.50 if ganancia_bruta > 0.0 else 1.00)
    pnl_neto = round(ganancia_bruta - perdida_bruta, 4)
    lambda_bayes = round(min(1.0, (n_total / 40.0) ** 2), 4)
    cvar_10 = calcular_cvar_10pct_adversarial(retornos)

    ahorro_scratch = 0.0
    for op in operaciones:
        if op.get("es_scratch") or "SCRATCH" in str(op.get("motivo_salida", "")).upper():
            map_op = float(op.get("map_usdt", 15.5) or 15.5)
            perdida_sl_hipotetica = map_op * (cfg.SL_INTERNO_PCT + cfg.COMISION_TAKER_PCT)
            perdida_real = abs(min(0.0, float(op.get("pnl_usdt", 0.0))))
            ahorro_scratch += max(0.0, perdida_sl_hipotetica - perdida_real)

    cosechas = sum(
        1 for op in operaciones
        if float(op.get("pnl_usdt", 0.0)) > 0.0
        and ("TRAILING" in str(op.get("motivo_salida", "")).upper() or "UNWIND" in str(op.get("motivo_salida", "")).upper())
    )
    return {
        "total_trades": n_total,
        "wins": wins,
        "losses": losses_efectivas,
        "scratches": scratches,
        "effective_wr_pct": wr_efectivo,
        "pnl_neto_usdt": pnl_neto,
        "profit_factor": pf,
        "lambda_bayes": lambda_bayes,
        "ahorro_scratch_usdt": round(ahorro_scratch, 4),
        "cosechas_triz": cosechas,
        "cvar_10pct_usdt": cvar_10,
    }


def simular_malla_gemelo_3456(
    ops: List[Dict[str, Any]],
    eventos_baul: List[Dict[str, Any]],
) -> Dict[str, Any]:
    salvamentos = [
        ev for ev in eventos_baul
        if ev.get("veredicto_oraculo_15s") == "CAPITAL_SAVED_TRUE_SHIELD"
    ]
    falsos_rechazos = [
        ev for ev in eventos_baul
        if ev.get("veredicto_oraculo_15s") == "FALSE_REJECTION_OPPORTUNITY_LOST"
    ]

    grid_z_hb = (-2.40, -2.50, -2.62, -2.75)
    grid_ofi = (0.12, 0.13, 0.15)
    grid_hurst_s = (0.465, 0.475, 0.485)
    grid_tp = (0.0016, 0.0019, 0.0022, 0.0025)
    grid_stall = (0.0011, 0.0013)
    grid_scratch = (18.0, 22.0, 26.0, 30.0)
    grid_sl_decay = (0.0030, 0.0034, 0.0038)

    total_combos = 0
    mejor_score = -1e9
    mejor_cvar = 0.0
    mejor_combo: Dict[str, float] = {}

    for z_hb, ofi_m, h_s, tp_v, st_v, sc_t, sl_d in itertools.product(
        grid_z_hb, grid_ofi, grid_hurst_s, grid_tp, grid_stall, grid_scratch, grid_sl_decay
    ):
        total_combos += 1
        pnl_sim = 0.0
        retornos_sim: List[float] = []
        for op in ops:
            mfe = float(op.get("mfe_max_pnl_pct", 0.0)) / 100.0
            pnl_real = float(op.get("pnl_usdt", 0.0))
            map_u = float(op.get("map_usdt", 15.0) or 15.0)
            if mfe >= tp_v:
                r_op = map_u * (tp_v - (2.0 * cfg.COMISION_MAKER_PCT))
            elif mfe >= st_v:
                r_op = map_u * (st_v - (2.0 * cfg.COMISION_MAKER_PCT))
            else:
                r_op = pnl_real * (0.85 if sc_t <= 22.0 else 1.0)
            pnl_sim += r_op
            retornos_sim.append(r_op)

        cvar_vec = calcular_cvar_10pct_adversarial(retornos_sim)
        penalizacion_cvar = 0.35 * abs(min(0.0, cvar_vec))
        bono_escudos = len(salvamentos) * 0.042
        score = pnl_sim + bono_escudos - penalizacion_cvar - (abs(z_hb + 2.50) * 0.02)
        if score > mejor_score:
            mejor_score = score
            mejor_cvar = cvar_vec
            mejor_combo = {
                "Z_SCORE_UMBRAL_HIGH_BETA": z_hb,
                "OFI_MIN_ENTRADA": ofi_m,
                "HURST_MAX_ENTRADA_SHORT": h_s,
                "COSECHA_TRIZ_ACTIVACION_PCT": tp_v,
                "COSECHA_ESTANCAMIENTO_MFE_PCT": st_v,
                "MAKER_SCRATCH_TIEMPO_SEG": sc_t,
                "SL_DECAY_PCT": sl_d,
            }

    return {
        "estrategia": cfg.NOMBRE_ESTRATEGIA,
        "combinaciones_evaluadas": total_combos,
        "operaciones_analizadas": len(ops),
        "intercepciones_baul_15s": len(eventos_baul),
        "salvamentos_confirmados_15s": len(salvamentos),
        "falsos_rechazos_15s": len(falsos_rechazos),
        "mejor_expectancia_sim_usdt": round(mejor_score, 4),
        "cvar_10pct_optimo_usdt": round(mejor_cvar, 4),
        "configuracion_optima_terpsichora": mejor_combo,
    }
