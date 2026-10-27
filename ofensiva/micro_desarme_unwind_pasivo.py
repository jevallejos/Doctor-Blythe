# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #11: Gobernador de Cosecha por Estancamiento (MFE Stall)
y Desarme Pasivo en Ganancia a los 42.0s ([MAKER_UNWIND]).
"""
import config_parametros as cfg
import core_estado_ram as ram
from ofensiva import micro_motor_wald_exit as mmw


def evaluar_cosecha_estancamiento_mfe(
    direccion: str,
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    piso_ganancia_neta_pct: float = 0.00065,
) -> bool:
    """
    Si tras 16.0s la operacion ya alcanzo el umbral mfe_stall_harvest_pct
    y sigue en ganancia neta pero el flujo OFI perdio traccion, autoriza
    cobrar como Maker antes de que el precio regrese a la entrada.
    """
    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    umbral_stall = float(ctrl.get("mfe_stall_harvest_pct", cfg.COSECHA_ESTANCAMIENTO_MFE_PCT))
    if edad_seg < 16.0 or mfe_pct < umbral_stall or pnl_pct < piso_ganancia_neta_pct:
        return False

    flujo_agotado = (
        (direccion == "LONG" and ofi_5s <= 0.05)
        or (direccion == "SHORT" and ofi_5s >= -0.05)
    )
    return bool(flujo_agotado)


def evaluar_desarme_maker_unwind_42s(
    direccion: str,
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    cosecha_activa: bool = False,
) -> bool:
    """
    Gobierna la activacion de [MAKER_UNWIND] al cumplirse w4_unwind_seg (42.0s),
    inhibiendo el cierre si la posicion va acelerando en rally cerca de su MFE.
    """
    if cosecha_activa or pnl_pct <= 0.00050:
        return False

    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    unwind_seg = float(ctrl.get("w4_unwind_seg", 42.0))
    if edad_seg < unwind_seg:
        return False

    if mmw.debe_inhibir_maker_unwind_en_rally(direccion, pnl_pct, mfe_pct, ofi_5s):
        return False

    return True
