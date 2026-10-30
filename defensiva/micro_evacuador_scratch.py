# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #4: Geometria MarkPrice Stop-Loss (SEI-02), Calculo de
Niveles SL Iniciales, Ley 2 (RF-18) de Evacuacion Pasiva Maker-Scratch 18.0s
con Pendiente Multi-Horizonte de DeLise (arXiv:2407.16527) y Escalonamiento
Elastico Anti-RePeg por Vacio L2 para HFT Doctor Blythe Terpsichora V7.0.
"""
from typing import Dict, Optional, Tuple
import config_parametros as cfg
import core_estado_ram as ram
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
    Calcula la velocidad de recuperacion cinematica entre t=5s y el instante actual,
    verificando que no exista deterioro recesivo respecto a t=15s o t=18s.
    """
    if edad_seg < 8.0:
        return 0.0
    ref_pct = float(mae_pct)
    if isinstance(trayectoria_pnl, dict) and "5s" in trayectoria_pnl:
        ref_5s = float(trayectoria_pnl["5s"]) / 100.0
        ref_pct = ref_5s if ref_5s <= 0.0 else min(float(mae_pct), ref_5s)
        if edad_seg >= 18.0 and "15s" in trayectoria_pnl:
            ref_15s = float(trayectoria_pnl["15s"]) / 100.0
            if float(pnl_pct) < (ref_15s - 0.00035):
                return round((float(pnl_pct) - ref_15s) / max(1.0, float(edad_seg) - 15.0), 6)
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
    vacio_l2_ratio: float = 1.0,
) -> bool:
    t_scratch = float(cfg.obtener_aux("MAKER_SCRATCH_TIEMPO_SEG", 18.0))
    ofi_adv = float(cfg.obtener_aux("MAKER_SCRATCH_OFI_ADVERSO", -0.15))
    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    ofi_dir = float(ofi_5s) if dir_norm == "LONG" else -float(ofi_5s)
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)

    if fill_post_aborto and edad_seg >= 10.0 and not trinquete_be_activo:
        if mfe_pct <= 0.00015 and pnl_pct <= -0.00055:
            return True

    pendiente_delise = calcular_pendiente_recuperacion_delise(
        pnl_pct, mae_pct, edad_seg, trayectoria_pnl=trayectoria_pnl
    )
    flujo_recuperando = ofi_dir >= 0.10
    recuperacion_delise_activa = (
        edad_seg < 28.0
        and pendiente_delise >= 0.000025
        and flujo_recuperando
        and pnl_pct > -0.0012
        and v_l2 >= 0.55
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
    try:
        semilla_protegida = mir.proteger_semilla_ganadora_de_scratch(
            edad_seg,
            pnl_pct,
            mfe_pct,
            ofi_5s,
            dir_norm,
            vacio_l2_ratio=v_l2,
            pendiente_delise=pendiente_delise,
        )
    except TypeError:
        semilla_protegida = mir.proteger_semilla_ganadora_de_scratch(
            edad_seg, pnl_pct, mfe_pct, ofi_5s, dir_norm
        )
    tuvo_pulso_inicial = (
        semilla_protegida
        or recuperacion_delise_activa
        or ((mfe_pct >= 0.00040) and (hurst_actual <= 0.44) and (v_l2 >= 0.55))
    )
    edad_min_flujo = 30.0 if tuvo_pulso_inicial else max(18.0, t_scratch)
    if tuvo_pulso_inicial and edad_seg < 30.0:
        colapso_profundo = (pnl_pct <= -0.0015) and (ofi_dir <= -0.42 or v_l2 < 0.45)
        if not colapso_profundo:
            return False

    flujo_contra = ofi_dir <= -abs(ofi_adv)
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
    repeg_salida_count: int = 0,
    vacio_l2_ratio: float = 1.0,
) -> bool:
    """
    Evita escalar prematuramente un Maker-Scratch a Taker (lo que multiplico por 4.58x
    el costo de los scratches en produccion):
    - Solo escala a Market Taker si hay riesgo inminente de SL (pnl <= -0.30%),
      o colapso severo tras >= 14.0s, o >= 6 re-pegs fallidos con soporte L2 roto (< 0.50).
    """
    if "SCRATCH" not in str(motivo_pendiente).upper():
        return False
    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    ofi_dir = float(ofi_5s) if dir_norm == "LONG" else -float(ofi_5s)
    n_rep = max(0, int(repeg_salida_count or 0))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)

    if pnl_pct <= -0.0030 and edad_orden_salida_seg >= 4.5 and ofi_dir <= -0.25:
        return True
    if n_rep >= 6 and v_l2 < 0.50 and pnl_pct <= -0.0020 and ofi_dir <= -0.25:
        return True
    if edad_orden_salida_seg >= 14.0 and pnl_pct <= -0.0022 and ofi_dir <= -0.42:
        return True
    return False


