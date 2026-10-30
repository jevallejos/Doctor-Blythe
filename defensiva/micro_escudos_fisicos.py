# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #1: Escudos Fisicos de Entrada (Terpsichora V7.0).
Aisla las barreras cinematicas y de microestructura (Lyapunov, Hurst, Absorcion
OFI/Hawkes con Barrera Hiperbolica Anti-Muralla L1 y Veto Anti-Spoofing arXiv:2502.17417,
Sesgo Autonomo No-Regresivo, Entropia LOB arXiv:2610.16151, Coherencia de Signo RF-06
y Conviccion Contra-EMA900).
"""
from __future__ import annotations

from typing import Tuple

import config_parametros as cfg
import core_estado_ram as ram


def evaluar_coherencia_signo_rf06(
    direccion: str,
    z_score: float,
    dp_pct: float,
) -> Tuple[bool, str]:
    if str(direccion).upper() in ("BUY", "LONG"):
        if z_score >= 0.0 or dp_pct >= 0.0:
            return False, f"RF06_LONG_MISMATCH(Z={z_score:+.2f},dp={dp_pct:+.4f})"
    else:
        if z_score <= 0.0 or dp_pct <= 0.0:
            return False, f"RF06_SHORT_MISMATCH(Z={z_score:+.2f},dp={dp_pct:+.4f})"
    return True, "OK"


def evaluar_freno_lyapunov(
    direccion: str,
    aceleracion_lyapunov: float,
    umbral_freno_long: float = -0.00022,
    umbral_agotamiento_short: float = -0.00010,
    irrev_lob: float = 0.0,
    symbol: str = "",
) -> Tuple[bool, str]:
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    irrev = float(irrev_lob or 0.0)
    sesgo_sym = (
        max(-0.04, min(0.08, float(ctrl.get(f"sesgo_escudo_{symbol}", 0.0) or 0.0)))
        if (not cfg.es_modo_test() and symbol)
        else 0.0
    )
    if str(direccion).upper() in ("BUY", "LONG"):
        sesgo_l = 0.0 if cfg.es_modo_test() else max(0.0, float(ctrl.get("sesgo_escudo_long", 0.0) or 0.0) + sesgo_sym)
        penal_irrev = 0.00004 * max(0.0, irrev - 0.75)
        u_long = float(umbral_freno_long) + (0.0008 * sesgo_l) + penal_irrev
        if aceleracion_lyapunov < u_long:
            return False, f"LYAPUNOV_REPULSOR(a={aceleracion_lyapunov:+.5f}<{u_long:+.5f})"
    else:
        sesgo_s = 0.0 if cfg.es_modo_test() else max(0.0, float(ctrl.get("sesgo_escudo_short", 0.0) or 0.0) + sesgo_sym)
        penal_irrev_s = 0.00004 * max(0.0, irrev - 0.75)
        u_short = float(umbral_agotamiento_short) - (0.0008 * sesgo_s) - penal_irrev_s
        if aceleracion_lyapunov > u_short:
            return False, f"LYAPUNOV_SHORT_NO_BRAKE(a={aceleracion_lyapunov:+.5f}>{u_short:+.5f})"
    return True, "OK"


def evaluar_filtro_hurst_direccional(
    direccion: str,
    hurst_actual: float,
    hurst_max_long: float = 0.485,
    hurst_max_short: float = 0.485,
) -> Tuple[bool, str]:
    es_long = str(direccion).upper() in ("BUY", "LONG")
    tope = float(hurst_max_long) if es_long else float(hurst_max_short)
    if hurst_actual > tope:
        etiqueta = "HURST_FILTER" if es_long else "P-02_HURST_SHORT"
        return False, f"{etiqueta}(H={hurst_actual:.3f}>{tope:.3f})"
    return True, "OK"


def evaluar_absorcion_ofi_hawkes(
    direccion: str,
    ofi_actual: float,
    ticks_absorcion: int,
    hawkes_actual: float,
    ofi_min_req: float = 0.13,
    ticks_min_req: int = 2,
    hawkes_min_req: float = 0.10,
    imb_l1: float = 0.0,
    cancel_net_l1: float = 0.0,
    irrev_lob: float = 0.0,
    vacio_l2_ratio: float = 1.0,
    symbol: str = "",
) -> Tuple[bool, str]:
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    irrev = float(irrev_lob or 0.0)
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    penal_entropia = 0.06 * max(0.0, irrev - 0.72)
    sesgo_sym = (
        max(-0.04, min(0.08, float(ctrl.get(f"sesgo_escudo_{symbol}", 0.0) or 0.0)))
        if (not cfg.es_modo_test() and symbol)
        else 0.0
    )

    if str(direccion).upper() in ("BUY", "LONG"):
        sesgo_l = 0.0 if cfg.es_modo_test() else max(-0.04, float(ctrl.get("sesgo_escudo_long", 0.0) or 0.0) + sesgo_sym)
        i_opp_l = max(0.0, -float(imb_l1))
        c_opp_l = max(0.0, -float(cancel_net_l1))
        barrera_muro_l1 = (0.08 * (i_opp_l * i_opp_l) / max(0.10, 1.05 - i_opp_l)) if (not cfg.es_modo_test() and i_opp_l > 0.65) else 0.0
        ofi_req_l = float(ofi_min_req) + sesgo_l + penal_entropia + barrera_muro_l1
        hawkes_req_l = float(hawkes_min_req) + (0.50 * sesgo_l)
        if (imb_l1 <= -0.78 and cancel_net_l1 <= -0.35 and ofi_actual < 0.35) or (
            not cfg.es_modo_test() and i_opp_l >= 0.88 and (c_opp_l >= 0.15 or v_l2 < 0.85) and ofi_actual < 0.55
        ):
            return False, f"L1_SPOOF_BID(imbL1={imb_l1:+.2f},cancel={cancel_net_l1:+.2f})"
        paso_rapido_1t = (
            ticks_absorcion >= 1
            and ofi_actual >= max(0.35, ofi_req_l * 2.2)
            and hawkes_actual >= max(0.20, hawkes_req_l)
            and v_l2 >= 0.85
        )
        if (ofi_actual < ofi_req_l or ticks_absorcion < ticks_min_req) and not paso_rapido_1t:
            return (
                False,
                f"WAIT_BID_ABSORPTION(OFI={ofi_actual:+.2f}[{ticks_absorcion}/{ticks_min_req}t]<{ofi_req_l:+.2f})",
            )
        if hawkes_actual < hawkes_req_l:
            return False, f"HAWKES_WEAK_LONG(I={hawkes_actual:+.2f}<{hawkes_req_l:+.2f})"
    else:
        sesgo_s = 0.0 if cfg.es_modo_test() else max(-0.04, float(ctrl.get("sesgo_escudo_short", 0.0) or 0.0) + sesgo_sym)
        i_opp_s = max(0.0, float(imb_l1))
        c_opp_s = max(0.0, float(cancel_net_l1))
        barrera_muro_s = (0.08 * (i_opp_s * i_opp_s) / max(0.10, 1.05 - i_opp_s)) if (not cfg.es_modo_test() and i_opp_s > 0.65) else 0.0
        ofi_short_req = -(abs(float(ofi_min_req)) + sesgo_s + penal_entropia + barrera_muro_s)
        hawkes_req_s = -(abs(float(hawkes_min_req)) + (0.50 * sesgo_s))
        if (imb_l1 >= 0.78 and cancel_net_l1 >= 0.35 and ofi_actual > -0.45) or (
            not cfg.es_modo_test() and i_opp_s >= 0.88 and (c_opp_s >= 0.15 or v_l2 < 0.85) and ofi_actual > -0.55
        ):
            return False, f"L1_SPOOF_ASK(imbL1={imb_l1:+.2f},cancel={cancel_net_l1:+.2f})"
        paso_rapido_s_1t = (
            ticks_absorcion >= 1
            and ofi_actual <= min(-0.45, ofi_short_req * 1.6)
            and hawkes_actual <= min(-0.20, hawkes_req_s)
            and v_l2 >= 0.85
        )
        if (ofi_actual > ofi_short_req or ticks_absorcion < ticks_min_req) and not paso_rapido_s_1t:
            return (
                False,
                f"WAIT_ASK_ABSORPTION(OFI={ofi_actual:+.2f}[{ticks_absorcion}/{ticks_min_req}t]>{ofi_short_req:+.2f})",
            )
        if hawkes_actual > hawkes_req_s:
            return False, f"HAWKES_WEAK_SHORT(I={hawkes_actual:+.2f}>{hawkes_req_s:+.2f})"
    return True, "OK"


def evaluar_conviccion_contratendencia_ema900(
    direccion: str,
    ema900_dist_pct: float,
    ofi_actual: float,
    hurst_actual: float,
    z_score: float = 0.0,
    irrev_lob: float = 0.0,
    vacio_l2_ratio: float = 1.0,
) -> Tuple[bool, str]:
    if abs(z_score) >= 6.0:
        return True, "OK"
    irrev = float(irrev_lob or 0.0)
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    ajuste_ofi = (0.06 * max(0.0, irrev - 0.70)) + (0.04 if v_l2 < 0.65 else 0.0)
    if str(direccion).upper() in ("SELL", "SHORT") and ema900_dist_pct >= 0.0050:
        ofi_req_s = -(0.42 + ajuste_ofi)
        if hurst_actual > 0.435 or ofi_actual > ofi_req_s:
            return (
                False,
                f"WEAK_COUNTER_TREND_SHORT(EMA900={ema900_dist_pct * 100:+.2f}%,OFI={ofi_actual:+.2f},H={hurst_actual:.2f})",
            )
    elif str(direccion).upper() in ("BUY", "LONG") and ema900_dist_pct <= -0.0050:
        ofi_req_l = 0.42 + ajuste_ofi
        if hurst_actual > 0.435 or ofi_actual < ofi_req_l:
            return (
                False,
                f"WEAK_COUNTER_TREND_LONG(EMA900={ema900_dist_pct * 100:+.2f}%,OFI={ofi_actual:+.2f},H={hurst_actual:.2f})",
            )
    return True, "OK"
