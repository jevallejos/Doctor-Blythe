# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #10: Retenedor y Completador de Llenados Parciales en Cola
PostOnly (Solucion al llenado parcial de 180/540 contratos del Trade #7).
"""
from typing import Tuple
import config_parametros as cfg


def evaluar_extension_fill_parcial_en_cola(
    direccion: str,
    contratos_solicitados: float,
    contratos_llenados: float,
    ofi_actual: float,
    hurst_actual: float,
    edad_orden_seg: float,
    ttl_base_seg: float,
) -> Tuple[bool, float]:
    """
    Si una orden PostOnly ya se lleno parcialmente (0 < filled < solicitados)
    y el flujo OFI sigue empujando a nuestro favor con Hurst antipersistente,
    otorga hasta +0.85s adicionales de retencion para completar el lote Kelly.
    Retorna (retener_en_cola: bool, ttl_efectivo_seg: float).
    """
    if contratos_llenados <= 0.0 or contratos_llenados >= contratos_solicitados:
        return False, ttl_base_seg

    if hurst_actual > 0.485:
        return False, ttl_base_seg

    flujo_fuerte = (
        (direccion == "LONG" and ofi_actual >= 0.35)
        or (direccion == "SHORT" and ofi_actual <= -0.35)
    )
    if flujo_fuerte:
        ttl_ext = ttl_base_seg + 0.85
        return bool(edad_orden_seg < ttl_ext), ttl_ext

    return False, ttl_base_seg


def validar_lote_ejecutado_suficiente(
    contratos_solicitados: float,
    contratos_llenados: float,
) -> bool:
    if contratos_llenados <= 0.0:
        return False
    frac_min = float(getattr(cfg, "FRACCION_MINIMA_FILL_LOTE", 0.15))
    if contratos_solicitados <= 0.0:
        return True
    return bool((contratos_llenados / contratos_solicitados) >= min(0.05, frac_min))
