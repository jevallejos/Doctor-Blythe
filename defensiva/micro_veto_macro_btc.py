# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #2: Veto Macro Lead-Lag de BTC (P-01_BTC_VETO),
Disyuntor de Colapso BTC (Z <= -4.0) y Liberacion Sincronizada de Cooldown 12s.
"""
from typing import Tuple
import config_parametros as cfg
import core_estado_ram as ram


def evaluar_choque_directo_btc(
    direccion: str,
    z_btc: float,
    ofi_btc: float,
    umbral_ofi_veto: float = 0.40,
    umbral_z_veto: float = 0.25,
) -> Tuple[bool, str]:
    """
    Evalua si el lider macro (BTC/USDT:USDT) esta empujando activamente en contra
    de la direccion del disparo. Exige movimiento real de precio (|z_btc| >= 0.15)
    para que un pulso de OFI dispare el veto, evitando falsos bloqueos cuando BTC
    esta plano (Z = 0.00).
    """
    if direccion == "LONG":
        if z_btc <= -1.45:
            return True, f"BTC_VETO_LONG(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if ofi_btc <= -abs(umbral_ofi_veto) and z_btc <= -0.15:
            return True, f"BTC_VETO_LONG(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if z_btc <= -abs(umbral_z_veto) and ofi_btc <= -0.15:
            return True, f"BTC_VETO_LONG(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
    else:
        if z_btc >= 1.45:
            return True, f"BTC_VETO_SHORT(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if ofi_btc >= abs(umbral_ofi_veto) and z_btc >= 0.15:
            return True, f"BTC_VETO_SHORT(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if z_btc >= abs(umbral_z_veto) and ofi_btc >= 0.15:
            return True, f"BTC_VETO_SHORT(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
    return False, "OK"


def puede_liberar_cooldown_btc_en_giro_sincronizado(
    direccion: str,
    segundos_restantes_cooldown: float,
    z_btc: float,
    ofi_btc: float,
    ofi_alt: float,
    hurst_alt: float,
    lyapunov_alt: float,
    cooldown_total_seg: float = 12.0,
) -> bool:
    """
    Libera anticipadamente la cola residual de BTC_VETO_COOLDOWN_12S cuando:
    1. Han transcurrido al menos 1.5s desde el pulso de choque inicial de BTC.
    2. BTC ya detuvo la caida (z_btc >= -0.08 y ofi_btc >= -0.05 en LONG).
    3. La altcoin presenta absorcion compradora (OFI >= +0.25) y frenado de Lyapunov.
    """
    tiempo_transcurrido = max(0.0, cooldown_total_seg - segundos_restantes_cooldown)
    if tiempo_transcurrido < 1.5:
        return False

    if hurst_alt > 0.62:
        return False

    if direccion == "LONG":
        btc_estabilizado = (z_btc >= -0.08) and (ofi_btc >= -0.05)
        alt_absorbiendo_piso = (ofi_alt >= 0.25) and (lyapunov_alt >= -0.00035)
        return bool(btc_estabilizado and alt_absorbiendo_piso)
    else:
        if hurst_alt > 0.485:
            return False
        btc_estabilizado_short = (z_btc <= 0.08) and (ofi_btc <= 0.05)
        alt_absorbiendo_techo = (ofi_alt <= -0.25) and (lyapunov_alt <= 0.00035)
        return bool(btc_estabilizado_short and alt_absorbiendo_techo)


def verificar_veto_macro_btc_completo(direccion: str, ahora: float) -> Tuple[bool, str]:
    m_btc = ram.ESTADO_GLOBAL.metricas_ticks.get(cfg.PAR_LIDER_MACRO)
    if m_btc is None or m_btc.mid <= 0.0:
        return True, "OK"
    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    umbral_ofi_btc = float(ctrl.get("w2_btc_beta", cfg.BTC_VETO_OFI_UMBRAL))
    if m_btc.z_score <= -4.0:
        ram.ESTADO_GLOBAL.pausa_macro_hasta = max(
            ram.ESTADO_GLOBAL.pausa_macro_hasta,
            ahora + cfg.PAUSA_MACRO_CONTAGIO_SEG,
        )
        ram.log_operativo(
            f"[CIRCUIT BREAKER BTC] {cfg.PAR_LIDER_MACRO} collapsing "
            f"(Z={m_btc.z_score:+.2f} <= -4.0)! Activating macro shield (30s)..."
        )
        return False, "CIRCUIT_BREAKER_BTC"
    if direccion == "LONG":
        caida_btc = (
            (m_btc.ofi_profundo <= -umbral_ofi_btc and m_btc.z_score <= -0.25)
            or (m_btc.z_score <= cfg.BTC_VETO_Z_UMBRAL_CAIDA)
            or (m_btc.ofi_profundo <= -0.25 and m_btc.z_score <= -0.50)
        )
        if caida_btc:
            ram.ESTADO_GLOBAL.btc_veto_long_hasta = max(
                ram.ESTADO_GLOBAL.btc_veto_long_hasta,
                ahora + cfg.BTC_VETO_COOLDOWN_SEG,
            )
            return False, f"BTC_VETO_LONG(OFI={m_btc.ofi_profundo:+.2f},Z={m_btc.z_score:+.2f})"
        if ahora < ram.ESTADO_GLOBAL.btc_veto_long_hasta:
            return False, "BTC_VETO_COOLDOWN_12S"
    else:
        subida_btc = (
            (m_btc.ofi_profundo >= umbral_ofi_btc and m_btc.z_score >= 0.25)
            or (m_btc.z_score >= cfg.BTC_VETO_Z_UMBRAL_SUBIDA)
            or (m_btc.ofi_profundo >= 0.25 and m_btc.z_score >= 0.50)
        )
        if subida_btc:
            ram.ESTADO_GLOBAL.btc_veto_short_hasta = max(
                ram.ESTADO_GLOBAL.btc_veto_short_hasta,
                ahora + cfg.BTC_VETO_COOLDOWN_SEG,
            )
            return False, f"BTC_VETO_SHORT(OFI={m_btc.ofi_profundo:+.2f},Z={m_btc.z_score:+.2f})"
        if ahora < ram.ESTADO_GLOBAL.btc_veto_short_hasta:
            return False, "BTC_VETO_COOLDOWN_12S"
    return True, "OK"
