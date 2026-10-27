# -*- coding: utf-8 -*-
"""
Micro-Modulo Independiente de Veto Macro Lead-Lag de BTC (P-01_BTC_VETO).
Mantiene intacto el escudo contra cascadas de BTC y el cooldown de 12s, pero
permite liberar el enfriamiento residual cuando BTC y la altcoin ya giraron
simultaneamente con absorcion fuerte a favor del tiro (Solucion a los
FALSE_REJECTION_OPPORTUNITY_LOST de baul_ia_forense_3.jsonl).
"""
from typing import Tuple
import config_parametros as cfg


def evaluar_choque_directo_btc(
    direccion: str,
    z_btc: float,
    ofi_btc: float,
    umbral_ofi_veto: float = 0.40,
    umbral_z_veto: float = 0.25,
) -> Tuple[bool, str]:
    """
    Evalua si el lider macro (BTC/USDT:USDT) esta empujando activamente en contra
    de la direccion del disparo en este milisegundo.
    Retorna (bloqueado: bool, motivo: str).
    """
    if direccion == "LONG":
        if ofi_btc <= -abs(umbral_ofi_veto) and z_btc <= 0.05:
            return True, f"BTC_VETO_LONG(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if z_btc <= -abs(umbral_z_veto) and ofi_btc < 0.0:
            return True, f"BTC_VETO_LONG(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
    else:
        if ofi_btc >= abs(umbral_ofi_veto) and z_btc >= -0.05:
            return True, f"BTC_VETO_SHORT(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if z_btc >= abs(umbral_z_veto) and ofi_btc > 0.0:
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
    Evalua si el enfriamiento residual de 12s (BTC_VETO_COOLDOWN_12S) puede levantarse
    anticipadamente porque BTC ya absorbio la caida y giro a favor junto con la altcoin:
    - Exige que hayan transcurrido al menos 3.0s del evento inicial.
    - Exige que BTC tenga Z y OFI claramente a favor (>= +0.25 OFI en LONG).
    - Exige que la altcoin tenga frenado Lyapunov positivo, Hurst < 0.45 y OFI >= +0.35.
    """
    tiempo_transcurrido = max(0.0, cooldown_total_seg - segundos_restantes_cooldown)
    if tiempo_transcurrido < 3.0:
        return False

    if hurst_alt > 0.45:
        return False

    if direccion == "LONG":
        btc_recuperado = (z_btc >= 0.0) and (ofi_btc >= 0.25)
        alt_en_rebote_limpio = (ofi_alt >= 0.35) and (lyapunov_alt > 0.00005)
        return bool(btc_recuperado and alt_en_rebote_limpio)
    else:
        btc_girado_abajo = (z_btc <= 0.0) and (ofi_btc <= -0.25)
        alt_en_caida_limpia = (ofi_alt <= -0.35) and (lyapunov_alt < -0.00005)
        return bool(btc_girado_abajo and alt_en_caida_limpia)
