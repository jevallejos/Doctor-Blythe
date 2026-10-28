# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #2: Piso Zero-Loss (SCAR-LOCK-14), Oxigeno Temprano MFE (24s)
con Elasticidad por Clase (High-Beta vs Tier-1) e Inhibidor de MAKER_UNWIND en Rally / Vacio L2.
"""
import math
import config_parametros as cfg


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
) -> bool:
    if trailing_wald_activo or mfe_pct >= cfg.COSECHA_TRIZ_ACTIVACION_PCT:
        return False
    es_hb = cfg.obtener_clase_activo(symbol) == cfg.CLASE_HIGH_BETA if symbol else True
    ventana_max = 24.0 if es_hb else 18.0
    if edad_seg >= ventana_max:
        return False
    piso_neto_vivo = 0.00048 if es_hb else 0.00055
    if pnl_pct < piso_neto_vivo:
        return False
    es_long = str(direccion).upper() in ("BUY", "LONG")
    flujo_vivo = (
        (es_long and ofi_5s >= 0.06 and lambda_wald >= -0.10)
        or ((not es_long) and ofi_5s <= -0.06 and lambda_wald >= -0.10)
    )
    return bool(flujo_vivo)


def debe_inhibir_maker_unwind_en_rally(
    direccion: str,
    pnl_pct: float,
    mfe_actual: float,
    ofi_5s: float,
    symbol: str = "",
    vacio_l2_ratio: float = 1.0,
) -> bool:
    if pnl_pct < 0.00095:
        return False
    es_hb = cfg.obtener_clase_activo(symbol) == cfg.CLASE_HIGH_BETA if symbol else True
    tol_retroceso = 0.00045 if es_hb else 0.00030
    retroceso = max(0.0, mfe_actual - pnl_pct)
    es_long = str(direccion).upper() in ("BUY", "LONG")
    ofi_dir = float(ofi_5s) if es_long else -float(ofi_5s)
    if float(vacio_l2_ratio) >= 1.45 and ofi_dir >= 0.06 and retroceso <= (tol_retroceso * 1.25):
        return True
    if pnl_pct < 0.0011:
        return False
    return bool(retroceso <= tol_retroceso and ofi_dir >= 0.10)
