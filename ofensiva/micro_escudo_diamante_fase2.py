# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #9: Motor [DIAMOND] Phase 2 Maker Shield PostOnly
con Proyeccion en Cresta para Impulsos Fuertes (Lambda >= 2.80) y Cosecha en
Desaceleracion (Remediacion Trades #3, #6 y #7).
"""
from typing import Tuple
import config_parametros as cfg
from ofensiva import micro_cotizador_stoikov as mcs


def evaluar_activacion_escudo_diamante_fase2(
    direccion: str,
    precio_entrada: float,
    precio_actual: float,
    best_bid: float,
    best_ask: float,
    edad_seg: float,
    pnl_pct: float,
    lambda_wald: float,
    tick_size: float,
    fase2_ya_ejecutada: bool = False,
) -> Tuple[bool, float]:
    """
    Gobierna el [DIAMOND] Phase 2 Maker Shield PostOnly:
    1. Si el impulso Wald sigue acelerando con fuerza (lambda_wald >= 2.80) y
       pnl_pct < +0.175%, NO ahoga el trade en best_ask (+0.14%): proyecta la
       orden PostOnly en la cresta (+0.185% desde entrada o >= 2 ticks a favor).
    2. Cuando el trade ya alcanzo >= +0.140% tras >= 20s y el impulso empieza
       a moderarse (0.60 <= lambda_wald < 2.80) o ya supero +0.175%, cotiza en
       la punta Maker para cobrar en la cresta antes del retroceso.
    """
    if fase2_ya_ejecutada or edad_seg < 18.0 or precio_entrada <= 0.0:
        return False, 0.0

    if pnl_pct < 0.00135 or lambda_wald < 0.60:
        return False, 0.0

    t_sz = max(1e-8, float(tick_size))
    es_long = str(direccion).upper() in ("BUY", "LONG")
    impulso_fuerte_en_curso = (lambda_wald >= 2.80) and (pnl_pct < 0.00175) and (edad_seg < 38.0)

    if es_long:
        if impulso_fuerte_en_curso:
            px_cresta = precio_entrada * (1.0 + 0.00185)
            px_obj = mcs.cuantizar_tick(max(best_ask + t_sz, precio_actual + (2.0 * t_sz), px_cresta), t_sz, modo="ceil")
        else:
            px_obj = mcs.cuantizar_tick(max(best_ask, precio_actual + t_sz), t_sz, modo="ceil")
        if px_obj <= precio_entrada:
            return False, 0.0
        return True, px_obj
    else:
        if impulso_fuerte_en_curso:
            px_cresta = precio_entrada * (1.0 - 0.00185)
            px_obj = mcs.cuantizar_tick(min(best_bid - t_sz, precio_actual - (2.0 * t_sz), px_cresta), t_sz, modo="floor")
        else:
            px_obj = mcs.cuantizar_tick(min(best_bid, precio_actual - t_sz), t_sz, modo="floor")
        if px_obj >= precio_entrada:
            return False, 0.0
        return True, px_obj


def calcular_intervalo_repeg_salida_maker(motivo: str) -> float:
    m_up = str(motivo).upper()
    if "UNWIND" in m_up or "HARVEST" in m_up or "TRAILING" in m_up or "WALD" in m_up:
        return float(cfg.COSECHA_REPEG_INTERVALO_SEG)
    return 1.80

# === [TERPSICHORA-BE-RATCHET-ENFORCER-V1] ===
def verificar_disparo_fisico_trinquete_be(
    side: str,
    trinquete_be_armado: bool,
    sl_actual: float,
    entry_price: float,
    current_price: float,
    be_offset_pct: float = 0.00065,
) -> tuple[bool, float]:
    """
    Garantiza fisicamente que una vez armado el Early Break-Even Ratchet
    (ej. SL 0.03442 en Trade #5 WAL SHORT), si el precio regresa y toca
    el nivel ratcheteado, se dispare la evacuacion inmediata cancelando
    cualquier orden Phase 2 Maker Shield colgada.
    """
    if not trinquete_be_armado or current_price <= 0.0 or entry_price <= 0.0:
        return False, float(sl_actual)
    side_u = str(side).upper()
    if side_u in ("LONG", "BUY"):
        piso_be = round(entry_price * (1.0 + be_offset_pct), 8)
        sl_efectivo = max(float(sl_actual), piso_be) if sl_actual > 0 else piso_be
        return bool(current_price <= sl_efectivo), sl_efectivo
    else:
        techo_be = round(entry_price * (1.0 - be_offset_pct), 8)
        sl_efectivo = min(float(sl_actual), techo_be) if sl_actual > 0 else techo_be
        return bool(current_price >= sl_efectivo), sl_efectivo
