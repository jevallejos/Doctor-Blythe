# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #2: Veto Macro Lead-Lag de BTC (P-01_BTC_VETO) Acoplado
a w2_btc_beta Autonomo e Irreversibilidad LOB, Disyuntor de Colapso BTC (Z <= -4.0)
y Liberacion Sincronizada de Cooldown 12s con Vacio L2 (Terpsichora V7.0).
"""
from typing import Tuple
import config_parametros as cfg
import core_estado_ram as ram


def evaluar_choque_directo_btc(
    direccion: str,
    z_btc: float,
    ofi_btc: float,
    umbral_ofi_veto: float = 0.32,
    umbral_z_veto: float = 0.25,
    irrev_btc: float = 0.0,
) -> Tuple[bool, str]:
    """
    Evalua si el lider macro (BTC/USDT:USDT) esta empujando activamente en contra
    de la direccion del disparo:
    - Respeta el peso autonomo umbral_ofi_veto (w2_btc_beta) tanto en el gatillo
      primario como en el gatillo compuesto (evitando falsos rechazos cuando BTC
      oscila en ruido con baja entropia irrev_btc < 0.30).
    """
    z_caida = float(getattr(cfg, "BTC_VETO_Z_UMBRAL_CAIDA", -1.50))
    z_subida = float(getattr(cfg, "BTC_VETO_Z_UMBRAL_SUBIDA", 1.45))
    irrev = float(irrev_btc or 0.0)
    mod_irrev = -0.04 if irrev >= 0.72 else (0.03 if (0.0 < irrev < 0.30) else 0.0)
    ofi_lim = max(0.22, min(0.46, abs(float(umbral_ofi_veto)) + mod_irrev))
    ofi_comp = max(0.22, round(ofi_lim * 0.80, 4))
    z_comp = max(0.25, abs(float(umbral_z_veto)))

    if str(direccion).upper() in ("BUY", "LONG"):
        if z_btc <= z_caida and ofi_btc < ofi_lim:
            return True, f"BTC_VETO_LONG(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if ofi_btc <= -ofi_lim and z_btc <= -0.15:
            return True, f"BTC_VETO_LONG(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if z_btc <= -max(0.35, z_comp) and ofi_btc <= -ofi_comp:
            return True, f"BTC_VETO_LONG(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
    else:
        if z_btc >= z_subida and ofi_btc > -ofi_lim:
            return True, f"BTC_VETO_SHORT(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if ofi_btc >= ofi_lim and z_btc >= 0.15:
            return True, f"BTC_VETO_SHORT(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
        if z_btc >= max(0.35, z_comp) and ofi_btc >= ofi_comp:
            return True, f"BTC_VETO_SHORT(OFI={ofi_btc:+.2f},Z={z_btc:+.2f})"
    return False, "OK"


def evaluar_desbloqueo_dinamico_flujo_btc(
    z_btc: float,
    ofi_btc: float,
    dp_btc_pct: float,
    ofi_alt: float,
    hurst_alt: float,
    acel_lyap_alt: float,
    elapsed_cooldown_seg: float,
    side: str = "LONG",
    vacio_l2_alt: float = 1.0,
) -> bool:
    """
    SCAR-LOCK-17: Desbloquea anticipadamente BTC_VETO_COOLDOWN_12S tras >= 1.5s
    cuando BTC detiene su impulso adverso y el par hijo confirma absorcion L1-L5
    con soporte L2 valido (vacio_l2_alt >= 0.55).
    """
    v_l2 = float(vacio_l2_alt if vacio_l2_alt is not None else 1.0)
    if elapsed_cooldown_seg < 1.50 or hurst_alt > 0.485 or v_l2 < 0.55:
        return False
    ofi_req_alt = 0.18 if v_l2 >= 1.35 else 0.22
    side_u = str(side).upper()
    if side_u in ("LONG", "BUY"):
        btc_estable = (
            (ofi_btc >= -0.10 and z_btc >= -0.25)
            or (abs(dp_btc_pct) < 0.0003 and ofi_btc >= -0.08)
            or (ofi_btc >= max(0.32, ofi_req_alt + 0.10) and z_btc >= -3.20)
        )
        alt_absorbiendo = (ofi_alt >= ofi_req_alt and acel_lyap_alt >= -0.00022)
        return bool(btc_estable and alt_absorbiendo)
    else:
        btc_estable = (
            (ofi_btc <= 0.10 and z_btc <= 0.25)
            or (abs(dp_btc_pct) < 0.0003 and ofi_btc <= 0.08)
            or (ofi_btc <= -max(0.32, ofi_req_alt + 0.10) and z_btc <= 3.20)
        )
        alt_absorbiendo = (ofi_alt <= -ofi_req_alt and acel_lyap_alt <= 0.00022)
        return bool(btc_estable and alt_absorbiendo)


def puede_liberar_cooldown_btc_en_giro_sincronizado(
    direccion: str,
    segundos_restantes_cooldown: float,
    z_btc: float,
    ofi_btc: float,
    ofi_alt: float,
    hurst_alt: float,
    lyapunov_alt: float,
    cooldown_total_seg: float = 12.0,
    vacio_l2_alt: float = 1.0,
) -> bool:
    """
    Libera anticipadamente la cola residual de BTC_VETO_COOLDOWN_12S cuando
    han transcurrido >= 1.5s, H_alt <= 0.485, vacio_l2_alt >= 0.55 y BTC + Altcoin
    confirman giro en V sincronizado.
    """
    v_l2 = float(vacio_l2_alt if vacio_l2_alt is not None else 1.0)
    tiempo_transcurrido = max(0.0, cooldown_total_seg - segundos_restantes_cooldown)
    if tiempo_transcurrido < 1.50 or hurst_alt > 0.485 or v_l2 < 0.55:
        return False
    ofi_req_v = 0.21 if v_l2 >= 1.35 else 0.25
    if str(direccion).upper() in ("BUY", "LONG"):
        btc_estabilizado = (
            ((z_btc >= -0.08) and (ofi_btc >= -0.05))
            or (ofi_btc >= max(0.32, ofi_req_v + 0.10) and z_btc >= -3.20)
        )
        alt_absorbiendo_piso = (ofi_alt >= ofi_req_v) and (lyapunov_alt >= -0.00035)
        return bool(btc_estabilizado and alt_absorbiendo_piso)
    else:
        btc_estabilizado_short = (
            ((z_btc <= 0.08) and (ofi_btc <= 0.05))
            or (ofi_btc <= -max(0.32, ofi_req_v + 0.10) and z_btc <= 3.20)
        )
        alt_absorbiendo_techo = (ofi_alt <= -ofi_req_v) and (lyapunov_alt <= 0.00035)
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

    irrev_b = float(getattr(m_btc, "irrev_lob", 0.0) or 0.0)
    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    choque, motivo_ch = evaluar_choque_directo_btc(
        dir_norm,
        m_btc.z_score,
        m_btc.ofi_profundo,
        umbral_ofi_veto=umbral_ofi_btc,
        umbral_z_veto=0.25,
        irrev_btc=irrev_b,
    )
    extra_cd = 4.0 if (abs(m_btc.z_score) >= 2.50 and irrev_b >= 0.75 and not cfg.es_modo_test()) else 0.0
    cd_seg = float(cfg.BTC_VETO_COOLDOWN_SEG) + extra_cd
    if dir_norm == "LONG":
        if choque:
            ram.ESTADO_GLOBAL.btc_veto_long_hasta = max(
                ram.ESTADO_GLOBAL.btc_veto_long_hasta,
                ahora + cd_seg,
            )
            return False, motivo_ch
        if ahora < ram.ESTADO_GLOBAL.btc_veto_long_hasta:
            return False, "BTC_VETO_COOLDOWN_12S"
    else:
        if choque:
            ram.ESTADO_GLOBAL.btc_veto_short_hasta = max(
                ram.ESTADO_GLOBAL.btc_veto_short_hasta,
                ahora + cd_seg,
            )
            return False, motivo_ch
        if ahora < ram.ESTADO_GLOBAL.btc_veto_short_hasta:
            return False, "BTC_VETO_COOLDOWN_12S"
    return True, "OK"
