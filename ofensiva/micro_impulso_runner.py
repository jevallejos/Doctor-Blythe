# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #8: Detector de Climax de Giro Extremo (con Tope Duro H <= 0.515
y Filtro Simetrico de Irreversibilidad LOB arXiv:2610.16151), Protector Elastico de
Semillas Ganadoras (MFE >= +0.045% con Vacio L2 y Pendiente DeLise) y Evacuacion
Anti-SL por Scratch Estancado para HFT Doctor Blythe Terpsichora V7.0.
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
    cancel_net_l1: float = 0.0,
) -> bool:
    if hurst_actual <= hurst_cap_base:
        return True
    irrev = float(irreversibilidad_lob or 0.0)
    if hurst_actual > 0.515 or irrev > 0.88:
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
            irreversibilidad_lob=irrev,
            cancel_net_l1=float(cancel_net_l1 or 0.0),
        )
        return bool(ok_s and hawkes_actual <= -0.35)

    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    if float(ctrl.get("sens_climax_hurst_override", 1.0)) < 0.5:
        return False
    ofi_req_long = 0.75 + (0.15 * max(0.0, irrev - 0.50))
    return bool(
        z_score <= -4.20
        and ofi_actual >= ofi_req_long
        and hawkes_actual >= 0.50
        and aceleracion_lyapunov >= 0.0
    )


def proteger_semilla_ganadora_de_scratch(
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    direccion: str,
    vacio_l2_ratio: float = 1.0,
    pendiente_delise: float = 0.0,
) -> bool:
    if mfe_pct < 0.00045:
        return False
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    if v_l2 < 0.45 and pnl_pct <= -0.00060:
        return False

    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    edad_base = float(ctrl.get("sens_scratch_edad_rebote_seg", 32.0))
    bono_delise = 4.0 if (float(pendiente_delise or 0.0) >= 0.000020 or v_l2 >= 1.25) else 0.0
    edad_proteccion = min(44.0, edad_base + bono_delise)

    if edad_seg < edad_proteccion and pnl_pct >= -0.00075:
        return True
    flujo_no_colapsado = (
        (str(direccion).upper() in ("BUY", "LONG") and ofi_5s > -0.35)
        or (str(direccion).upper() in ("SELL", "SHORT") and ofi_5s < 0.35)
    )
    if edad_seg < min(44.0, edad_proteccion + 6.0) and pnl_pct >= -0.00045 and flujo_no_colapsado:
        return True
    return False


def debe_forzar_evacuacion_scratch_estancado(
    en_proceso_cierre: bool,
    motivo_pendiente: str,
    edad_orden_salida_seg: float,
    pnl_pct: float,
    ofi_5s: float,
    direccion: str,
    repeg_salida_count: int = 0,
    vacio_l2_ratio: float = 1.0,
    cosecha_parcial_ejecutada: bool = False,
) -> bool:
    if cosecha_parcial_ejecutada or not en_proceso_cierre or "SCRATCH" not in str(motivo_pendiente).upper():
        return False
    n_rep = max(0, int(repeg_salida_count or 0))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    edad_min_esc = 8.0 if (n_rep >= 5 and v_l2 < 0.55) else 11.0
    if edad_orden_salida_seg < edad_min_esc:
        return False
    flujo_adverso = (
        (str(direccion).upper() in ("BUY", "LONG") and ofi_5s <= -0.20)
        or (str(direccion).upper() in ("SELL", "SHORT") and ofi_5s >= 0.20)
    )
    umbral_pnl_esc = -0.0020 if (n_rep >= 5 and v_l2 < 0.55) else -0.0023
    return bool(pnl_pct <= umbral_pnl_esc and flujo_adverso)
