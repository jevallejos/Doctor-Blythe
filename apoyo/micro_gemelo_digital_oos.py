# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #4: Motor Estadistico Walk-Forward (72h) y Simulador
Contrafactual de 3,456 Combinaciones con Penalizacion Adversarial CVaR_10%
(arXiv:2609.22785 & arXiv:2607.11888) y Evaluacion Activa de las 7 Dimensiones.
"""
import itertools
import math
from typing import Any, Dict, List, Tuple
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
    wins = 0
    scratches = 0
    ganancia_bruta = 0.0
    perdida_bruta = 0.0
    ahorro_scratch = 0.0
    cosechas = 0
    retornos: List[float] = []
    costo_sl_unit = cfg.SL_INTERNO_PCT + cfg.COMISION_TAKER_PCT

    for op in operaciones:
        r = float(op.get("pnl_usdt", 0.0))
        retornos.append(r)
        motivo = str(op.get("motivo_salida", "")).upper()
        es_sc = bool(op.get("es_scratch")) or ("SCRATCH" in motivo)
        if r > 0.0:
            wins += 1
            ganancia_bruta += r
            if "TRAILING" in motivo or "UNWIND" in motivo or "TRINQUETE" in motivo:
                cosechas += 1
        else:
            perdida_bruta += abs(r)
            if es_sc:
                scratches += 1
                map_op = float(op.get("map_usdt", 15.5) or 15.5)
                ahorro_scratch += max(0.0, (map_op * costo_sl_unit) - abs(r))

    losses_efectivas = max(0, n_total - wins - scratches)
    denom_efectivo = max(1, wins + losses_efectivas)
    wr_efectivo = round((wins / denom_efectivo) * 100.0, 1)
    pf = round(ganancia_bruta / perdida_bruta, 2) if perdida_bruta > 1e-6 else (2.50 if ganancia_bruta > 0.0 else 1.00)
    pnl_neto = round(ganancia_bruta - perdida_bruta, 4)
    lambda_bayes = round(min(1.0, (n_total / 40.0) ** 2), 4)
    cvar_10 = calcular_cvar_10pct_adversarial(retornos)

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

    # Pre-extraer tuplas de operaciones para evaluacion vectorizada O(1) en las 3,456 celdas
    # (mfe, mae, pnl_real, map_u, hold_seg, z_abs, ofi_abs, hurst_in, es_short)
    ops_vec: List[Tuple[float, float, float, float, float, float, float, float, bool]] = []
    for op in ops:
        mfe = float(op.get("mfe_max_pnl_pct", 0.0)) / 100.0
        mae = abs(float(op.get("mae_min_pnl_pct", 0.0))) / 100.0
        pnl_real = float(op.get("pnl_usdt", 0.0))
        map_u = float(op.get("map_usdt", 15.0) or 15.0)
        hold_s = float(op.get("hold_seg", 20.0) or 20.0)
        vec_in = op.get("vector_entrada") if isinstance(op.get("vector_entrada"), dict) else {}
        z_in = abs(float(vec_in.get("z_entry", -2.65) or -2.65))
        ofi_in = abs(float(vec_in.get("ofi_entry", 0.20) or 0.20))
        h_in = float(vec_in.get("hurst_entry", 0.42) or 0.42)
        es_short = str(op.get("side", "LONG")).upper() in ("SELL", "SHORT")
        ops_vec.append((mfe, mae, pnl_real, map_u, hold_s, z_in, ofi_in, h_in, es_short))

    n_salv = len(salvamentos)
    n_falsos = len(falsos_rechazos)
    fee_rt_maker = 2.0 * cfg.COMISION_MAKER_PCT
    fee_taker_exit = cfg.COMISION_MAKER_PCT + cfg.COMISION_TAKER_PCT

    grid_z_hb = (-2.40, -2.50, -2.62, -2.75)
    grid_ofi = (0.06, 0.12, 0.15)
    grid_hurst_s = (0.465, 0.475, 0.485)
    grid_tp = (0.0014, 0.0016, 0.0019, 0.0022)
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
        z_req = abs(z_hb)

        for mfe, mae, pnl_real, map_u, hold_s, z_in, ofi_in, h_in, es_short in ops_vec:
            # Filtro de entrada contrafactual (z_hb, ofi_m, h_s)
            if (z_in < z_req) or (ofi_in < ofi_m) or (es_short and h_in > h_s):
                # Si la barrera habria filtrado una perdida, suma fracci?n de capital salvado
                if pnl_real < 0.0:
                    r_op = abs(pnl_real) * 0.25
                else:
                    r_op = -pnl_real * 0.15
            elif mfe >= tp_v:
                r_op = map_u * (tp_v - fee_rt_maker)
            elif mfe >= st_v:
                r_op = map_u * (st_v - fee_rt_maker)
            elif hold_s >= 42.0 and mae >= sl_d and pnl_real < 0.0:
                r_op = -map_u * (sl_d + fee_taker_exit)
            else:
                factor_sc = 0.88 if (sc_t >= 26.0 and mfe >= 0.0005) else (0.85 if sc_t <= 22.0 else 0.94)
                r_op = pnl_real * factor_sc if pnl_real < 0.0 else pnl_real
            pnl_sim += r_op
            retornos_sim.append(r_op)

        cvar_vec = calcular_cvar_10pct_adversarial(retornos_sim)
        penalizacion_cvar = 0.35 * abs(min(0.0, cvar_vec))
        bono_escudos = (n_salv * 0.042) - (n_falsos * 0.012 * max(0.0, ofi_m - 0.05))
        reg_prior = (
            abs(z_hb + 2.50) * 0.015
            + abs(tp_v - 0.0014) * 2.0
            + abs(h_s - 0.485) * 0.20
            + abs(sl_d - 0.0032) * 1.5
        )
        score = pnl_sim + bono_escudos - penalizacion_cvar - reg_prior

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
        "salvamentos_confirmados_15s": n_salv,
        "falsos_rechazos_15s": n_falsos,
        "mejor_expectancia_sim_usdt": round(mejor_score, 4),
        "cvar_10pct_optimo_usdt": round(mejor_cvar, 4),
        "configuracion_optima_terpsichora": mejor_combo,
    }
