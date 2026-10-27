# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #1: Supervivencia en Cola L1 y Re-Peg Maker (Moallemi-Stoikov).
Resuelve la Paradoja de Seleccion Adversa en Cola: cuando el soporte Q_L1 se mantiene
firme o crece (q_l1_now >= q_l1_init * 0.55) y Hurst <= 0.490, no aborta la orden por
un parpadeo de 1 tick de OFI causado por el vendedor que nos va a llenar en el piso.
"""
from typing import Tuple
import config_parametros as cfg
import core_estado_ram as ram


def evaluar_aborto_cola_moallemi(
    direccion: str,
    q_l1_init: float,
    q_l1_now: float,
    ofi_profundo: float,
    hurst_actual: float,
    elapsed_seg: float,
    veto_btc_activo: bool,
) -> Tuple[bool, bool]:
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    umbral_ofi_abort = abs(float(ctrl.get("sens_ofi_abort_cola", -0.35)))
    ratio_soporte_firme = float(ctrl.get("sens_q_l1_hold_ratio", 0.55))

    ratio_q = (q_l1_now / q_l1_init) if q_l1_init > 0.0 else 1.0
    erosion_adversa = (
        q_l1_init > 0.0
        and q_l1_now > 0.0
        and ratio_q < 0.16
        and (
            (direccion == "LONG" and ofi_profundo <= -0.15)
            or (direccion == "SHORT" and ofi_profundo >= 0.15)
        )
    )

    flujo_a_favor_fuerte = (
        (direccion == "LONG" and ofi_profundo >= 0.12)
        or (direccion == "SHORT" and ofi_profundo <= -0.12)
    )
    # Si Q_L1 crecio o se mantiene firme (>= 55% de la liquidez inicial), exigir H > 0.52 para abortar por Hurst
    tope_h_cola = 0.525 if ratio_q >= ratio_soporte_firme else cfg.HURST_TECHO_DURO_ABSOLUTO
    hurst_toxico = (hurst_actual > tope_h_cola) and (not flujo_a_favor_fuerte)

    # Si la muralla de liquidez Q_L1 sigue intacta (>= 55%) y H <= 0.490, un tick de OFI negativo
    # es absorcion pasiva normal; solo abortar por OFI si la cola tambien se debilita o OFI es extremo.
    soporte_intacto_en_rango = (ratio_q >= ratio_soporte_firme) and (hurst_actual <= 0.490)
    if soporte_intacto_en_rango:
        ofi_contra_fuerte = (
            elapsed_seg >= 1.45
            and (
                (direccion == "LONG" and ofi_profundo <= -0.92)
                or (direccion == "SHORT" and ofi_profundo >= 0.92)
            )
        )
    else:
        ofi_contra_fuerte = (
            (direccion == "LONG" and ofi_profundo <= -umbral_ofi_abort)
            or (direccion == "SHORT" and ofi_profundo >= umbral_ofi_abort)
        )

    cola_toxica = erosion_adversa or (
        elapsed_seg >= cfg.EARLY_QUEUE_ABORT_SEG
        and (hurst_toxico or veto_btc_activo or ofi_contra_fuerte)
    )
    return bool(cola_toxica), bool(erosion_adversa)


def listo_para_repeg_cola(
    fue_cancelada_postonly: bool,
    elapsed_seg: float,
    ultimo_repeg_elapsed: float,
) -> bool:
    if fue_cancelada_postonly:
        return True
    intervalo_min = max(0.35, float(getattr(cfg, "REPEG_PASIVO_ENTRADA_SEG", 0.65)) * 0.60)
    return bool(elapsed_seg >= 0.30 and (elapsed_seg - ultimo_repeg_elapsed) >= intervalo_min)
