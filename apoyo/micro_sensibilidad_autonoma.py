# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #7: Gobernador de Sensibilidad Autonoma en Tiempo Real
con Colas Estratificadas, Deduplicacion Markoviana de Rafagas (dt > 15.0s),
Retroalimentacion OPSR No Censurada (COLT 2026), Calibracion de los 8 Atributos
de Orden Superior y Memoria Bayesiana de Edge/Kelly por Par para
HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
import collections
import math
import time
from typing import Any, Dict, List
import config_parametros as cfg
import stats_tracker as st
from apoyo import micro_inspector_forense as mif


def _deduplicar_episodios_escudo_15s(
    eventos_15s: List[Dict[str, Any]],
    ventana_seg: float = 15.0,
) -> List[Dict[str, Any]]:
    """
    Filtra rafagas de ticks del mismo escudo/par/direccion dentro de una ventana
    Markoviana de 15.0s para que el auto-aprendizaje pondere episodios fisicos
    independientes en lugar de ruido correlacionado (factor 3.49x).
    """
    dedup: List[Dict[str, Any]] = []
    ultimo_ts_clave: Dict[str, float] = {}
    for ev in eventos_15s:
        sym = str(ev.get("symbol", ""))
        esc = str(ev.get("escudo", ""))
        direc = str(ev.get("direccion", ""))
        ts = float(ev.get("timestamp", 0.0) or 0.0)
        clave = f"{sym}|{esc}|{direc}"
        ts_prev = ultimo_ts_clave.get(clave, -1e9)
        if (ts - ts_prev) >= ventana_seg:
            dedup.append(ev)
            ultimo_ts_clave[clave] = ts
    return dedup


