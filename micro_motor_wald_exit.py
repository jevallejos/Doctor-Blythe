# -*- coding: utf-8 -*-
"""
Micro-Modulo Independiente de Salida Ganadora y Trinquete de Abraham Wald (SPRT).
Conectado a las constantes reales de config_parametros.py (COMISION_MAKER_PCT,
COMISION_TAKER_PCT, TRINQUETE_BE_OFFSET_PCT) y a gestor_posiciones.py.
"""
import math
from typing import Tuple
import config_parametros as cfg


def calcular_piso_cero_perdida(
    precio_entrada: float,
    direccion: str,
    tick_size: float = 0.0001,
) -> float:
    """
    SCAR-LOCK-14: Calcula el piso exacto libre de comisiones (Zero-Loss Floor).
    """
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
) -> bool:
    """
    Solucion al Caso Trade #3 (salida prematura a los 8.06s en el inicio de un rally de +1.56%):
    Cuando el Early Break-Even Ratchet (+0.11% MFE) esta activo pero aun no llegamos a la
    Cresta de Wald (+0.22%), si el trade tiene menos de 22s, sigue en ganancia neta
    (>= +0.055% libre de comisiones Maker) y el flujo OFI_5s sigue empujando a favor (>= +0.08),
    absorbe el micro-retroceso de 1 tick para no ahogar el despegue.
    """
    if trailing_wald_activo or mfe_pct >= cfg.COSECHA_TRIZ_ACTIVACION_PCT:
        return False
    if edad_seg >= 22.0:
        return False
    if pnl_pct < 0.00055:
        return False

    flujo_vivo = (
        (direccion == "LONG" and ofi_5s >= 0.08 and lambda_wald >= 0.0)
        or (direccion == "SHORT" and ofi_5s <= -0.08 and lambda_wald >= 0.0)
    )
    return bool(flujo_vivo)


def debe_inhibir_maker_unwind_en_rally(
    direccion: str,
    pnl_pct: float,
    mfe_actual: float,
    ofi_5s: float,
) -> bool:
    """
    Solucion al Caso Trade #7 (salida prematura por MAKER_UNWIND en pleno rally):
    Si la posicion en Fase 2 lleva ganancia saludable (>= +0.12%), esta pegada a su
    maximo MFE (retroceso <= 0.035%) y el flujo OFI de 5s sigue empujando con fuerza
    a favor (>= +0.12 en LONG o <= -0.12 en SHORT), inhibe el cierre por estancamiento
    para permitir que alcance la Cresta de Wald (+0.22%..+0.90%).
    """
    if pnl_pct < 0.0012:
        return False
    retroceso = max(0.0, mfe_actual - pnl_pct)
    flujo_fuerte = (
        (direccion == "LONG" and ofi_5s >= 0.12)
        or (direccion == "SHORT" and ofi_5s <= -0.12)
    )
    return bool(retroceso <= 0.00035 and flujo_fuerte)
