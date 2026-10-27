# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #7: Puppeteer Phase-Latched Envelope (4.50s) para Captura
de Suelos en V (LONG) y Agotamiento/Rollover de Techos (SHORT-SNIPER).
"""
from typing import Any, Tuple
import config_parametros as cfg


def evaluar_dislocacion_y_latch_long(
    es_hb: bool,
    z_score: float,
    dp_pct: float,
    ema900_dist_pct: float,
    ahora: float,
    metrica: Any,
) -> Tuple[bool, bool]:
    z_umbral_long = cfg.Z_SCORE_UMBRAL_HIGH_BETA if es_hb else cfg.Z_SCORE_UMBRAL_TIER1
    dp_min_long = cfg.DP_MIN_EXCURSION_LONG_HB if es_hb else cfg.DP_MIN_EXCURSION_LONG_T1
    recorrido_req = -0.0018 if es_hb else -0.0014
    piso_anti_ruido = -0.0011 if es_hb else -0.0009

    excursion_dual_ok = (
        min(dp_pct, ema900_dist_pct) <= recorrido_req
        and (max(dp_pct, ema900_dist_pct) <= piso_anti_ruido or (z_score <= -2.70 and dp_pct <= -0.0019))
    )
    dislocacion_long_activa = (
        z_score <= z_umbral_long
        and dp_pct < 0.0
        and excursion_dual_ok
    )
    if dislocacion_long_activa:
        metrica.phase_latched = True
        metrica.phase_latch_ts = ahora
        metrica.phase_latch_dir = "LONG"
        metrica.phase_latch_z_peak = min(metrica.phase_latch_z_peak or z_score, z_score)
        metrica.phase_latch_ema_dist = min(metrica.phase_latch_ema_dist or ema900_dist_pct, ema900_dist_pct)

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
    ema_min_short = cfg.EMA900_SOBREEXTENSION_SHORT_HB if es_hb else cfg.EMA900_SOBREEXTENSION_SHORT_T1
    dp_min_short = cfg.DP_MIN_EXCURSION_SHORT_HB if es_hb else cfg.DP_MIN_EXCURSION_SHORT_T1

    sobreextension_short = (
        ema900_dist_pct >= ema_min_short
        and z_score >= cfg.Z_SCORE_SHORT_UMBRAL
        and dp_pct >= dp_min_short
    )
    if sobreextension_short:
        metrica.phase_latched = True
        metrica.phase_latch_ts = ahora
        metrica.phase_latch_dir = "SHORT"
        metrica.phase_latch_z_peak = max(metrica.phase_latch_z_peak or z_score, z_score)
        metrica.phase_latch_ema_dist = max(metrica.phase_latch_ema_dist or ema900_dist_pct, ema900_dist_pct)
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
        and est.max_z_pump_short >= cfg.Z_SCORE_SHORT_UMBRAL
        and ema900_dist_pct >= (ema_min_short * 0.88)
        and dp_pct >= -0.0005
        and mid <= (est.px_pico_pump_short * 0.9998)
        and ofi_inst <= (cfg.OFI_MAX_ENTRADA_SHORT - 0.06)
    )
    return bool(sobreextension_short), bool(latch_short_vigente), bool(rollover_techo_vigente)
