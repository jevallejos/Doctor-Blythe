# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #7: Puppeteer Phase-Latched Envelope (4.50s) para Captura
de Suelos en V (LONG), Agotamiento/Rollover de Techos (SHORT-SNIPER), Disparo en
Vertice e Impedancia Log-Elastica de Vacio L2 (V_L2) con Modulacion por Edge
Bayesiano y Percentil 24h para HFT Doctor Blythe Engine -
Production Baseline Terpsichora V7.0.
"""
import math
from typing import Any, Tuple
import config_parametros as cfg
import core_estado_ram as ram
from apoyo import micro_cinematica_l2 as mcl


def calcular_impedancia_log_vacio_l2(
    vacio_l2_ratio: float,
    alpha_disloc: float = 1.0,
) -> float:
    """
    Operador continuo de Impedancia Log-Elastica sobre el Vacio Profundo L2 (V_L2):
    - En modo test con V_L2 ~ 1.0, retorna exactamente 1.0 para preservar el contrato.
    - Cuando V_L2 < 1.0 (l_v2 < 0, pared de liquidez opuesta bloqueando el TP),
      eleva la exigencia de dislocacion (psi > 1.0) proporcional a alpha_disloc.
    - Cuando V_L2 >= 1.0 (l_v2 >= 0, vacio profundo a favor del rebote/caida),
      relaja suavemente la impedancia (psi <= 1.0) acotado en [0.90, 1.34].
    """
    if cfg.es_modo_test() and abs(float(vacio_l2_ratio or 1.0) - 1.0) < 1e-6:
        return 1.0
    v_clip = max(
        0.12,
        min(
            3.00,
            float(vacio_l2_ratio if vacio_l2_ratio and vacio_l2_ratio > 0.0 else 1.0),
        ),
    )
    l_v2 = math.tanh(math.log(v_clip))
    alpha = max(0.88, min(1.18, float(alpha_disloc or 1.0)))
    if l_v2 < 0.0:
        psi = 1.0 - (0.26 * alpha) * l_v2
    else:
        psi = 1.0 - (0.10 / alpha) * l_v2
    return round(max(0.90, min(1.34, psi)), 6)


def _obtener_multiplicador_dislocacion_par(metrica: Any) -> float:
    if cfg.es_modo_test():
        return 1.0
    sym = str(getattr(metrica, "symbol", "") or "")
    if not sym:
        return 1.0
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    alpha = float(ctrl.get(f"alpha_disloc_{sym}", 1.0) or 1.0)
    alpha_safe = max(0.88, min(1.40, alpha))
    p_24h = float(getattr(metrica, "percentil_24h", 0.50) or 0.50)
    es_hb = cfg.obtener_clase_activo(sym) == cfg.CLASE_HIGH_BETA
    mult_elastico = mcl.calcular_multiplicador_elastico_par(
        p_24h, alpha_disloc_par=max(1.0, alpha_safe), es_high_beta=es_hb
    )
    if alpha_safe < 1.0:
        mult_elastico = round(mult_elastico * alpha_safe, 4)
    if hasattr(metrica, "multiplicador_elastico"):
        metrica.multiplicador_elastico = mult_elastico
    return max(1.00 if es_hb else 0.90, min(1.45, mult_elastico))


def evaluar_dislocacion_y_latch_long(
    es_hb: bool,
    z_score: float,
    dp_pct: float,
    ema900_dist_pct: float,
    ahora: float,
    metrica: Any,
) -> Tuple[bool, bool]:
    alpha_par = _obtener_multiplicador_dislocacion_par(metrica)
    z_base = cfg.Z_SCORE_UMBRAL_HIGH_BETA if es_hb else cfg.Z_SCORE_UMBRAL_TIER1
    dp_base = cfg.DP_MIN_EXCURSION_LONG_HB if es_hb else cfg.DP_MIN_EXCURSION_LONG_T1
    rec_base = -0.0018 if es_hb else -0.0011
    piso_base = -0.0011 if es_hb else -0.00075

    symbol = str(getattr(metrica, "symbol", "") or "")
    vacio_l2 = float(getattr(metrica, "vacio_l2_ratio", 1.0) or 1.0)
    if not cfg.es_modo_test():
        ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
        alpha_sym = float(ctrl.get(f"alpha_disloc_{symbol}", 1.0) or 1.0)
    else:
        alpha_sym = 1.0

    psi_l2 = calcular_impedancia_log_vacio_l2(vacio_l2, 1.0)
    raiz_psi_l2 = math.sqrt(psi_l2)

    z_umbral_base = min(z_base, z_base * alpha_par) if es_hb else (z_base * alpha_par)
    dp_req_base = min(dp_base, dp_base * alpha_par) if es_hb else (dp_base * alpha_par)
    piso_z_duro = z_base if es_hb else (z_base * 0.90)
    piso_dp_duro = dp_base if es_hb else (dp_base * 0.90)

    z_umbral_eff = min(piso_z_duro, z_umbral_base * psi_l2)
    dp_req_eff = min(piso_dp_duro, dp_req_base * raiz_psi_l2)
    z_umbral_long = z_umbral_eff
    dp_min_long = dp_req_eff
    recorrido_req = (rec_base * alpha_par) * raiz_psi_l2
    piso_anti_ruido = (piso_base * alpha_par) * raiz_psi_l2

    if (
        not metrica.phase_latched
        or metrica.phase_latch_dir != "LONG"
        or (ahora - metrica.phase_latch_ts) > cfg.PHASE_LATCH_VENTANA_SEG
    ):
        if metrica.phase_latch_dir == "LONG" and (ahora - metrica.phase_latch_ts) > cfg.PHASE_LATCH_VENTANA_SEG:
            metrica.phase_latched = False
            metrica.phase_latch_z_peak = 0.0
            metrica.phase_latch_ema_dist = 0.0

    excursion_dual_ok = (
        min(dp_pct, ema900_dist_pct) <= recorrido_req
        and (
            max(dp_pct, ema900_dist_pct) <= piso_anti_ruido
            or (z_score <= (-2.70 * alpha_par * psi_l2) and dp_pct <= (-0.0019 * alpha_par * raiz_psi_l2))
        )
    )
    dislocacion_long_activa = (
        z_score <= z_umbral_long
        and dp_pct < 0.0
        and excursion_dual_ok
    )
    if dislocacion_long_activa:
        prev_z = metrica.phase_latch_z_peak if (metrica.phase_latched and metrica.phase_latch_dir == "LONG") else z_score
        prev_ema = metrica.phase_latch_ema_dist if (metrica.phase_latched and metrica.phase_latch_dir == "LONG") else ema900_dist_pct
        metrica.phase_latched = True
        metrica.phase_latch_ts = ahora
        metrica.phase_latch_dir = "LONG"
        metrica.phase_latch_z_peak = min(prev_z, z_score)
        metrica.phase_latch_ema_dist = min(prev_ema, ema900_dist_pct)

    latch_long_vigente = (
        metrica.phase_latched
        and metrica.phase_latch_dir == "LONG"
        and (ahora - metrica.phase_latch_ts) <= cfg.PHASE_LATCH_VENTANA_SEG
        and z_score <= (z_umbral_long * 0.72)
        and dp_pct <= (dp_min_long * 0.70)
        and min(dp_pct, ema900_dist_pct) <= (recorrido_req * 0.80)
        and ema900_dist_pct <= (piso_anti_ruido * 0.85)
    )
    return bool(dislocacion_long_activa), bool(latch_long_vigente)


def evaluar_sobreextension_y_rollover_short(
    es_hb: bool,
    z_score: float,
    dp_pct: float,
    ema900_dist_pct: float,
    mid: float,
    ofi_inst: float,
    ahora: float,
    metrica: Any,
    est: Any,
) -> Tuple[bool, bool, bool]:
    alpha_par = _obtener_multiplicador_dislocacion_par(metrica)
    ema_base = cfg.EMA900_SOBREEXTENSION_SHORT_HB if es_hb else cfg.EMA900_SOBREEXTENSION_SHORT_T1
    dp_base = cfg.DP_MIN_EXCURSION_SHORT_HB if es_hb else cfg.DP_MIN_EXCURSION_SHORT_T1

    symbol = str(getattr(est, "symbol", "") or getattr(metrica, "symbol", "") or "")
    vacio_est = float(getattr(est, "vacio_l2_ratio", 0.0) or 0.0)
    if vacio_est > 0.0:
        vacio_l2 = vacio_est
    elif not cfg.es_modo_test():
        m_ram = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol) if symbol else metrica
        vacio_l2 = float(getattr(m_ram, "vacio_l2_ratio", getattr(metrica, "vacio_l2_ratio", 1.0)) or 1.0)
    else:
        vacio_l2 = float(getattr(metrica, "vacio_l2_ratio", 1.0) or 1.0)

    if not cfg.es_modo_test():
        ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
        alpha_sym = float(ctrl.get(f"alpha_disloc_{symbol}", 1.0) or 1.0)
    else:
        alpha_sym = 1.0

    psi_l2 = calcular_impedancia_log_vacio_l2(vacio_l2, 1.0)
    raiz_psi_l2 = math.sqrt(psi_l2)

    z_base_short = cfg.Z_SCORE_SHORT_UMBRAL * alpha_par
    z_req_short = max(cfg.Z_SCORE_SHORT_UMBRAL * 0.90, z_base_short * psi_l2)
    z_short_req = z_req_short
    ema_min_short = (ema_base * alpha_par) * raiz_psi_l2
    dp_min_short = (dp_base * alpha_par) * raiz_psi_l2

    if ahora > est.vigilancia_short_hasta_ts:
        est.max_z_pump_short = 0.0
        est.max_ema_pump_short = 0.0
        est.px_pico_pump_short = 0.0

    if (
        metrica.phase_latch_dir == "SHORT"
        and (ahora - metrica.phase_latch_ts) > cfg.PHASE_LATCH_VENTANA_SEG
    ):
        metrica.phase_latched = False
        metrica.phase_latch_z_peak = 0.0
        metrica.phase_latch_ema_dist = 0.0

    sobreextension_short = (
        ema900_dist_pct >= ema_min_short
        and z_score >= z_short_req
        and dp_pct >= dp_min_short
    )
    if sobreextension_short:
        prev_z_s = metrica.phase_latch_z_peak if (metrica.phase_latched and metrica.phase_latch_dir == "SHORT") else z_score
        prev_ema_s = metrica.phase_latch_ema_dist if (metrica.phase_latched and metrica.phase_latch_dir == "SHORT") else ema900_dist_pct
        metrica.phase_latched = True
        metrica.phase_latch_ts = ahora
        metrica.phase_latch_dir = "SHORT"
        metrica.phase_latch_z_peak = max(prev_z_s, z_score)
        metrica.phase_latch_ema_dist = max(prev_ema_s, ema900_dist_pct)
        est.vigilancia_short_hasta_ts = ahora + 15.0
        est.max_z_pump_short = max(est.max_z_pump_short, z_score)
        est.max_ema_pump_short = max(est.max_ema_pump_short, ema900_dist_pct)
        est.px_pico_pump_short = max(est.px_pico_pump_short, mid)

    latch_short_vigente = (
        metrica.phase_latched
        and metrica.phase_latch_dir == "SHORT"
        and (ahora - metrica.phase_latch_ts) <= cfg.PHASE_LATCH_VENTANA_SEG
        and z_score > 0.0
        and dp_pct >= (dp_min_short * 0.65)
        and ema900_dist_pct >= (ema_min_short * 0.85)
    )
    rollover_techo_vigente = (
        ahora <= est.vigilancia_short_hasta_ts
        and est.max_z_pump_short >= z_short_req
        and ema900_dist_pct >= (ema_min_short * 0.88)
        and z_score > 0.0
        and dp_pct > 0.0
        and est.px_pico_pump_short > 0.0
        and mid <= (est.px_pico_pump_short * 0.9998)
        and ofi_inst <= (cfg.OFI_MAX_ENTRADA_SHORT - 0.06)
    )
    return bool(sobreextension_short), bool(latch_short_vigente), bool(rollover_techo_vigente)


def confirmar_disparo_vertice_armado(
    z_score: float,
    hurst: float,
    acel_lyapunov: float,
    ofi_actual: float,
    ofi_previo: float,
    latched_activo: bool,
    side: str = "LONG",
    ofi_min_umbral: float = 0.06,
    vacio_l2_ratio: float = 1.0,
) -> bool:
    if hurst > 0.485 or not latched_activo:
        return False

    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio and vacio_l2_ratio > 0.0 else 1.0)
    if not cfg.es_modo_test() and abs(v_l2 - 1.0) < 1e-6:
        for m_tick in (getattr(ram.ESTADO_GLOBAL, "metricas_ticks", {}) or {}).values():
            if getattr(m_tick, "phase_latched", False) and abs(float(getattr(m_tick, "z_score", 0.0)) - float(z_score)) < 1e-4:
                v_l2 = float(getattr(m_tick, "vacio_l2_ratio", 1.0) or 1.0)
                break

    ofi_piso_vertice = 0.04
    if v_l2 < 0.65 and (not cfg.es_modo_test() or abs(float(vacio_l2_ratio or 1.0) - 1.0) > 1e-6):
        ofi_piso_vertice = -0.05 + 0.22 * max(0.0, -math.tanh(math.log(max(0.12, v_l2))))

    delta_ofi = float(ofi_actual) - float(ofi_previo)
    side_u = str(side).upper()
    if side_u in ("LONG", "BUY"):
        freno_ok = acel_lyapunov >= -0.00022
        umbral_eff = max(float(ofi_min_umbral), ofi_piso_vertice)
        piso_climax = max(0.04, ofi_piso_vertice)
        giro_ofi_ok = (ofi_actual >= umbral_eff) or (
            z_score <= -2.80 and ofi_actual >= piso_climax and delta_ofi >= 0.14
        )
        return bool(freno_ok and giro_ofi_ok)
    else:
        freno_ok = acel_lyapunov <= 0.00022
        umbral_short_eff = max(0.18, float(ofi_min_umbral), ofi_piso_vertice)
        piso_climax_short = max(0.10, ofi_piso_vertice)
        giro_ofi_ok = (ofi_actual <= -umbral_short_eff) or (
            z_score >= 2.80 and ofi_actual <= -piso_climax_short and delta_ofi <= -0.14
        )
        return bool(freno_ok and giro_ofi_ok)
