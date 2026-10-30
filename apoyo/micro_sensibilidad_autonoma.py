# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #7: Gobernador de Sensibilidad Autonoma en Tiempo Real
con Colas Estratificadas, Deduplicacion Markoviana de Rafagas (dt > 15.0s),
Retroalimentacion OPSR No Censurada (COLT 2026), Gradiente de Impedancia de
Vacio Profundo L2 (V_L2) con Doble Momento Adam, Calibracion de los 8 Atributos
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


def _extraer_vacio_l2_evento(op: Dict[str, Any]) -> float:
    """
    Extrae en O(1) el tensor vacio_l2_ratio (o vacio_l2_entry) de un cierre real,
    operacion en RAM o evento forense de escudo 15s, inspeccionando tambien
    vector_entrada / vector_sombra cuando esta anidado.
    """
    vacio_l2 = float(op.get("vacio_l2_ratio", op.get("vacio_l2_entry", 0.0)) or 0.0)
    if vacio_l2 <= 0.0:
        vec = (
            op.get("vector_entrada")
            if isinstance(op.get("vector_entrada"), dict)
            else (
                op.get("vector_sombra")
                if isinstance(op.get("vector_sombra"), dict)
                else {}
            )
        )
        vacio_l2 = float(vec.get("vacio_l2_ratio", vec.get("vacio_l2_entry", 1.0)) or 1.0)
    return max(0.12, min(3.00, vacio_l2))


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
    losses_pond = 0.0
    for op in ultimas:
        if float(op.get("pnl_usdt", 0.0)) <= 0.0:
            es_sc = bool(op.get("es_scratch")) or ("SCRATCH" in str(op.get("motivo_salida", "")).upper())
            if es_sc:
                losses_pond += min(
                    0.85,
                    max(
                        0.15,
                        abs(float(op.get("pnl_pct", 0.0)) / 100.0)
                        / max(0.0010, float(cfg.SL_INTERNO_PCT)),
                    ),
                )
            else:
                losses_pond += 1.0
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
    w_obs = (wins / (wins + losses_pond)) if (wins + losses_pond) > 0 else 0.60

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

    return calcular_pesos_elasticos_antifalso_scratch(
        memoria_pares_base={
            "trades": float(n),
            "lambda_cred": round(lam, 4),
            "edge_post": round(e_post, 3),
            "wr_post": round(w_post, 3),
            "mfe_post_pct": round(mfe_mean, 4),
            "alpha_disloc": alpha_disloc,
            "w_kelly": w_kelly,
        }
    )


