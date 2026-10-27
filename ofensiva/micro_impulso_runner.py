# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #8: Detector de Climax de Giro Extremo, Protector de
Semillas Ganadoras (MFE >= +0.045%) y Evacuacion Anti-SL por Scratch Estancado.
Basado en la evidencia empirica de baul_ia_forense_2.jsonl y bot_hft_2.log.
"""
import core_estado_ram as ram


def evaluar_override_climax_hurst(
    z_score: float,
    hurst_actual: float,
    ofi_actual: float,
    aceleracion_lyapunov: float,
    hurst_cap_base: float = 0.485,
) -> bool:
    """
    Permite relajar ligeramente hurst_cap_base (0.485) SOLO hasta un techo duro
    de 0.515 cuando existe agotamiento de climax extremo, bloqueando siempre
    cualquier entrada contra tendencia persistente (H > 0.515, Caso WAL Trade #8).
    """
    if hurst_actual <= hurst_cap_base:
        return True
    if hurst_actual > 0.515:
        return False
    return bool(z_score >= 5.20 and ofi_actual <= -0.80 and aceleracion_lyapunov <= -0.00050)


def proteger_semilla_ganadora_de_scratch(
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    direccion: str,
) -> bool:
    """
    Solucion al Caso Trade #5 (ZEREBRO LONG @ 0.03082 que subio a MFE +0.0811% a los 18s
    y fue cerrado en scratch a los 24s al tocar 0.00%):
    Si la posicion ya demostro rebote real (MFE >= +0.045%, ~1.5-2 ticks a favor),
    no permite que MAKER_SCRATCH_18S la cierre antes de los 32s mientras la perdida
    flotante sea menor a -0.075%.
    """
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
    """
    Solucion al Caso Trade #6 (ZEREBRO LONG que activo MAKER_SCRATCH_18S a los 18.1s
    pero paso 40s persiguiendo el Ask sin llenarse hasta tocar SL_INTERNO_CHRONOS -0.59%):
    Si llevamos >= 11.0s intentando evacuar por MAKER_SCRATCH_18S sin lograr fill pasivo
    y el precio ya cayo por debajo de -0.23% con flujo en contra, fuerza salida inmediata
    ahorrando mas de la mitad del Stop-Loss.
    """
    if not en_proceso_cierre or "SCRATCH" not in str(motivo_pendiente).upper():
        return False
    if edad_orden_salida_seg < 11.0:
        return False
    flujo_adverso = (
        (direccion == "LONG" and ofi_5s <= -0.20)
        or (direccion == "SHORT" and ofi_5s >= 0.20)
    )
    return bool(pnl_pct <= -0.0023 and flujo_adverso)