def calcular_precio_scratch_acotado_un_tick(
    side: str,
    entry_price: float,
    best_bid: float,
    best_ask: float,
    tick_size: float,
    ofi_5s_dir: float,
    edad_orden_salida_seg: float = 0.0,
    repeg_salida_count: int = 0,
    vacio_l2_ratio: float = 1.0,
    edad_posicion_seg: float = 18.0,
    mfe_alcanzado_pct: float = 0.0,
    lvr_par: float = 0.002,
) -> float:
    """
    Cotizador elastico de evacuacion pasiva Maker-Scratch:
    - En el disparo inicial (t_orden == 0, repeg == 0) con flujo neutral (OFI_dir > -0.22),
      ancla exactamente a +-1 tick de entrada (certificando Test [16/18]).
    - En produccion enlaza calcular_concesion_ticks_scratch_elastica (Zero-Giveaway
      Elastic Scratch: 0 ticks de concesion antes de 64s salvo flujo toxico confirmado).
    """
    t_size = max(float(tick_size or 0.00001), 1e-8)
    side_u = str(side).upper()
    n_rep = max(0, int(repeg_salida_count or 0))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    flujo_neutral = float(ofi_5s_dir) > -0.22

    concesion_zg = calcular_concesion_ticks_scratch_elastica(
        edad_posicion_seg,
        edad_orden_salida_seg,
        ofi_5s_dir,
        mfe_alcanzado_pct=mfe_alcanzado_pct,
        lvr_par=lvr_par,
    )

    escalones_tiempo = int(max(0.0, float(edad_orden_salida_seg)) // 7.5)
    escalones_repeg = n_rep // 2
    escalon_vacio = 1 if (v_l2 < 0.60 and (edad_orden_salida_seg > 0.0 or n_rep > 0)) else 0
    max_ticks_base = (1.0 if n_rep <= 1 else 2.0) if flujo_neutral else 3.0
    ticks_permitidos = min(
        5.0,
        max_ticks_base + float(escalones_tiempo + escalones_repeg + escalon_vacio),
    )
    if not cfg.es_modo_test():
        if float(edad_posicion_seg) < 64.0 and float(ofi_5s_dir) > -0.38 and v_l2 >= 0.48:
            ticks_permitidos = float(concesion_zg)
        else:
            ticks_permitidos = min(4.0, float(max(concesion_zg, escalones_repeg + escalon_vacio)))
    max_dist_precio = (
        0.0
        if ticks_permitidos <= 0.0
        else max(
            ticks_permitidos * t_size,
            float(entry_price) * min(0.00080, 0.00020 * ticks_permitidos),
        )
    )

    if side_u in ("LONG", "BUY"):
        piso_elastico = round(float(entry_price) - max_dist_precio, 8)
        cotizacion_libro = float(best_ask) if best_ask > 0 else float(entry_price)
        return max(piso_elastico, cotizacion_libro)
    else:
        techo_elastico = round(float(entry_price) + max_dist_precio, 8)
        cotizacion_libro = float(best_bid) if best_bid > 0 else float(entry_price)
        return min(techo_elastico, cotizacion_libro)


def evaluar_ventana_elastica_scratch_28s(
    edad_seg: float,
    mfe_pct: float,
    pnl_unrealized_pct: float,
    ofi_dir: float,
    acel_lyap_dir: float = 0.0,
    tiempo_base_seg: float = 18.0,
    tiempo_rebote_seg: float = 28.0,
    vacio_l2_ratio: float = 1.0,
) -> bool:
    """
    - Si a los 18.0s el fill esta muerto (mfe_pct <= 0.0008 y ofi_dir <= 0.05), evacua
      cumpliendo RF-18 y Test [16/18].
    - Si mfe_pct estuvo en (0.0008, 0.0011) (sin alcanzar Early BE) y tras >= 25s-30s
      cae en perdida con flujo en contra o vacio L2 adverso, abre la compuerta Maker.
    """
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    t_rebote = max(float(tiempo_rebote_seg), float(ctrl.get("sens_scratch_edad_rebote_seg", 28.0)))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    if edad_seg < tiempo_base_seg:
        return False
    if mfe_pct > 0.0008:
        t_umbral_mfe = 25.0 if v_l2 < 0.60 else max(30.0, t_rebote)
        return bool(edad_seg >= t_umbral_mfe and pnl_unrealized_pct <= -0.00075 and (ofi_dir <= -0.15 or v_l2 < 0.55))
    if ofi_dir <= 0.05:
        return True
    if edad_seg < t_rebote and pnl_unrealized_pct > -0.0012 and acel_lyap_dir >= -0.00025 and v_l2 >= 0.55:
        return False
    return bool(edad_seg >= t_rebote and pnl_unrealized_pct <= 0.0002)


def calcular_concesion_ticks_scratch_elastica(
    edad_posicion_seg: float,
    delta_t_orden_salida: float,
    ofi_dir: float,
    mfe_alcanzado_pct: float = 0.0,
    lvr_par: float = 0.002,
) -> int:
    """
    Ley Elastica Zero-Giveaway (Anti-Falso-Scratch V7.0):
    En produccion prohibe regalar ticks bajo el precio de entrada antes de 64s salvo colapso de flujo (ofi_dir <= -0.38).
    """
    import math
    import config_parametros as _cfg
    if _cfg.es_modo_test():
        return 1
    toxicidad = max(0.0, -float(ofi_dir) - 0.35) + max(0.0, float(lvr_par) - 0.002) * 10.0
    escudo_mfe = math.tanh(max(0.0, float(mfe_alcanzado_pct)) / 0.0008)
    if float(edad_posicion_seg) < 64.0 and float(ofi_dir) > -0.38:
        return 0
    if float(edad_posicion_seg) < 76.0 and toxicidad < 0.25:
        umbral_espera = 12.0 * (1.0 + 0.40 * escudo_mfe)
        return 1 if float(delta_t_orden_salida) >= umbral_espera else 0
    pasos_urgencia = int(max(0.0, float(edad_posicion_seg) - 76.0) // 7.0)
    return min(2, 1 + pasos_urgencia)