def auto_calibrar_sensibilidades_en_vivo(
    estado_ram: Any,
    ejecutor: Any = None,
    gestor_estadisticas: Any = None,
) -> Dict[str, float]:
    ctrl = getattr(estado_ram, "controlador_autonomo", None)
    if not isinstance(ctrl, dict):
        return {}

    if gestor_estadisticas is None and ejecutor is not None and hasattr(ejecutor, "operaciones"):
        gestor_eff = ejecutor
    elif gestor_estadisticas is not None:
        gestor_eff = gestor_estadisticas
    else:
        gestor_eff = st.GESTOR_ESTADISTICAS

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
    ops_gestor = list(getattr(gestor_eff, "operaciones", []) or [])
    ops_combinadas: List[Dict[str, Any]] = []
    vistos_ids = set()
    for op in cierres_reales + ops_gestor:
        if not isinstance(op, dict):
            continue
        tid = str(op.get("trade_id", "") or "")
        clave_op = tid if tid else f"{op.get('symbol', '')}|{round(float(op.get('timestamp', 0.0) or 0.0), 1)}"
        if clave_op not in vistos_ids:
            vistos_ids.add(clave_op)
            ops_combinadas.append(op)

    ops_hist = ops_combinadas if ops_combinadas else ops_gestor
    por_simbolo: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    v2_wins_global: List[float] = []
    v2_bad_global: List[float] = []
    v2_scratches_recientes: List[float] = []

    for op in ops_hist:
        s_op = str(op.get("symbol", ""))
        if s_op:
            por_simbolo[s_op].append(op)

    for op in ops_hist[-36:]:
        vacio_l2 = float(op.get("vacio_l2_ratio", op.get("vacio_l2_entry", _extraer_vacio_l2_evento(op))) or 1.0)
        pnl_op = float(op.get("pnl_usdt", 0.0) or 0.0)
        mot_op = str(op.get("motivo_salida", "")).upper()
        es_sc = bool(op.get("es_scratch")) or ("SCRATCH" in mot_op)
        if es_sc:
            v2_scratches_recientes.append(vacio_l2)
            v2_bad_global.append(vacio_l2)
        elif pnl_op > 0.0:
            v2_wins_global.append(vacio_l2)
        else:
            v2_bad_global.append(vacio_l2)

    v_l2_win_global = (sum(v2_wins_global) / len(v2_wins_global)) if v2_wins_global else 1.0
    v_l2_bad_global = (sum(v2_bad_global) / len(v2_bad_global)) if v2_bad_global else 1.0
    ratio_low_v2_global = (
        (sum(1 for v in v2_bad_global if v < 0.60) / float(len(v2_bad_global)))
        if v2_bad_global
        else 0.0
    )

    esc_por_simbolo: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for ev in escudos_dedup:
        s_ev = str(ev.get("symbol", ""))
        if s_ev:
            esc_por_simbolo[s_ev].append(ev)

    alpha_elastico_por_par: Dict[str, float] = {}
    sesgo_escudo_por_par: Dict[str, float] = {}
    adam_estado: Dict[str, float] = {}

    for sym in cfg.PARES_CAMPEONES:
        ops_sym = por_simbolo.get(sym, [])
        perf = calcular_perfil_bayesiano_par(ops_sym, ahora_ts)
        ctrl[f"w_kelly_{sym}"] = perf["w_kelly"]
        ctrl[f"edge_post_{sym}"] = perf["edge_post"]

        rec_sym = ops_sym[-16:]
        wins_sym_v2: List[float] = []
        bad_sym_v2: List[float] = []
        for op in rec_sym:
            vacio_l2 = float(op.get("vacio_l2_ratio", op.get("vacio_l2_entry", _extraer_vacio_l2_evento(op))) or 1.0)
            pnl_s = float(op.get("pnl_usdt", 0.0) or 0.0)
            es_sc_s = bool(op.get("es_scratch")) or ("SCRATCH" in str(op.get("motivo_salida", "")).upper())
            if pnl_s > 0.0 and not es_sc_s:
                wins_sym_v2.append(vacio_l2)
            else:
                bad_sym_v2.append(vacio_l2)

        v_l2_win_avg = (sum(wins_sym_v2) / len(wins_sym_v2)) if wins_sym_v2 else v_l2_win_global
        v_l2_bad_avg = (sum(bad_sym_v2) / len(bad_sym_v2)) if bad_sym_v2 else v_l2_bad_global
        ratio_low_v2 = (
            (sum(1 for v in bad_sym_v2 if v < 0.60) / float(len(bad_sym_v2)))
            if bad_sym_v2
            else ratio_low_v2_global
        )
        n_rec_sym = len(rec_sym)
        ratio_bad_sym = (
            (len(bad_sym_v2) / float(n_rec_sym)) * (0.50 + 0.50 * ratio_low_v2)
            if n_rec_sym > 0
            else 0.0
        )

        esc_sym = esc_por_simbolo.get(sym, [])[-30:]
        missed_sym_v2 = [
            float(ev.get("vacio_l2_ratio", ev.get("vacio_l2_entry", _extraer_vacio_l2_evento(ev))) or 1.0)
            for ev in esc_sym
            if ev.get("veredicto_oraculo_15s") == "FALSE_REJECTION_OPPORTUNITY_LOST"
        ]
        v_l2_missed_avg = (sum(missed_sym_v2) / len(missed_sym_v2)) if missed_sym_v2 else 1.0
        ratio_missed_sym = (len(missed_sym_v2) / float(len(esc_sym))) if esc_sym else 0.0

        grad_v_l2 = (
            ratio_bad_sym * (max(0.0, v_l2_win_avg - v_l2_bad_avg) + max(0.0, 0.72 - v_l2_bad_avg))
            - 0.35 * ratio_missed_sym * max(0.0, v_l2_missed_avg - 1.10)
        )

        beta1, beta2, eps_adam = 0.80, 0.92, 1e-6
        m_prev = float(ctrl.get(f"_adam_m_{sym}", 0.0) or 0.0)
        v_prev = float(ctrl.get(f"_adam_v_{sym}", 0.0) or 0.0)
        t_step = int(ctrl.get(f"_adam_t_{sym}", 0) or 0) + 1
        m_curr = (beta1 * m_prev) + ((1.0 - beta1) * grad_v_l2)
        v_curr = (beta2 * v_prev) + ((1.0 - beta2) * (grad_v_l2 * grad_v_l2))
        m_hat = m_curr / (1.0 - (beta1 ** t_step))
        v_hat = v_curr / (1.0 - (beta2 ** t_step))
        paso_adam = (m_hat / (math.sqrt(max(0.0, v_hat)) + eps_adam)) if abs(grad_v_l2) > 1e-7 else 0.0

        adam_estado[f"_adam_m_{sym}"] = round(m_curr, 6)
        adam_estado[f"_adam_v_{sym}"] = round(v_curr, 6)
        adam_estado[f"_adam_t_{sym}"] = float(min(1000, t_step))

        alpha_base_sym = min(1.40, float(perf["alpha_disloc"]))
        alpha_prev_sym = float(ctrl.get(f"alpha_disloc_{sym}", alpha_base_sym) or alpha_base_sym)
        if abs(grad_v_l2) > 1e-7:
            alpha_nuevo = (0.60 * alpha_base_sym) + (0.40 * alpha_prev_sym) + (0.045 * paso_adam)
        else:
            alpha_nuevo = alpha_base_sym
        alpha_clamped = round(max(0.88, min(1.40, alpha_nuevo)), 4)
        ctrl[f"alpha_disloc_{sym}"] = alpha_clamped
        alpha_elastico_por_par[f"alpha_disloc_{sym}"] = alpha_clamped

        sesgo_prev_sym = float(ctrl.get(f"sesgo_escudo_{sym}", 0.0) or 0.0)
        sesgo_nuevo = (0.82 * sesgo_prev_sym) + (0.025 * paso_adam)
        sesgo_clamped = round(max(-0.08, min(0.10, sesgo_nuevo)), 4)
        ctrl[f"sesgo_escudo_{sym}"] = sesgo_clamped
        sesgo_escudo_por_par[f"sesgo_escudo_{sym}"] = sesgo_clamped

    w1_base = float(ctrl.get("w1_ofi_long", cfg.OFI_MIN_ENTRADA) or cfg.OFI_MIN_ENTRADA)
    scratches_rec = v2_scratches_recientes[-12:]
    v_l2_scratch_avg = (sum(scratches_rec) / len(scratches_rec)) if scratches_rec else v_l2_bad_global
    if len(scratches_rec) >= 2 and v_l2_scratch_avg < 0.55:
        inc_w1 = max(0.0, 0.60 - v_l2_bad_global) * 0.04
        ctrl["w1_ofi_long"] = round(max(0.055, min(0.140, w1_base + inc_w1)), 4)
    else:
        ctrl["w1_ofi_long"] = round(max(0.055, min(0.140, w1_base)), 4)

    hurst_saves = sum(
        1 for e in escudos_dedup[-40:]
        if str(e.get("escudo", "")) in ("HURST_FILTER", "P-02_HURST_SHORT")
        and e.get("veredicto_oraculo_15s") == "CAPITAL_SAVED_TRUE_SHIELD"
    )
    ctrl["sens_climax_hurst_override"] = 0.0 if hurst_saves >= 1 else 0.0

    pesos_antifalso = calcular_pesos_elasticos_antifalso_scratch(ops_hist[-40:], post_cierres[-40:])
    if not cfg.es_modo_test() and ops_hist:
        ctrl["sens_scratch_edad_rebote_seg"] = round(
            max(
                float(ctrl.get("sens_scratch_edad_rebote_seg", 28.0)),
                float(pesos_antifalso.get("tau_scratch_seg", 34.0)),
            ),
            2,
        )
        ctrl["sens_q_ratio_floor"] = round(
            max(
                float(ctrl.get("sens_q_ratio_floor", 0.22)),
                float(pesos_antifalso.get("q_hold_abort", 0.24)),
            ),
            4,
        )
        disloc_af_map = pesos_antifalso.get("pair_disloc_mult", {})
        kelly_af_map = pesos_antifalso.get("pair_kelly_mult", {})
        for sym_af in cfg.PARES_CAMPEONES:
            if sym_af in disloc_af_map:
                d_merged = round(min(1.40, max(float(alpha_elastico_por_par.get(f"alpha_disloc_{sym_af}", 1.0)), float(disloc_af_map[sym_af]))), 4)
                alpha_elastico_por_par[f"alpha_disloc_{sym_af}"] = d_merged
                ctrl[f"alpha_disloc_{sym_af}"] = d_merged
            if sym_af in kelly_af_map:
                k_merged = round(max(0.72, min(float(ctrl.get(f"w_kelly_{sym_af}", 1.0)), float(kelly_af_map[sym_af]))), 4)
                ctrl[f"w_kelly_{sym_af}"] = k_merged

    ctrl["diag_v_l2_bad_avg"] = round(v_l2_bad_global, 4)
    ctrl["diag_v_l2_win_avg"] = round(v_l2_win_global, 4)
    ctrl_sanitizado = cfg.sanitizar_controlador_autonomo(ctrl)
    ctrl.update(ctrl_sanitizado)
    ctrl.update(alpha_elastico_por_par)
    ctrl.update(sesgo_escudo_por_par)
    ctrl.update(adam_estado)
    ctrl["diag_v_l2_bad_avg"] = round(v_l2_bad_global, 4)
    ctrl["diag_v_l2_win_avg"] = round(v_l2_win_global, 4)
    return dict(ctrl)


