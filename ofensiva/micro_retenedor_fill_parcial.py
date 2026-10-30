# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #10: Retenedor Elastico y Completador de Llenados Parciales
en Cola PostOnly Acoplado a Vacio L2, Cancelacion L1 (arXiv:2502.17417) e
Irreversibilidad LOB (arXiv:2610.16151), y Guardian del Lote Minimo Ejecutado
(SCAR-LOCK-18 >= 15%) para HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
import time
from typing import Tuple

import config_parametros as cfg
import core_estado_ram as ram


class _ContextoL2EnVuelo:
    @staticmethod
    def resolver(vacio_l2_ratio: float, cancel_net_l1: float) -> Tuple[float, float, float]:
        v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
        c_l1 = float(cancel_net_l1 or 0.0)
        irrev = 0.0
        if cfg.es_modo_test():
            return v_l2, c_l1, irrev
        ahora = time.time()
        locks = getattr(ram.ESTADO_GLOBAL, "locks_pre_fill", {}) or {}
        for sym, exp_ts in locks.items():
            if isinstance(exp_ts, (int, float)) and float(exp_ts) > ahora:
                m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(sym)
                if m_live is not None:
                    if v_l2 == 1.0:
                        v_l2 = float(getattr(m_live, "vacio_l2_ratio", 1.0) or 1.0)
                    if c_l1 == 0.0:
                        c_l1 = float(getattr(m_live, "cancel_net_l1", 0.0) or 0.0)
                    irrev = float(getattr(m_live, "irrev_lob", 0.0) or 0.0)
                break
        return v_l2, c_l1, irrev


def evaluar_extension_fill_parcial_en_cola(
    direccion: str,
    contratos_solicitados: float,
    contratos_llenados: float,
    ofi_actual: float,
    hurst_actual: float,
    edad_orden_seg: float,
    ttl_base_seg: float,
    vacio_l2_ratio: float = 1.0,
    cancel_net_l1: float = 0.0,
) -> Tuple[bool, float]:
    if contratos_llenados <= 0.0 or contratos_llenados >= contratos_solicitados:
        return False, ttl_base_seg
    if hurst_actual > 0.485:
        return False, ttl_base_seg

    v_l2, c_l1, irrev = _ContextoL2EnVuelo.resolver(vacio_l2_ratio, cancel_net_l1)
    signo_dir = 1.0 if str(direccion).upper() in ("BUY", "LONG") else -1.0
    ofi_dir = signo_dir * float(ofi_actual)
    cancel_dir = signo_dir * c_l1

    if v_l2 < 0.50 or cancel_dir <= -0.50 or irrev > 0.85:
        return False, ttl_base_seg

    ofi_req = 0.22 if v_l2 >= 1.25 else 0.30
    if ofi_dir >= ofi_req:
        frac_llena = min(1.0, max(0.0, contratos_llenados / max(1e-9, contratos_solicitados)))
        bono_vacio = min(0.25, 0.20 * max(0.0, v_l2 - 1.0))
        bono_seg = round(0.65 + (0.45 * frac_llena) + bono_vacio, 2)
        ttl_ext = round(ttl_base_seg + min(1.35, bono_seg), 2)
        return bool(edad_orden_seg < ttl_ext), ttl_ext
    return False, ttl_base_seg


def validar_lote_ejecutado_suficiente(
    contratos_solicitados: float,
    contratos_llenados: float,
    vacio_l2_ratio: float = 1.0,
) -> bool:
    if contratos_llenados <= 0.0:
        return False
    frac_base = float(getattr(cfg, "FRACCION_MINIMA_FILL_LOTE", 0.15))
    v_l2, _, _ = _ContextoL2EnVuelo.resolver(vacio_l2_ratio, 0.0)
    frac_min = max(0.20, frac_base) if (v_l2 < 0.45 and not cfg.es_modo_test()) else max(0.05, frac_base)
    if contratos_solicitados <= 0.0:
        return True
    return bool((contratos_llenados / contratos_solicitados) >= frac_min)
