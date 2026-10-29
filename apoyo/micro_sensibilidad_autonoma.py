# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #7: Gobernador de Sensibilidad Autonoma en Tiempo Real
con Ley de Control Monotona, Retroalimentacion OPSR (arXiv:2605.19584 COLT 2026),
Auto-Remediacion de ESCAPE_TEMPORAL y Memoria Bayesiana de Edge/Kelly por Par.
"""
import collections
import math
import time
from typing import Any, Dict, List
import config_parametros as cfg
import stats_tracker as st
from apoyo import micro_inspector_forense as mif


def calcular_perfil_bayesiano_par(
    ops_par: List[Dict[str, Any]],
    ahora_ts: float,
    k_prior: float = 5.0,
    tau_olvido_seg: float = 14400.0,
) -> Dict[str, float]:
    """
    Calcula en O(1) sobre la ventana reciente del par (ultimos 12 cierres):
    - Credibilidad Bayesiana de James-Stein con decaimiento exponencial temporal (4h)
      para evitar inanicion perpetua cuando cambia el regimen de mercado.
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

    e_obs = min(2.50, mfe_mean / max(0.020, mae_mean))
    w_obs = (wins / (wins + losses)) if (wins + losses) > 0 else 0.60

    e_post = ((1.0 - lam) * 1.00) + (lam * e_obs)
    w_post = ((1.0 - lam) * 0.60) + (lam * w_obs)
    m_post = ((1.0 - lam) * 0.110) + (lam * mfe_mean)

    score_q = (0.45 * min(1.50, e_post)) + (0.35 * (w_post / 0.60)) + (0.20 * min(1.50, m_post / 0.090))
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

    eventos = mif.cargar_eventos_baul_forense(max_lineas=120)
    post_cierres = [e for e in eventos if e.get("tipo_evento") == "AUDITORIA_POST_CIERRE_60S"]
    cierres_reales = [e for e in eventos if e.get("tipo_evento") == "CIERRE_OPERACION_REAL"]
    opsr_eventos = [
        e for e in eventos
        if e.get("tipo_evento") == "AUDITORIA_ESCUDO_15S"
        and str(e.get("escudo", "")).startswith("OPSR_")
    ]
    opsr_missed_alpha = sum(
        1 for e in opsr_eventos if e.get("veredicto_oraculo_15s") == "FALSE_REJECTION_OPPORTUNITY_LOST"
    )
    opsr_true_saves = sum(
        1 for e in opsr_eventos if e.get("veredicto_oraculo_15s") == "CAPITAL_SAVED_TRUE_SHIELD"
    )

    if opsr_missed_alpha >= (opsr_true_saves + 2):
        ctrl["sens_q_l1_hold_ratio"] = max(0.18, round(float(ctrl["sens_q_l1_hold_ratio"]) - 0.05, 2))
        ctrl["sens_ofi_abort_cola"] = max(-0.46, round(float(ctrl["sens_ofi_abort_cola"]) - 0.04, 2))
    elif opsr_true_saves >= (opsr_missed_alpha + 2):
        ctrl["sens_q_l1_hold_ratio"] = min(0.55, round(float(ctrl["sens_q_l1_hold_ratio"]) + 0.05, 2))
        ctrl["sens_ofi_abort_cola"] = min(-0.26, round(float(ctrl["sens_ofi_abort_cola"]) + 0.04, 2))

    ultimos_cierres = cierres_reales[-10:]
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
        1 for e in post_cierres[-6:]
        if "SCRATCH" in str(e.get("motivo_salida", "")).upper()
        and float(e.get("continuation_60s_pct", 0.0)) >= 0.05
    )

    if escapes_con_mfe_alto >= 1:
        ctrl["w4_unwind_seg"] = max(32.0, round(42.0 - (4.0 * escapes_con_mfe_alto), 1))
        ctrl["mfe_stall_harvest_pct"] = 0.00095
    else:
        ctrl["w4_unwind_seg"] = float(cfg.obtener_aux("EARLY_UNWIND_TIEMPO_SEG", 42.0))
        ctrl["mfe_stall_harvest_pct"] = (
            0.00090 if scratches_con_rebote_posterior >= 1 else float(cfg.COSECHA_ESTANCAMIENTO_MFE_PCT)
        )

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

    ctrl["sens_climax_hurst_override"] = 0.0
    return dict(ctrl)
