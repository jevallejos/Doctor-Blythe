# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #4: Geometria MarkPrice Stop-Loss (SEI-02), Calculo de Niveles SL Iniciales,
Ley 2 (RF-18) de Evacuacion Pasiva Maker-Scratch 18.0s con Compensacion de Deriva Negativa Post-Fill
de DeLise (arXiv:2407.16527, pendiente t=6s->18s) y Tope Anti-Deslizamiento en Caida Libre.
"""
from typing import Dict, Optional, Tuple
import config_parametros as cfg
from ofensiva import micro_cotizador_stoikov as mcs
from ofensiva import micro_impulso_runner as mir


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


def calcular_pendiente_recuperacion_delise(
    pnl_pct: float,
    mae_pct: float,
    edad_seg: float,
    trayectoria_pnl: Optional[Dict[str, float]] = None,
) -> float:
    """
    Mejora de Frontera #4 (arXiv:2407.16527 - DeLise Post-Fill Negative Drift):
    Calcula la pendiente de recuperacion cinematica entre t=5..6s (o el piso MAE inicial)
    y el instante actual t >= 12s.
    """
    if edad_seg < 8.0:
        return 0.0
    ref_pct = float(mae_pct)
    if isinstance(trayectoria_pnl, dict) and "5s" in trayectoria_pnl:
        ref_pct = min(float(mae_pct), float(trayectoria_pnl["5s"]) / 100.0)
    dt = max(1.0, float(edad_seg) - 5.0)
    return round((float(pnl_pct) - ref_pct) / dt, 6)


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
    mae_pct: float = 0.0,
    trayectoria_pnl: Optional[Dict[str, float]] = None,
) -> bool:
    t_scratch = float(cfg.obtener_aux("MAKER_SCRATCH_TIEMPO_SEG", 18.0))
    ofi_adv = float(cfg.obtener_aux("MAKER_SCRATCH_OFI_ADVERSO", -0.15))

    # 0. Vigilancia acelerada (10.0s) si el fill ocurrio en transito durante un Early Queue Abort
    if fill_post_aborto and edad_seg >= 10.0 and not trinquete_be_activo:
        if mfe_pct <= 0.00015 and pnl_pct <= -0.00055:
            return True

    # Mejora #4 (DeLise arXiv:2407.16527): Pendiente de recuperacion entre 6s y 18s
    pendiente_delise = calcular_pendiente_recuperacion_delise(
        pnl_pct, mae_pct, edad_seg, trayectoria_pnl=trayectoria_pnl
    )
    flujo_recuperando = (
        (direccion == "LONG" and ofi_5s >= 0.10)
        or (direccion == "SHORT" and ofi_5s <= -0.10)
    )
    recuperacion_delise_activa = (
        edad_seg < 28.0
        and pendiente_delise >= 0.000025
        and flujo_recuperando
        and pnl_pct > -0.0012
    )

    # 1. Regla Invariante RF-18 (Test 16/18): Fill muerto sin rebote ni recuperacion DeLise
    sin_rebote_18s = (
        edad_seg >= 18.0
        and not trinquete_be_activo
        and mfe_pct <= 0.00015
        and pnl_pct <= -0.0007
        and not recuperacion_delise_activa
    )
    if sin_rebote_18s:
        return True

    # 2. Ventana de Maduracion Fractal y Proteccion de Semilla Ganadora
    semilla_protegida = mir.proteger_semilla_ganadora_de_scratch(
        edad_seg, pnl_pct, mfe_pct, ofi_5s, direccion
    )
    tuvo_pulso_inicial = (
        semilla_protegida
        or recuperacion_delise_activa
        or ((mfe_pct >= 0.00040) and (hurst_actual <= 0.44))
    )
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