def calcular_perfil_bayesiano_par(
    ops_par: List[Dict[str, Any]],
    ahora_ts: float,
    k_prior: float = 5.0,
    tau_olvido_seg: float = 14400.0,
) -> Dict[str, float]:
    """
    Calcula en O(1) sobre la ventana reciente del par (ultimos 12 cierres):
    - Credibilidad Bayesiana de James-Stein con decaimiento exponencial temporal (4h).
    - Pondera MFE/MAE, Win-Rate efectivo, eficiencia regularizada eta_MFE
      (mfe_capture_ratio) y penalizacion por salidas Taker o exceso de re-pegs.
    - Multiplicador Elastico de Profundidad de Dislocacion alpha_disloc in [1.00, 1.40]
      (estrictamente no-regresivo >= 1.00 sobre pisos SCAR-LOCK).
    - Peso Bayesiano de Conviccion Kelly w_kelly in [0.72, 1.12].
    """
    ultimas = ops_par[-12:] if ops_par else []
    n = len(ultimas)
    if n < 2:
        return {
            "trades": float(n),
            "lambda_cred": 0.0,
            "edge_post": 1.00,
            "wr_post": 0.60,
            "mfe_post_pct": 0.110,
            "alpha_disloc": 1.00,
            "w_kelly": 1.00,
        }

    ultimo_ts = float(ultimas[-1].get("timestamp", ahora_ts) or ahora_ts)
    dt_inactivo = max(0.0, ahora_ts - ultimo_ts)
    factor_olvido = math.exp(-dt_inactivo / max(1800.0, tau_olvido_seg))
    lam = (n / (n + k_prior)) * factor_olvido

    mfe_mean = sum(float(op.get("mfe_max_pnl_pct", 0.0)) for op in ultimas) / n
    mae_mean = sum(abs(float(op.get("mae_min_pnl_pct", 0.0))) for op in ultimas) / n
    wins = sum(1 for op in ultimas if float(op.get("pnl_usdt", 0.0)) > 0.0)
    losses = sum(
        1 for op in ultimas
        if float(op.get("pnl_usdt", 0.0)) <= 0.0
        and not (bool(op.get("es_scratch")) or "SCRATCH" in str(op.get("motivo_salida", "")).upper())
    )
    escapes = sum(1 for op in ultimas if "ESCAPE_TEMPORAL" in str(op.get("motivo_salida", "")).upper())
    taker_exits = sum(1 for op in ultimas if not bool(op.get("es_salida_maker", True)))

    cap_vals: List[float] = []
    repeg_vals: List[float] = []
    for op in ultimas:
        vec = op.get("vector_entrada") if isinstance(op.get("vector_entrada"), dict) else {}
        if "mfe_capture_ratio" in vec:
            cap_vals.append(max(-1.50, min(1.50, float(vec.get("mfe_capture_ratio", 0.0) or 0.0))))
        if "repeg_salida_count" in vec:
            repeg_vals.append(float(vec.get("repeg_salida_count", 0.0) or 0.0))

    mean_cap = (sum(cap_vals) / len(cap_vals)) if cap_vals else 0.25
    mean_repeg = (sum(repeg_vals) / len(repeg_vals)) if repeg_vals else 0.0
    taker_ratio = taker_exits / float(n)

    e_obs = min(2.50, mfe_mean / max(0.020, mae_mean))
    w_obs = (wins / (wins + losses)) if (wins + losses) > 0 else 0.60

    e_post = ((1.0 - lam) * 1.00) + (lam * e_obs)
    w_post = ((1.0 - lam) * 0.60) + (lam * w_obs)
    m_post = ((1.0 - lam) * 0.110) + (lam * mfe_mean)

    bono_cap = 0.06 * max(-0.50, min(0.50, mean_cap))
    penal_friccion = (0.08 * max(0.0, taker_ratio - 0.25)) + (0.015 * max(0.0, mean_repeg - 2.0))
    score_q = (
        (0.45 * min(1.50, e_post))
        + (0.35 * (w_post / 0.60))
        + (0.20 * min(1.50, m_post / 0.090))
        + bono_cap
        - penal_friccion
    )
    penal_escape = (0.06 * min(3, escapes)) if score_q < 1.05 else 0.0

    alpha_disloc = round(max(1.00, min(1.40, 1.00 + max(0.0, 0.65 * (1.0 - score_q)) + penal_escape)), 4)
    w_kelly = round(
        max(0.72, min(1.12, (0.55 + (0.45 * score_q)) - (0.03 * min(3, escapes) if score_q < 1.05 else 0.0))),
        4,
    )

    return {
        "trades": float(n),
        "lambda_cred": round(lam, 4),
        "edge_post": round(e_post, 3),
        "wr_post": round(w_post, 3),
        "mfe_post_pct": round(mfe_mean, 4),
        "alpha_disloc": alpha_disloc,
        "w_kelly": w_kelly,
    }


