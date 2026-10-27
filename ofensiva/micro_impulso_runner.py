# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #8: Detector de Climax de Giro Extremo (con Tope Duro H <= 0.515
y Filtro de Irreversibilidad LOB arXiv:2610.16151), Protector de Semillas Ganadoras
(MFE >= +0.045%) y Evacuacion Anti-SL por Scratch Estancado.
"""
import core_estado_ram as ram
from defensiva import micro_candado_climax_hurst as mcch


def evaluar_override_climax_hurst(
    direccion: str,
    z_score: float,
    ofi_actual: float,
    hawkes_actual: float,
    aceleracion_lyapunov: float,
    hurst_actual: float,
    hurst_cap_base: float = 0.485,
    irreversibilidad_lob: float = 0.0,
) -> bool:
    if hurst_actual <= hurst_cap_base:
        return True
    if hurst_actual > 0.515 or irreversibilidad_lob > 0.88:
        return False

    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    if dir_norm == "SHORT":
        ok_s, _, _ = mcch.evaluar_tope_duro_climax_hurst(
            z_score=float(z_score),
            hurst_actual=float(hurst_actual),
            ofi_actual=float(ofi_actual),
            aceleracion_lyapunov=float(aceleracion_lyapunov),
            hurst_cap_base=hurst_cap_base,
            techo_duro_absoluto=0.515,
            irreversibilidad_lob=float(irreversibilidad_lob),
        )
        return bool(ok_s and hawkes_actual <= -0.35)

    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    if float(ctrl.get("sens_climax_hurst_override", 1.0)) < 0.5:
        return False
    return bool(
        z_score <= -4.20
        and ofi_actual >= 0.75
        and hawkes_actual >= 0.50
        and aceleracion_lyapunov >= 0.0
    )


def proteger_semilla_ganadora_de_scratch(
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    direccion: str,
) -> bool:
    if mfe_pct < 0.00045:
        return False
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    edad_proteccion = float(ctrl.get("sens_scratch_edad_rebote_seg", 32.0))
    if edad_seg < edad_proteccion and pnl_pct >= -0.00075:
        return True
    flujo_no_colapsado = (
        (direccion == "LONG" and ofi_5s > -0.35)
        or (direccion == "SHORT" and ofi_5s < 0.35)
    )
    if edad_seg < 40.0 and pnl_pct >= -0.00045 and flujo_no_colapsado:
        return True
    return False


def debe_forzar_evacuacion_scratch_estancado(
    en_proceso_cierre: bool,
    motivo_pendiente: str,
    edad_orden_salida_seg: float,
    pnl_pct: float,
    ofi_5s: float,
    direccion: str,
) -> bool:
    if not en_proceso_cierre or "SCRATCH" not in str(motivo_pendiente).upper():
        return False
    if edad_orden_salida_seg < 11.0:
        return False
    flujo_adverso = (
        (direccion == "LONG" and ofi_5s <= -0.20)
        or (direccion == "SHORT" and ofi_5s >= 0.20)
    )
    return bool(pnl_pct <= -0.0023 and flujo_adverso)