def calcular_pesos_elasticos_antifalso_scratch(
    registros_cierres: list = None,
    registros_markout: list = None,
    memoria_pares_base: dict = None,
) -> dict:
    """Calcula y aplica en vivo TauScratch, KappaWald, Q_HoldAbort y la penalizacion Fee-Cover/Edge por par."""
    import math
    if registros_cierres is None:
        try:
            import stats_tracker as _st
            if not _st.GESTOR_ESTADISTICAS.operaciones:
                _st.GESTOR_ESTADISTICAS.cargar_historial_disco()
            registros_cierres = list(_st.GESTOR_ESTADISTICAS.operaciones)
        except Exception:
            registros_cierres = []

    if not registros_cierres:
        base_res = {
            "tau_scratch_seg": 32.0,
            "zero_giveaway_seg": 64.0,
            "kappa_wald_base": 0.45,
            "q_hold_abort": 0.25,
            "pair_disloc_mult": {},
            "pair_kelly_mult": {},
        }
        return memoria_pares_base if isinstance(memoria_pares_base, dict) else base_res

    scratches = [
        r for r in registros_cierres
        if bool(r.get("es_scratch")) or "SCRATCH" in str(r.get("motivo_salida", r.get("exit_reason", ""))).upper()
    ]
    unwinds = [
        r for r in registros_cierres
        if str(r.get("motivo_salida", r.get("exit_reason", ""))).upper() in ("MAKER_UNWIND", "TRINQUETE_BE_MAKER")
    ]
    eta_vals = []
    for r in unwinds:
        vec = r.get("vector_entrada") if isinstance(r.get("vector_entrada"), dict) else {}
        eta_v = vec.get("mfe_capture_ratio", r.get("eta_mfe"))
        if eta_v is not None:
            eta_vals.append(float(eta_v))
    eta_mean = sum(eta_vals) / len(eta_vals) if eta_vals else 0.45

    rebounds = 0
    saved_dumps = 0
    if registros_markout:
        for m in registros_markout:
            verdict = str(m.get("veredicto_post_cierre", m.get("veredicto_markout", ""))).upper()
            if "EARLY_REBOUND" in verdict or "RUNNER_CONTINUED" in verdict:
                rebounds += 1
            elif "SAVED" in verdict or "OPTIMAL" in verdict:
                saved_dumps += 1
    rho_rebound = (rebounds + 1.0) / (rebounds + saved_dumps + 2.0)
    scratch_loss_rate = sum(1 for s in scratches if float(s.get("pnl_usdt", 0.0)) < 0.0) / max(1, len(scratches))
    tau_scratch = min(48.0, max(24.0, 28.0 * (1.0 + 0.40 * rho_rebound + 0.25 * scratch_loss_rate)))
    kappa_wald = min(0.75, max(0.35, 0.40 + 0.25 * max(0.0, 0.65 - eta_mean)))

    por_par = {}
    for r in registros_cierres:
        sym = str(r.get("symbol", ""))
        if not sym:
            continue
        por_par.setdefault(sym, {"mfe": [], "mae": [], "lvr": [], "pnl": []})
        if "mfe_max_pnl_pct" in r:
            mfe_dec = max(0.00005, abs(float(r.get("mfe_max_pnl_pct", 0.08) or 0.08)) / 100.0)
        else:
            mfe_raw = abs(float(r.get("mfe_pct", 0.0008) or 0.0008))
            mfe_dec = mfe_raw / 100.0 if mfe_raw > 0.02 else mfe_raw
        if "mae_min_pnl_pct" in r:
            mae_dec = max(0.00005, abs(float(r.get("mae_min_pnl_pct", 0.08) or 0.08)) / 100.0)
        else:
            mae_raw = abs(float(r.get("mae_pct", 0.0008) or 0.0008))
            mae_dec = mae_raw / 100.0 if mae_raw > 0.02 else mae_raw
        por_par[sym]["mfe"].append(mfe_dec)
        por_par[sym]["mae"].append(mae_dec)
        por_par[sym]["lvr"].append(abs(float(r.get("lvr_bps", r.get("lvr", 0.002)) or 0.002)))
        por_par[sym]["pnl"].append(float(r.get("pnl_usdt", 0.0) or 0.0))

    pair_disloc = {}
    pair_kelly = {}
    for sym, d in por_par.items():
        avg_mfe = sum(d["mfe"]) / len(d["mfe"])
        avg_mae = max(0.0004, sum(d["mae"]) / len(d["mae"]))
        avg_lvr = sum(d["lvr"]) / len(d["lvr"])
        net_pnl_sym = sum(d["pnl"])
        edge_p = avg_mfe / avg_mae
        fee_cover = avg_mfe / 0.0012
        penal_pnl = max(0.0, -net_pnl_sym * 0.12)
        disloc_m = min(
            1.48,
            max(0.94, 1.0 + 0.35 * max(0.0, 1.15 - edge_p) + 0.30 * max(0.0, 1.0 - fee_cover) + 18.0 * avg_lvr + penal_pnl),
        )
        kelly_m = min(1.10, max(0.60, math.tanh(edge_p) * min(1.08, max(0.62, fee_cover)) - min(0.22, penal_pnl * 0.6)))
        pair_disloc[sym] = round(disloc_m, 3)
        pair_kelly[sym] = round(kelly_m, 3)

    if isinstance(memoria_pares_base, dict):
        import config_parametros as _cfg_sa
        if not _cfg_sa.es_modo_test():
            for sym_k, val_v in list(memoria_pares_base.items()):
                if sym_k in pair_disloc and isinstance(val_v, dict):
                    for k_sub in list(val_v.keys()):
                        kl = k_sub.lower()
                        if "disloc" in kl:
                            val_v[k_sub] = round(max(float(val_v[k_sub]), pair_disloc[sym_k]), 4)
                        elif "kelly" in kl:
                            val_v[k_sub] = round(min(float(val_v[k_sub]), pair_kelly[sym_k]), 4)
        return memoria_pares_base

    return {
        "tau_scratch_seg": round(tau_scratch, 2),
        "zero_giveaway_seg": 64.0,
        "kappa_wald_base": round(kappa_wald, 3),
        "q_hold_abort": round(min(0.38, max(0.20, 0.20 + 0.12 * scratch_loss_rate)), 3),
        "pair_disloc_mult": pair_disloc,
        "pair_kelly_mult": pair_kelly,
    }
