# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #10: Retenedor y Completador de Llenados Parciales en Cola PostOnly
y Guardian del Lote Minimo Ejecutado (SCAR-LOCK-18 >= 15%).
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
    otorga entre +0.60s y +1.10s adicionales de retencion segun la fraccion llenada.
    """
    if contratos_llenados <= 0.0 or contratos_llenados >= contratos_solicitados:
        return False, ttl_base_seg
    if hurst_actual > 0.485:
        return False, ttl_base_seg
    signo_dir = 1.0 if str(direccion).upper() in ("BUY", "LONG") else -1.0
    ofi_dir = signo_dir * float(ofi_actual)
    if ofi_dir >= 0.30:
        frac_llena = min(1.0, max(0.0, contratos_llenados / max(1e-9, contratos_solicitados)))
        bono_seg = round(0.65 + (0.45 * frac_llena), 2)
        ttl_ext = ttl_base_seg + bono_seg
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
    return bool((contratos_llenados / contratos_solicitados) >= max(0.05, frac_min))
