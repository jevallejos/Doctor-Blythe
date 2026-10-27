# -*- coding: utf-8 -*-
"""
Micro-Modulo Independiente de Salida Ganadora y Trinquete de Abraham Wald (SPRT).
Aisla el calculo del piso Zero-Loss cuantizado por tick, el oxigeno temprano MFE
y el inhibidor de MAKER_UNWIND cuando el trade ganador sigue en expansion.
"""
import math
from typing import Any, Dict, Tuple
import config_parametros as cfg


def calcular_piso_cero_perdida(
    precio_entrada: float,
    direccion: str,
    tick_size: float,
    es_entrada_maker: bool = True,
    es_salida_maker: bool = True,
    colchon_neto_pct: float = 0.00025,
) -> float:
    """
    Calcula el precio exacto de salida que garantiza PnL neto > 0 despues de comisiones
    Bybit UTA, cuantizado estrictamente hacia el lado seguro del tick_size.
    """
    fee_in = (
        float(getattr(cfg, "BYBIT_TAKER_FEE_PCT", 0.00055))
        if not es_entrada_maker
        else float(getattr(cfg, "BYBIT_MAKER_FEE_PCT", 0.00020))
    )
    fee_out = (
        float(getattr(cfg, "BYBIT_MAKER_FEE_PCT", 0.00020))
        if es_salida_maker
        else float(getattr(cfg, "BYBIT_TAKER_FEE_PCT", 0.00055))
    )
    delta_min_pct = fee_in + fee_out + max(0.00010, colchon_neto_pct)

    if direccion == "LONG":
        precio_crudo = precio_entrada * (1.0 + delta_min_pct)
        if tick_size > 0.0:
            ticks = math.ceil((precio_crudo - precio_entrada) / tick_size)
            ticks = max(1, ticks)
            return round(precio_entrada + (ticks * tick_size), 8)
        return round(precio_crudo, 8)
    else:
        precio_crudo = precio_entrada * (1.0 - delta_min_pct)
        if tick_size > 0.0:
            ticks = math.ceil((precio_entrada - precio_crudo) / tick_size)
            ticks = max(1, ticks)
            return round(precio_entrada - (ticks * tick_size), 8)
        return round(precio_crudo, 8)


def calcular_sl_trinquete_oxigenado(
    precio_entrada: float,
    direccion: str,
    tick_size: float,
    es_entrada_maker: bool,
    mfe_actual: float,
    edad_seg: float,
    ofi_actual: float,
) -> float:
    """
    Determina el nivel del candado ganador (Early Break-Even / Progressive Ratchet):
    - Si el trade tiene menos de 25s y MFE entre +0.12% y +0.21% con flujo OFI no adverso,
      fija un colchon neto de +0.035% (Total ~+0.075% bruto = 2 ticks sobre entrada) para
      no ahogar el trade a los 8s en un retroceso normal de 1 tick (Caso Trade #3).
    - Si el MFE ya supero +0.21% o el flujo OFI se giro en contra, asegura el 62% del MFE.
    """
    flujo_a_favor = (
        (direccion == "LONG" and ofi_actual >= -0.05)
        or (direccion == "SHORT" and ofi_actual <= 0.05)
    )

    if edad_seg < 25.0 and mfe_actual < 0.0021 and flujo_a_favor:
        colchon_dinamico = 0.00035
    else:
        colchon_dinamico = max(0.00045, mfe_actual * 0.58)

    return calcular_piso_cero_perdida(
        precio_entrada,
        direccion,
        tick_size,
        es_entrada_maker=es_entrada_maker,
        es_salida_maker=True,
        colchon_neto_pct=colchon_dinamico,
    )


def debe_inhibir_maker_unwind_en_rally(
    direccion: str,
    pnl_pct: float,
    mfe_actual: float,
    ofi_actual: float,
) -> bool:
    """
    Evita que el reloj fijo de 42s (MAKER_UNWIND) corte un tiro ganador que va en pleno
    despegue cerca de su MFE con flujo OFI saludable (Caso Trade #7 a las 21:49:37 CL).
    """
    if pnl_pct < 0.0011:
        return False

    retroceso_desde_pico = max(0.0, mfe_actual - pnl_pct)
    flujo_sano = (
        (direccion == "LONG" and ofi_actual >= -0.10)
        or (direccion == "SHORT" and ofi_actual <= 0.10)
    )

    if retroceso_desde_pico <= 0.00055 and flujo_sano:
        return True
    return False
