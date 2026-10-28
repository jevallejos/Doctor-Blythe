# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #5: Factor de Retencion Hiperbolico kappa(MFE_t),
Test Secuencial de Probabilidad de Abraham Wald (SPRT) y Deteccion de Cresta.
"""
import math
import config_parametros as cfg


def calcular_kappa_convexo_wald(mfe_pct: float) -> float:
    piso_act = min(float(cfg.COSECHA_TRIZ_ACTIVACION_PCT), 0.0014)
    exceso = max(0.0, float(mfe_pct) - piso_act)
    return round(0.35 + (0.43 * math.tanh(exceso / 0.0040)), 4)


def calcular_lambda_wald_sprt(
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    edad_seg: float,
    lambda_prev: float = 0.0,
    vol_bv: float = cfg.VOLATILIDAD_BV_PISO_MIN,
    hurst: float = 0.42,
    direccion: str = "LONG",
) -> float:
    sigma = max(float(vol_bv or cfg.VOLATILIDAD_BV_PISO_MIN), 0.00045)
    signo_dir = -1.0 if str(direccion).upper() in ("SELL", "SHORT") else 1.0
    ofi_dir = signo_dir * float(ofi_5s)
    ofi_term = ofi_dir / 0.35
    ret_term = (float(pnl_pct) - (0.55 * float(mfe_pct))) / sigma
    hurst_drag = 0.14 * max(0.0, float(hurst) - 0.48) * math.sqrt(max(0.0, float(edad_seg)) / 18.0)
    time_drag = max(0.0, (float(edad_seg) - 20.0) * 0.025)
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
    direccion: str = "LONG",
) -> bool:
    signo_dir = -1.0 if str(direccion).upper() in ("SELL", "SHORT") else 1.0
    ofi_dir = signo_dir * float(ofi_5s)
    piso_be_min = max(float(cfg.TRINQUETE_BE_OFFSET_PCT), 0.00080)
    umbral_retencion = max(piso_be_min, kappa * float(mfe_pct))
    return bool(
        (mfe_pct >= 0.0042 and (pnl_pct <= (mfe_pct * 0.72) or ofi_dir <= -0.10))
        or (edad_seg >= 20.0 and (lambda_w <= -0.25 or ofi_dir <= -0.12))
        or (mfe_pct >= 0.0022 and pnl_pct <= umbral_retencion and ofi_dir <= 0.05)
        or (pnl_pct <= (kappa * mfe_pct) and ofi_dir < 0.0)
    )
