# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #7: Puppeteer Phase-Latched Envelope (4.50s) para Captura
de Suelos en V (LONG), Agotamiento/Rollover de Techos (SHORT-SNIPER), Disparo en
Vertice y Modulacion Elastica de Profundidad por Edge Bayesiano y Percentil 24h
para HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
from typing import Any, Tuple
import config_parametros as cfg
import core_estado_ram as ram
from apoyo import micro_cinematica_l2 as mcl


def _obtener_multiplicador_dislocacion_par(metrica: Any) -> float:
    if cfg.es_modo_test():
        return 1.0
    sym = str(getattr(metrica, "symbol", "") or "")
    if not sym:
        return 1.0
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    alpha = float(ctrl.get(f"alpha_disloc_{sym}", 1.0) or 1.0)
    alpha_safe = max(1.0, min(1.40, alpha))
    p_24h = float(getattr(metrica, "percentil_24h", 0.50) or 0.50)
    es_hb = cfg.obtener_clase_activo(sym) == cfg.CLASE_HIGH_BETA
    mult_elastico = mcl.calcular_multiplicador_elastico_par(
        p_24h, alpha_disloc_par=alpha_safe, es_high_beta=es_hb
    )
    if hasattr(metrica, "multiplicador_elastico"):
        metrica.multiplicador_elastico = mult_elastico
    return max(1.00 if es_hb else 0.94, min(1.45, mult_elastico))


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

    z_umbral_long = min(z_base, z_base * alpha_par) if es_hb else (z_base * alpha_par)
    dp_min_long = min(dp_base, dp_base * alpha_par) if es_hb else (dp_base * alpha_par)
    recorrido_req = rec_base * alpha_par
    piso_anti_ruido = piso_base * alpha_par

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
            or (z_score <= (-2.70 * alpha_par) and dp_pct <= (-0.0019 * alpha_par))
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
    ema_min_short = ema_base * alpha_par
    dp_min_short = dp_base * alpha_par
    z_short_req = cfg.Z_SCORE_SHORT_UMBRAL * alpha_par

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
        and dp_pct >= -0.0005
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
) -> bool:
    if hurst > 0.485 or not latched_activo:
        return False
    delta_ofi = float(ofi_actual) - float(ofi_previo)
    side_u = str(side).upper()
    if side_u in ("LONG", "BUY"):
        freno_ok = acel_lyapunov >= -0.00022
        giro_ofi_ok = (ofi_actual >= ofi_min_umbral) or (
            z_score <= -2.80 and ofi_actual >= 0.04 and delta_ofi >= 0.14
        )
        return bool(freno_ok and giro_ofi_ok)
    else:
        freno_ok = acel_lyapunov <= 0.00022
        giro_ofi_ok = (ofi_actual <= -max(0.18, ofi_min_umbral)) or (
            z_score >= 2.80 and ofi_actual <= -0.10 and delta_ofi <= -0.14
        )
        return bool(freno_ok and giro_ofi_ok)