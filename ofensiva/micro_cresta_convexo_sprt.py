# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #5: Factor de Retencion Hiperbolico kappa(MFE_t),
Test Secuencial de Probabilidad de Abraham Wald (SPRT) y Deteccion de Cresta.
"""
import math
import config_parametros as cfg


def calcular_kappa_convexo_wald(mfe_pct: float) -> float:
    exceso = max(0.0, float(mfe_pct) - float(cfg.COSECHA_TRIZ_ACTIVACION_PCT))
    return round(0.35 + (0.43 * math.tanh(exceso / 0.0045)), 4)


def calcular_lambda_wald_sprt(
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    edad_seg: float,
    lambda_prev: float = 0.0,
    vol_bv: float = cfg.VOLATILIDAD_BV_PISO_MIN,
    hurst: float = 0.42,
) -> float:
    sigma = max(float(vol_bv or cfg.VOLATILIDAD_BV_PISO_MIN), 0.00045)
    ofi_term = float(ofi_5s) / 0.35
    ret_term = (float(pnl_pct) - (0.55 * float(mfe_pct))) / sigma
    hurst_drag = 0.14 * max(0.0, float(hurst) - 0.48) * math.sqrt(max(0.0, float(edad_seg)) / 18.0)
    time_drag = max(0.0, (float(edad_seg) - 20.0) * 0.035)
    d_lambda = ofi_term + ret_term - hurst_drag - time_drag
    val = (0.86 * float(lambda_prev)) + d_lambda
    return round(max(-5.00, min(5.00, val)), 2)


def evaluar_agotamiento_cresta_wald(
    mfe_pct: float,
    pnl_pct: float,
    ofi_5s: float,
    edad_seg: float,
    lambda_w: float,
    kappa: float,
) -> bool:
    return bool(
        (mfe_pct >= 0.0042 and (pnl_pct <= (mfe_pct * 0.72) or ofi_5s <= -0.10))
        or (edad_seg >= 20.0 and (lambda_w <= -0.25 or ofi_5s <= -0.12))
        or (pnl_pct <= (kappa * mfe_pct))
    )
