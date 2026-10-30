# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #5: Factor de Retencion Hiperbolico kappa(MFE_t), Test
Secuencial de Probabilidad de Abraham Wald (SPRT) Des-Saturado con Soporte de
Vacio L2 y Deteccion de Cresta sin Ventana Ciega (<20s) para Terpsichora V7.0.
"""
import math

import config_parametros as cfg


def calcular_kappa_convexo_wald(
    mfe_pct: float,
    vacio_l2_ratio: float = 1.0,
) -> float:
    piso_act = min(float(cfg.COSECHA_TRIZ_ACTIVACION_PCT), 0.0014)
    exceso = max(0.0, float(mfe_pct) - piso_act)
    base_k = 0.35 + (0.43 * math.tanh(exceso / 0.0040))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    ajuste_l2 = 0.03 * max(0.0, 0.75 - v_l2) if v_l2 < 0.75 else 0.0
    return round(min(0.82, base_k + ajuste_l2), 4)


def calcular_lambda_wald_sprt(
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    edad_seg: float,
    lambda_prev: float = 0.0,
    vol_bv: float = cfg.VOLATILIDAD_BV_PISO_MIN,
    hurst: float = 0.42,
    direccion: str = "LONG",
    vacio_l2_ratio: float = 1.0,
) -> float:
    sigma = max(float(vol_bv or cfg.VOLATILIDAD_BV_PISO_MIN), 0.00028)
    signo_dir = -1.0 if str(direccion).upper() in ("SELL", "SHORT") else 1.0
    ofi_dir = signo_dir * float(ofi_5s)
    ofi_term = ofi_dir / 0.38
    ret_raw = (float(pnl_pct) - (0.52 * float(mfe_pct))) / sigma
    ret_term = 2.60 * math.tanh(ret_raw / 2.60)
    hurst_drag = 0.14 * max(0.0, float(hurst) - 0.48) * math.sqrt(max(0.0, float(edad_seg)) / 18.0)
    time_drag = max(0.0, (float(edad_seg) - 20.0) * 0.022)

    v_l2 = max(0.20, min(3.00, float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)))
    l2_support = 0.18 * math.tanh(v_l2 - 1.0)

    d_lambda = ofi_term + ret_term + l2_support - hurst_drag - time_drag
    peso_prev = 0.72 if (float(lambda_prev) * d_lambda) > 0.0 else 0.65
    peso_step = 0.34 if abs(float(lambda_prev)) > 0.01 else 0.85
    u = (peso_prev * float(lambda_prev)) + (peso_step * d_lambda)
    val = 5.00 * math.tanh(u / 3.80)
    return round(max(-5.00, min(5.00, val)), 2)


def evaluar_agotamiento_cresta_wald(
    mfe_pct: float,
    pnl_pct: float,
    ofi_5s: float,
    edad_seg: float,
    lambda_w: float,
    kappa: float,
    direccion: str = "LONG",
) -> bool:
    signo_dir = -1.0 if str(direccion).upper() in ("SELL", "SHORT") else 1.0
    ofi_dir = signo_dir * float(ofi_5s)
    piso_be_min = max(float(cfg.TRINQUETE_BE_OFFSET_PCT), 0.00080)
    umbral_retencion = max(piso_be_min, kappa * float(mfe_pct))
    return bool(
        (mfe_pct >= 0.0042 and (pnl_pct <= (mfe_pct * 0.72) or ofi_dir <= -0.10))
        or (mfe_pct >= 0.0018 and lambda_w <= -0.85 and ofi_dir <= -0.08)
        or (edad_seg >= 20.0 and (lambda_w <= -0.25 or ofi_dir <= -0.12))
        or (mfe_pct >= 0.0022 and pnl_pct <= umbral_retencion and ofi_dir <= 0.05)
        or (pnl_pct <= (kappa * mfe_pct) and ofi_dir < 0.0)
    )