def auto_calibrar_sensibilidades_en_vivo(estado_ram: Any, ejecutor: Any) -> Dict[str, float]:
    ctrl = getattr(estado_ram, "controlador_autonomo", None)
    if not isinstance(ctrl, dict):
        return {}

    intentados = int(getattr(ejecutor, "disparos_intentados", 0) or 0)
    abortados = int(getattr(ejecutor, "disparos_abortados_cola", 0) or 0)

    if intentados >= 4:
        ratio_abort = min(1.0, max(0.0, abortados / float(intentados)))
        hold_base = round(0.46 - (0.24 * ratio_abort), 2)
        ofi_base = round(-0.30 - (0.16 * ratio_abort), 2)
        ctrl["sens_q_l1_hold_ratio"] = max(0.20, min(0.50, hold_base))
        ctrl["sens_ofi_abort_cola"] = max(-0.48, min(-0.28, ofi_base))
    else:
        ctrl["sens_ofi_abort_cola"] = -0.38
        ctrl["sens_q_l1_hold_ratio"] = 0.25

    eventos = mif.cargar_eventos_baul_forense(max_lineas=1800)
    post_cierres = [e for e in eventos if e.get("tipo_evento") == "AUDITORIA_POST_CIERRE_60S"]
    cierres_reales = [e for e in eventos if e.get("tipo_evento") == "CIERRE_OPERACION_REAL"]
    escudos_raw = [e for e in eventos if e.get("tipo_evento") == "AUDITORIA_ESCUDO_15S"]
    escudos_dedup = _deduplicar_episodios_escudo_15s(escudos_raw, ventana_seg=15.0)

    opsr_eventos = [e for e in escudos_dedup if str(e.get("escudo", "")).startswith("OPSR_")]
    opsr_recientes = opsr_eventos[-40:]
    opsr_missed_alpha = sum(
        1 for e in opsr_recientes if e.get("veredicto_oraculo_15s") == "FALSE_REJECTION_OPPORTUNITY_LOST"
    )
    opsr_true_saves = sum(
        1 for e in opsr_recientes if e.get("veredicto_oraculo_15s") == "CAPITAL_SAVED_TRUE_SHIELD"
    )

    if opsr_missed_alpha >= (opsr_true_saves + 2):
        ctrl["sens_q_l1_hold_ratio"] = max(0.18, round(float(ctrl["sens_q_l1_hold_ratio"]) - 0.05, 2))
        ctrl["sens_ofi_abort_cola"] = max(-0.46, round(float(ctrl["sens_ofi_abort_cola"]) - 0.04, 2))
    elif opsr_true_saves >= (opsr_missed_alpha + 2):
        ctrl["sens_q_l1_hold_ratio"] = min(0.55, round(float(ctrl["sens_q_l1_hold_ratio"]) + 0.05, 2))
        ctrl["sens_ofi_abort_cola"] = min(-0.26, round(float(ctrl["sens_ofi_abort_cola"]) + 0.04, 2))

    btc_eventos = [e for e in escudos_dedup if str(e.get("escudo", "")) == "P-01_BTC_VETO"][-45:]
    btc_missed = sum(1 for e in btc_eventos if e.get("veredicto_oraculo_15s") == "FALSE_REJECTION_OPPORTUNITY_LOST")
    btc_saved = sum(1 for e in btc_eventos if e.get("veredicto_oraculo_15s") == "CAPITAL_SAVED_TRUE_SHIELD")
    if len(btc_eventos) >= 4:
        delta_btc = max(-3, min(3, btc_missed - btc_saved))
        ctrl["w2_btc_beta"] = round(max(0.24, min(0.42, float(cfg.BTC_VETO_OFI_UMBRAL) + (0.015 * delta_btc))), 3)

    ultimos_cierres = cierres_reales[-12:]
    escapes_con_mfe_alto = sum(
        1 for c in ultimos_cierres
        if str(c.get("motivo_salida", "")).upper() == "ESCAPE_TEMPORAL"
        and float(c.get("mfe_max_pnl_pct", 0.0)) >= 0.115
    )
    escapes_inercia_muerta = sum(
        1 for c in ultimos_cierres
        if str(c.get("motivo_salida", "")).upper() == "ESCAPE_TEMPORAL"
        and float(c.get("mfe_max_pnl_pct", 0.0)) < 0.080
    )
    scratches_con_rebote_posterior = sum(
        1 for e in post_cierres[-8:]
        if "SCRATCH" in str(e.get("motivo_salida", "")).upper()
        and (
            float(e.get("continuation_60s_pct", 0.0)) >= 0.05
            or float(e.get("mejor_excursion_60s_pct", 0.0)) >= 0.16
        )
    )
    runners_continuados = sum(
        1 for e in post_cierres[-10:]
        if str(e.get("veredicto_post_cierre", "")) == "WALD_RUNNER_CONTINUED"
    )
    crestas_optimas = sum(
        1 for e in post_cierres[-10:]
        if str(e.get("veredicto_post_cierre", "")) == "WALD_CREST_OPTIMAL"
    )

    repeg_altos = 0
    cap_ganadores: List[float] = []
    perdidas_long = 0
    perdidas_short = 0
    for c in ultimos_cierres:
        vec_c = c.get("vector_entrada") if isinstance(c.get("vector_entrada"), dict) else {}
        rep_c = int(vec_c.get("repeg_salida_count", 0) or 0)
        if rep_c >= 4:
            repeg_altos += 1
        pnl_u = float(c.get("pnl_usdt", 0.0) or 0.0)
        if pnl_u > 0.0 and "mfe_capture_ratio" in vec_c:
            cap_ganadores.append(float(vec_c.get("mfe_capture_ratio", 0.65) or 0.65))
        elif pnl_u < -0.015:
            if str(c.get("side", "LONG")).upper() in ("BUY", "LONG"):
                perdidas_long += 1
            else:
                perdidas_short += 1

    if escapes_con_mfe_alto >= 1 or repeg_altos >= 2:
        reduccion_u = (4.0 * escapes_con_mfe_alto) + (2.0 * min(2, repeg_altos))
        ctrl["w4_unwind_seg"] = max(30.0, round(42.0 - reduccion_u, 1))
        ctrl["mfe_stall_harvest_pct"] = 0.00095
    else:
        ctrl["w4_unwind_seg"] = float(cfg.obtener_aux("EARLY_UNWIND_TIEMPO_SEG", 42.0))
        ctrl["mfe_stall_harvest_pct"] = (
            0.00090 if scratches_con_rebote_posterior >= 1 else float(cfg.COSECHA_ESTANCAMIENTO_MFE_PCT)
        )

    avg_cap_win = (sum(cap_ganadores) / len(cap_ganadores)) if cap_ganadores else 0.65
    tp_base = float(cfg.COSECHA_TRIZ_ACTIVACION_PCT)
    if runners_continuados > crestas_optimas and avg_cap_win >= 0.70 and escapes_con_mfe_alto == 0:
        ctrl["w3_tp_maker_pct"] = round(min(0.0018, tp_base + 0.00015), 5)
    elif escapes_con_mfe_alto >= 1 or avg_cap_win < 0.45:
        ctrl["w3_tp_maker_pct"] = round(max(0.00125, tp_base - 0.00010), 5)
    else:
        ctrl["w3_tp_maker_pct"] = round(tp_base, 5)

    ctrl["sesgo_escudo_long"] = round(min(0.04, 0.01 * max(0, perdidas_long - 1)), 4)
    ctrl["sesgo_escudo_short"] = round(min(0.04, 0.01 * max(0, perdidas_short - 1)), 4)

    if escapes_inercia_muerta >= 1 and scratches_con_rebote_posterior == 0:
        ctrl["sens_scratch_edad_rebote_seg"] = 24.0
    elif scratches_con_rebote_posterior >= 1:
        ctrl["sens_scratch_edad_rebote_seg"] = 34.0
    else:
        ctrl["sens_scratch_edad_rebote_seg"] = 30.0

    ahora_ts = time.time()
    ops_hist = list(getattr(st.GESTOR_ESTADISTICAS, "operaciones", []) or [])
    if not ops_hist and cierres_reales:
        ops_hist = cierres_reales
    por_simbolo: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for op in ops_hist:
        s_op = str(op.get("symbol", ""))
        if s_op:
            por_simbolo[s_op].append(op)

    for par in cfg.PARES_CAMPEONES:
        perf = calcular_perfil_bayesiano_par(por_simbolo.get(par, []), ahora_ts)
        ctrl[f"alpha_disloc_{par}"] = perf["alpha_disloc"]
        ctrl[f"w_kelly_{par}"] = perf["w_kelly"]
        ctrl[f"edge_post_{par}"] = perf["edge_post"]

    hurst_saves = sum(
        1 for e in escudos_dedup[-40:]
        if str(e.get("escudo", "")) in ("HURST_FILTER", "P-02_HURST_SHORT")
        and e.get("veredicto_oraculo_15s") == "CAPITAL_SAVED_TRUE_SHIELD"
    )
    ctrl["sens_climax_hurst_override"] = 0.0 if hurst_saves >= 1 else 0.0
    return dict(ctrl)
