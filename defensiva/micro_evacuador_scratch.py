# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #4: Geometria MarkPrice Stop-Loss (SEI-02), Calculo de
Niveles SL Iniciales, Ley 2 (RF-18) de Evacuacion Pasiva Maker-Scratch 18.0s
con Ventana de Maduracion Fractal (30.0s) y Tope Anti-Deslizamiento en Caida Libre.
"""
from typing import Tuple
import config_parametros as cfg
from ofensiva import micro_cotizador_stoikov as mcs


def calcular_niveles_sl_iniciales(
    precio_entrada: float,
    side: str,
    tick_size: float = 0.0001,
) -> Tuple[float, float]:
    sl_int_pct = float(cfg.SL_INTERNO_PCT)
    sl_bybit_pct = float(cfg.obtener_aux("SL_EMERGENCIA_BYBIT_PCT", 0.0068))
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
    if dir_norm == "LONG":
        sl_int = mcs.cuantizar_tick(precio_entrada * (1.0 - sl_int_pct), tick_size, modo="floor")
        sl_srv = mcs.cuantizar_tick(precio_entrada * (1.0 - sl_bybit_pct), tick_size, modo="floor")
    else:
        sl_int = mcs.cuantizar_tick(precio_entrada * (1.0 + sl_int_pct), tick_size, modo="ceil")
        sl_srv = mcs.cuantizar_tick(precio_entrada * (1.0 + sl_bybit_pct), tick_size, modo="ceil")
    return sl_int, sl_srv


def ajustar_geometria_sl_markprice(
    sl_precio: float,
    direccion: str,
    bid_live: float,
    ask_live: float,
    tick_size: float,
    buffer_ticks: float = 1.0,
) -> float:
    t_size = max(1e-8, float(tick_size))
    sl_seguro = float(sl_precio)
    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    if bid_live > 0.0 and ask_live > 0.0:
        if dir_norm == "LONG" and sl_seguro >= bid_live:
            sl_seguro = mcs.cuantizar_tick(bid_live - (buffer_ticks * t_size), t_size, modo="floor")
        elif dir_norm == "SHORT" and sl_seguro <= ask_live:
            sl_seguro = mcs.cuantizar_tick(ask_live + (buffer_ticks * t_size), t_size, modo="ceil")
    return sl_seguro


def evaluar_gatillo_maker_scratch_18s(
    direccion: str,
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    lambda_w: float,
    trinquete_be_activo: bool,
    hurst_actual: float = 0.42,
    fill_post_aborto: bool = False,
) -> bool:
    t_scratch = float(cfg.obtener_aux("MAKER_SCRATCH_TIEMPO_SEG", 18.0))
    ofi_adv = float(cfg.obtener_aux("MAKER_SCRATCH_OFI_ADVERSO", -0.15))

    # 0. Vigilancia acelerada (10.0s) si el fill ocurrio en transito durante un Early Queue Abort (Caso Trade #9)
    if fill_post_aborto and edad_seg >= 10.0 and not trinquete_be_activo:
        if mfe_pct <= 0.00015 and pnl_pct <= -0.00055:
            return True

    # 1. Regla Invariante RF-18 (Test 16/18): Fill muerto sin ningun rebote (MFE <= +0.015%)
    sin_rebote_18s = (
        edad_seg >= 18.0
        and not trinquete_be_activo
        and mfe_pct <= 0.00015
        and pnl_pct <= -0.0007
    )
    if sin_rebote_18s:
        return True

    # 2. Ventana de Maduracion Fractal (Casos Trade #6 y Trade #11):
    tuvo_pulso_inicial = (mfe_pct >= 0.00040) and (hurst_actual <= 0.44)
    edad_min_flujo = 30.0 if tuvo_pulso_inicial else max(18.0, t_scratch)

    if tuvo_pulso_inicial and edad_seg < 30.0:
        colapso_profundo = (pnl_pct <= -0.0015) and (
            (direccion == "LONG" and ofi_5s <= -0.42)
            or (direccion == "SHORT" and ofi_5s >= 0.42)
        )
        if not colapso_profundo:
            return False

    flujo_contra = (
        (direccion == "LONG" and ofi_5s <= ofi_adv)
        or (direccion == "SHORT" and ofi_5s >= abs(ofi_adv))
    )

    scratch_por_flujo = (
        edad_seg >= edad_min_flujo
        and not trinquete_be_activo
        and pnl_pct <= -0.00045
        and flujo_contra
    )
    scratch_por_wald = (
        edad_seg >= max(edad_min_flujo, t_scratch)
        and not trinquete_be_activo
        and pnl_pct <= -0.0006
        and lambda_w <= -1.20
    )
    return bool(scratch_por_flujo or scratch_por_wald)


def debe_escalar_scratch_colgado_a_taker(
    direccion: str,
    edad_orden_salida_seg: float,
    pnl_pct: float,
    ofi_5s: float,
    motivo_pendiente: str,
) -> bool:
    """
    Evita el deslizamiento pasivo de 36s del Trade #2 (-0.3027%):
    Si una orden PostOnly de MAKER_SCRATCH_18S lleva >= 5.0s sin llenarse mientras
    el precio cae por debajo de -0.14% con flujo adverso, o si el PnL deteriora a <= -0.20%,
    corta la espera pasiva y evacua de inmediato antes de llegar al Stop-Loss.
    """
    if "SCRATCH" not in str(motivo_pendiente).upper():
        return False
    if pnl_pct <= -0.0020 and edad_orden_salida_seg >= 2.5:
        return True
    flujo_fuerte_contra = (
        (direccion == "LONG" and ofi_5s <= -0.30)
        or (direccion == "SHORT" and ofi_5s >= 0.30)
    )
    if edad_orden_salida_seg >= 5.0 and pnl_pct <= -0.0014 and flujo_fuerte_contra:
        return True
    return False
