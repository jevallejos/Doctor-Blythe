# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #2: Piso Zero-Loss (SCAR-LOCK-14), Trinquete Convexo
Unificado de Wald, Oxigeno Elastico Temprano MFE Acoplado a Vacio Profundo L2 e
Inhibidor de MAKER_UNWIND en Rally para HFT Doctor Blythe Terpsichora V7.0.
"""
import math

import config_parametros as cfg
import core_estado_ram as ram
from ofensiva import micro_cresta_convexo_sprt as mcw


def calcular_ratchet_convexo_mfe_elastico(
    precio_entrada: float,
    mfe_pct: float,
    v_l2: float,
    eta_mfe_hist: float,
    es_long: bool,
    tick_size: float,
    fee_maker: float = 0.0002,
) -> float:
    piso_fee_pct = max(float(cfg.TRINQUETE_BE_OFFSET_PCT), 2.0 * float(fee_maker) + 0.00015)
    mfe_dec = float(mfe_pct) / 100.0 if abs(float(mfe_pct)) > 0.05 else float(mfe_pct)
    if mfe_dec <= piso_fee_pct:
        return float(precio_entrada) * (1.0 + piso_fee_pct if es_long else 1.0 - piso_fee_pct)

    kappa_base = mcw.calcular_kappa_convexo_wald(mfe_dec, vacio_l2_ratio=v_l2)
    eta_clamped = max(0.0, min(1.0, float(eta_mfe_hist)))
    v_freno = math.tanh(max(0.0, float(v_l2) - 1.0))
    kappa_lock = max(0.35, min(0.82, kappa_base + 0.08 * (0.65 - eta_clamped) - 0.05 * v_freno))
    ganancia_bloqueada_pct = max(piso_fee_pct, mfe_dec * kappa_lock)
    t_sz = float(tick_size) if float(tick_size) > 0.0 else 0.0
    if es_long:
        raw_p = float(precio_entrada) * (1.0 + ganancia_bloqueada_pct)
        return round(math.ceil((raw_p / t_sz) - 1e-9) * t_sz, 8) if t_sz > 0.0 else raw_p
    raw_p = float(precio_entrada) * (1.0 - ganancia_bloqueada_pct)
    return round(math.floor((raw_p / t_sz) + 1e-9) * t_sz, 8) if t_sz > 0.0 else raw_p


def calcular_piso_cero_perdida(
    precio_entrada: float,
    direccion: str,
    tick_size: float = 0.0001,
    mfe_pct: float = 0.0,
    v_l2: float = 1.0,
    eta_mfe_hist: float = 0.45,
) -> float:
    offset_min = max(
        float(cfg.TRINQUETE_BE_OFFSET_PCT),
        (cfg.COMISION_MAKER_PCT + cfg.COMISION_TAKER_PCT) * 1.15,
    )
    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    t_size = max(1e-8, float(tick_size))
    decimales = max(0, int(round(-math.log10(t_size)))) if t_size < 1.0 else 2
    piso_ratchet = calcular_ratchet_convexo_mfe_elastico(
        precio_entrada,
        mfe_pct,
        v_l2,
        eta_mfe_hist,
        dir_norm == "LONG",
        t_size,
        fee_maker=float(cfg.COMISION_MAKER_PCT),
    )

    if dir_norm == "LONG":
        raw = precio_entrada * (1.0 + offset_min)
        piso = round(math.ceil((raw / t_size) - 1e-9) * t_size, decimales)
        if piso <= precio_entrada:
            piso = round(precio_entrada + max(t_size, 1e-6), 6)
        if not cfg.es_modo_test() and mfe_pct > 0.0014:
            piso = max(piso, round(piso_ratchet, decimales))
        return piso
    else:
        raw = precio_entrada * (1.0 - offset_min)
        techo = round(math.floor((raw / t_size) + 1e-9) * t_size, decimales)
        if techo >= precio_entrada:
            techo = round(precio_entrada - max(t_size, 1e-6), 6)
        if not cfg.es_modo_test() and mfe_pct > 0.0014:
            techo = min(techo, round(piso_ratchet, decimales))
        return techo


def debe_absorber_micro_retroceso_be_temprano(
    direccion: str,
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    lambda_wald: float,
    trailing_wald_activo: bool,
    symbol: str = "",
    vacio_l2_ratio: float = 1.0,
) -> bool:
    if trailing_wald_activo or mfe_pct >= cfg.COSECHA_TRIZ_ACTIVACION_PCT:
        return False

    es_hb = cfg.obtener_clase_activo(symbol) == cfg.CLASE_HIGH_BETA if symbol else True
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    if symbol and v_l2 == 1.0 and not cfg.es_modo_test():
        m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
        if m_live is not None:
            v_l2 = float(getattr(m_live, "vacio_l2_ratio", 1.0) or 1.0)

    mod_vacio = max(0.90, min(1.25, 0.85 + (0.15 * v_l2)))
    ventana_base = 24.0 if es_hb else 18.0
    ventana_max = ventana_base * mod_vacio
    if edad_seg >= ventana_max:
        return False

    piso_neto_vivo = (0.00045 if v_l2 >= 1.20 else 0.00048) if es_hb else (0.00050 if v_l2 >= 1.20 else 0.00055)
    if pnl_pct < piso_neto_vivo:
        return False

    es_long = str(direccion).upper() in ("BUY", "LONG")
    ofi_dir = float(ofi_5s) if es_long else -float(ofi_5s)
    umbral_ofi_min = 0.04 if v_l2 >= 1.25 else 0.06
    umbral_lambda_min = -0.35 if v_l2 >= 1.25 else -0.10
    flujo_vivo = (ofi_dir >= umbral_ofi_min) and (lambda_wald >= umbral_lambda_min)
    return bool(flujo_vivo)


def debe_inhibir_maker_unwind_en_rally(
    direccion: str,
    pnl_pct: float,
    mfe_actual: float,
    ofi_5s: float,
    symbol: str = "",
    vacio_l2_ratio: float = 1.0,
    lambda_wald: float = 0.0,
    cosecha_parcial_ejecutada: bool = False,
) -> bool:
    piso_rally = 0.00060 if cosecha_parcial_ejecutada else 0.00095
    if pnl_pct < piso_rally:
        return False

    es_hb = cfg.obtener_clase_activo(symbol) == cfg.CLASE_HIGH_BETA if symbol else True
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    if symbol and v_l2 == 1.0 and not cfg.es_modo_test():
        m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
        if m_live is not None:
            v_l2 = float(getattr(m_live, "vacio_l2_ratio", 1.0) or 1.0)

    tol_retroceso = 0.00045 if es_hb else 0.00030
    if lambda_wald >= 1.20 and v_l2 >= 1.25:
        tol_retroceso *= 1.20

    retroceso = max(0.0, mfe_actual - pnl_pct)
    es_long = str(direccion).upper() in ("BUY", "LONG")
    ofi_dir = float(ofi_5s) if es_long else -float(ofi_5s)
    if cosecha_parcial_ejecutada and ofi_dir >= 0.02 and lambda_wald >= 0.15 and retroceso <= (tol_retroceso * 1.35):
        return True
    if v_l2 >= 1.45 and ofi_dir >= 0.06 and retroceso <= (tol_retroceso * 1.25):
        return True
    if pnl_pct < 0.0011:
        return False
    return bool(retroceso <= tol_retroceso and ofi_dir >= 0.10)
