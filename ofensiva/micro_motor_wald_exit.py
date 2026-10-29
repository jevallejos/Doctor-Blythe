# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #2: Piso Zero-Loss (SCAR-LOCK-14), Oxigeno Elastico
Temprano MFE (18s-30s) Acoplado a Vacio Profundo L2 e Inhibidor de MAKER_UNWIND
en Rally para HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
import math
import config_parametros as cfg
import core_estado_ram as ram


def calcular_piso_cero_perdida(
    precio_entrada: float,
    direccion: str,
    tick_size: float = 0.0001,
) -> float:
    offset_min = max(
        float(cfg.TRINQUETE_BE_OFFSET_PCT),
        (cfg.COMISION_MAKER_PCT + cfg.COMISION_TAKER_PCT) * 1.15,
    )
    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    t_size = max(1e-8, float(tick_size))
    decimales = max(0, int(round(-math.log10(t_size)))) if t_size < 1.0 else 2
    if dir_norm == "LONG":
        raw = precio_entrada * (1.0 + offset_min)
        piso = round(math.ceil((raw / t_size) - 1e-9) * t_size, decimales)
        if piso <= precio_entrada:
            piso = round(precio_entrada + max(t_size, 1e-6), 6)
        return piso
    else:
        raw = precio_entrada * (1.0 - offset_min)
        techo = round(math.floor((raw / t_size) + 1e-9) * t_size, decimales)
        if techo >= precio_entrada:
            techo = round(precio_entrada - max(t_size, 1e-6), 6)
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
    """
    Otorga oxigeno elastico ante micro-retrocesos sobre el piso Break-Even temprano
    cuando el flujo H-OFI y el soporte L2 (vacio_l2_ratio) confirman que el impulso
    sigue vivo, evitando liquidar en el piso del pullback (Casos Trades #20, #72, #81).
    """
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
) -> bool:
    if pnl_pct < 0.00095:
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
    if v_l2 >= 1.45 and ofi_dir >= 0.06 and retroceso <= (tol_retroceso * 1.25):
        return True
    if pnl_pct < 0.0011:
        return False
    return bool(retroceso <= tol_retroceso and ofi_dir >= 0.10)