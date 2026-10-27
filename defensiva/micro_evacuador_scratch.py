# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #4: Geometria MarkPrice Stop-Loss (SEI-02), Calculo de
Niveles SL Iniciales y Ley 2 (RF-18) de Evacuacion Pasiva Maker-Scratch 18.0s.
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
) -> bool:
    t_scratch = float(cfg.obtener_aux("MAKER_SCRATCH_TIEMPO_SEG", 18.0))
    ofi_adv = float(cfg.obtener_aux("MAKER_SCRATCH_OFI_ADVERSO", -0.15))
    flujo_contra = (
        (direccion == "LONG" and ofi_5s <= ofi_adv)
        or (direccion == "SHORT" and ofi_5s >= abs(ofi_adv))
    )
    sin_rebote_18s = (
        edad_seg >= 18.0
        and not trinquete_be_activo
        and mfe_pct <= 0.00015
        and pnl_pct <= -0.0007
    )
    return bool(
        (edad_seg >= 18.0 and pnl_pct <= 0.0 and flujo_contra)
        or sin_rebote_18s
        or (edad_seg >= t_scratch and pnl_pct <= -0.0006 and lambda_w <= -1.20)
    )
