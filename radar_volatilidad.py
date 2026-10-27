"""
Level 5 DAG: 25.0 Hz L2 Microstructural Radar, Bipower Variation Z-Score Engine,
24-Hour Elastic Seasonality Curve, Immutable SCAR_BASE (SCAR-LOCK-00..18),
4.50s Puppeteer Phase-Latched Envelope, and Top-Rollover SHORT-SNIPER Capture
for HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import collections
import math
import time
from typing import Any, Deque, Dict, List, Optional, Tuple

import config_parametros as cfg
from ofensiva import micro_enganche_fase as mep
from ofensiva import micro_impulso_runner as mir
from defensiva import micro_escudos_fisicos as mef
from defensiva import micro_veto_macro_btc as mvb
from apoyo import micro_cinematica_l2 as mcl
import core_estado_ram as ram
import escudo_tricortex as tri

# ==============================================================================
# IMMUTABLE SCAR-TISSUE LEDGER (SCAR-LOCK-00 THROUGH SCAR-LOCK-18)
# ==============================================================================
SCAR_BASE: Dict[str, Dict[str, Any]] = {
    "SCAR-LOCK-00": {"regla": "PISO_VOLATILIDAD_BV", "piso": cfg.VOLATILIDAD_BV_PISO_MIN},
    "SCAR-LOCK-01": {"regla": "SPREAD_MAX_PERMITIDO", "techo": cfg.SPREAD_MAX_PERMITIDO_PCT},
    "SCAR-LOCK-02": {"regla": "VPIN_MAX_TOXICIDAD", "techo": cfg.VPIN_MAX_TOXICIDAD},
    "SCAR-LOCK-03": {"regla": "LYAPUNOV_FRENADO_MIN", "piso": cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO},
    "SCAR-LOCK-04": {"regla": "HURST_LONG_HIGH_BETA_CAP", "techo": cfg.HURST_MAX_ENTRADA_LONG},
    "SCAR-LOCK-05": {"regla": "HURST_LONG_TIER1_CAP", "techo": cfg.HURST_MAX_ENTRADA_LONG_T1},
    "SCAR-LOCK-06": {"regla": "HURST_SHORT_ABSOLUTE_CAP", "techo": cfg.HURST_TECHO_DURO_ABSOLUTO},
    "SCAR-LOCK-07": {"regla": "HAWKES_LONG_MIN_INTENSITY", "piso": cfg.HAWKES_INTENSIDAD_MIN_LONG},
    "SCAR-LOCK-08": {"regla": "HAWKES_SHORT_MAX_INTENSITY", "techo": cfg.HAWKES_INTENSIDAD_MAX_SHORT},
    "SCAR-LOCK-09": {"regla": "OFI_PERSISTENCIA_MIN_TICKS", "piso": cfg.OFI_TICKS_PERSISTENCIA_MIN},
    "SCAR-LOCK-10": {"regla": "EMA900_ANTI_PUMP_TOP_LONG", "techo": cfg.EMA900_MAX_SOBRECOMPRA_LONG},
    "SCAR-LOCK-11": {"regla": "BTC_MACRO_VETO_COOLDOWN", "piso": cfg.BTC_VETO_COOLDOWN_SEG},
    "SCAR-LOCK-12": {"regla": "IGNICION_ALCISTA_SHORT_VETO", "techo": cfg.Z_SCORE_IGNICION_SHORT_VETO},
    "SCAR-LOCK-13": {"regla": "DP_MIN_EXCURSION_HB_LONG", "techo": cfg.DP_MIN_EXCURSION_LONG_HB},
    "SCAR-LOCK-14": {"regla": "ZERO_LOSS_BE_OFFSET_MIN", "piso": cfg.TRINQUETE_BE_OFFSET_PCT},
    "SCAR-LOCK-15": {"regla": "STEP_LOCK_ANTI_SQUEEZE_SHORT", "piso": 1800.0},
    "SCAR-LOCK-16": {"regla": "RECORRIDO_MIN_EMA900_FACTOR", "piso": cfg.FACTOR_RECORRIDO_MIN_EMA900},
    "SCAR-LOCK-17": {"regla": "PHASE_LATCH_MAX_WINDOW_SEG", "techo": cfg.PHASE_LATCH_VENTANA_SEG},
    "SCAR-LOCK-18": {"regla": "MIN_FILL_LOT_FRACTION", "piso": cfg.FRACCION_MINIMA_FILL_LOTE},
}

VentanaZ = mcl.VentanaZ


def calcular_percentil_intradia_24h(
    volatilidad_bv: float,
    timestamp_utc: Optional[float] = None,
) -> Tuple[float, str]:
    return mcl.calcular_percentil_intradia_24h(volatilidad_bv, timestamp_utc)


def calcular_ofi_profundo(
    bids_prev: List[Tuple[float, float]],
    asks_prev: List[Tuple[float, float]],
    bids_curr: List[Tuple[float, float]],
    asks_curr: List[Tuple[float, float]],
) -> float:
    return mcl.calcular_ofi_profundo(bids_prev, asks_prev, bids_curr, asks_curr)


def calcular_exponente_hurst(precios_activos: List[float], z_score_actual: float = 0.0) -> float:
    return mcl.calcular_exponente_hurst(precios_activos, z_score_actual=z_score_actual)


def calcular_aceleracion_lyapunov(precios: List[float], spread_pct: float = 0.0) -> float:
    return mcl.calcular_aceleracion_lyapunov(precios, spread_pct=spread_pct)


class EstadoRadarPar:
    def __init__(self, symbol: str) -> None:
        self.symbol: str = symbol
        self.ventana_z: VentanaZ = VentanaZ()
        self.bids_prev: List[Tuple[float, float]] = []
        self.asks_prev: List[Tuple[float, float]] = []
        self.precios_activos: Deque[float] = collections.deque(maxlen=64)
        self.ofi_ema_5s: float = 0.0
        self.ultimo_ofi_top5: float = 0.0
        self.ofi_ticks_pos: int = 0
        self.ofi_ticks_neg: int = 0
        self.intensidad_hawkes: float = 0.0
        self.vpin_ema: float = 0.05
        self.ultimo_ts: float = 0.0
        self.ultimo_shock_lyapunov_ts: float = 0.0
        self.ultimo_pulso_toxico_ts: float = 0.0
        self.ultimo_hurst_alto_short_ts: float = 0.0
        self.px_squeeze_max: float = 0.0
        self.ultimo_rally_squeeze_ts: float = 0.0
        self.vigilancia_short_hasta_ts: float = 0.0
        self.max_z_pump_short: float = 0.0
        self.max_ema_pump_short: float = 0.0
        self.px_pico_pump_short: float = 0.0
        self.ultimo_log_warn_ts: float = 0.0


class RadarVolatilidadHFT:
    """
    Terpsichora V1.0 L2 Microstructural Radar with 4.50s Puppeteer Phase-Latched
    Envelope, Top-Rollover SHORT-SNIPER Capture, Strict Sign Coherence (RF-06),
    and 12s Macro BTC-Veto Cooldown.
    """

    def __init__(self) -> None:
        self.estados_par: Dict[str, EstadoRadarPar] = {
            par: EstadoRadarPar(par) for par in cfg.UNIVERSO_PARES_TOTAL
        }

    def resetear_libro_par(self, symbol: str) -> None:
        est = self.estados_par.get(symbol)
        if est is not None:
            est.bids_prev.clear()
            est.asks_prev.clear()

    def obtener_estado_par(self, symbol: str) -> EstadoRadarPar:
        est = self.estados_par.get(symbol)
        if est is None:
            est = EstadoRadarPar(symbol)
            self.estados_par[symbol] = est
        return est

    def _verificar_veto_macro_btc(self, direccion: str, ahora: float) -> Tuple[bool, str]:
        return mvb.verificar_veto_macro_btc_completo(direccion, ahora)

    def procesar_instantanea_libro(
        self,
        symbol: str,
        orderbook: Dict[str, Any],
        timestamp: Optional[float] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        ahora = float(timestamp) if timestamp is not None else time.time()
        bids_raw = orderbook.get("bids") or []
        asks_raw = orderbook.get("asks") or []
        if not bids_raw or not asks_raw:
            return False, "EMPTY_ORDERBOOK", None

        bids: List[Tuple[float, float]] = [(float(b[0]), float(b[1])) for b in bids_raw[:5]]
        asks: List[Tuple[float, float]] = [(float(a[0]), float(a[1])) for a in asks_raw[:5]]
        best_bid, best_bid_qty = bids[0]
        best_ask, best_ask_qty = asks[0]
        if best_bid <= 0.0 or best_ask <= 0.0 or best_ask < best_bid:
            return False, "INVALID_QUOTES", None

        mid = 0.5 * (best_bid + best_ask)
        spread_pct = (best_ask - best_bid) / mid
        liq_top = best_bid_qty + best_ask_qty
        micro_price = (
            ((best_bid * best_ask_qty) + (best_ask * best_bid_qty)) / liq_top
            if liq_top > 0.0
            else mid
        )

        est = self.obtener_estado_par(symbol)
        dt = max(0.005, min(1.0, ahora - est.ultimo_ts)) if est.ultimo_ts > 0.0 else cfg.INTERVALO_RADAR_SEG
        est.ultimo_ts = ahora

        z_score, dp_pct, vol_bv = est.ventana_z.actualizar(micro_price, ahora)
        if not est.precios_activos or abs(micro_price - est.precios_activos[-1]) > 1e-12:
            est.precios_activos.append(micro_price)

        top5_cambio = (bids != est.bids_prev) or (asks != est.asks_prev)
        if not est.bids_prev or not est.asks_prev:
            ofi_inst = 0.0
            est.ultimo_ofi_top5 = 0.0
            est.bids_prev = bids
            est.asks_prev = asks
        elif top5_cambio:
            ofi_raw = calcular_ofi_profundo(est.bids_prev, est.asks_prev, bids, asks)
            est.bids_prev = bids
            est.asks_prev = asks
            if abs(ofi_raw) < 0.06 and (ofi_raw * est.ultimo_ofi_top5) >= 0.0:
                ofi_inst = round((0.60 * ofi_raw) + (0.40 * est.ultimo_ofi_top5), 4)
            else:
                ofi_inst = ofi_raw
            est.ultimo_ofi_top5 = ofi_inst
            if ofi_inst >= cfg.OFI_MIN_ENTRADA:
                est.ofi_ticks_pos += 1
                est.ofi_ticks_neg = 0
            elif ofi_inst <= -cfg.OFI_MIN_ENTRADA:
                est.ofi_ticks_neg += 1
                est.ofi_ticks_pos = 0
            elif (est.ofi_ticks_pos > 0 and ofi_inst >= -0.03) or (est.ofi_ticks_neg > 0 and ofi_inst <= 0.03):
                # Micro-pause on same direction does not erase accumulated tick persistence
                pass
            else:
                est.ofi_ticks_pos = max(0, est.ofi_ticks_pos - 1)
                est.ofi_ticks_neg = max(0, est.ofi_ticks_neg - 1)
        else:
            # Deep levels (6..50) changed, but Top-5 quotes/sizes are identical:
            # preserve the last genuine Top-5 OFI instead of overwriting with negative 5s EMA
            ofi_inst = round(est.ultimo_ofi_top5 * math.exp(-dt / 1.50), 4)

        alpha_5s = min(1.0, dt / 1.8)
        if top5_cambio:
            est.ofi_ema_5s = round((alpha_5s * ofi_inst) + ((1.0 - alpha_5s) * est.ofi_ema_5s), 4)

        decay = math.exp(-dt / max(0.08, cfg.HAWKES_MEMORIA_PULSO_SEG))
        if (est.ofi_ticks_pos >= 2 and est.intensidad_hawkes < 0.0) or (
            est.ofi_ticks_neg >= 2 and est.intensidad_hawkes > 0.0
        ):
            decay *= 0.35
        raw_hawkes = (est.intensidad_hawkes * decay) + (ofi_inst * 0.85)
        est.intensidad_hawkes = round(max(-1.0, min(1.0, raw_hawkes)), 4)
        if ofi_inst <= -0.35:
            est.ultimo_pulso_toxico_ts = ahora

        hurst = calcular_exponente_hurst(list(est.precios_activos), z_score_actual=z_score)
        acel_lyap = calcular_aceleracion_lyapunov(list(est.precios_activos), spread_pct=spread_pct)
        tox_inst = min(
            1.0,
            (spread_pct / max(1e-6, cfg.SPREAD_MAX_PERMITIDO_PCT)) * 0.30
            + (0.25 if abs(acel_lyap) > 0.0025 else 0.04),
        )
        est.vpin_ema = round((0.08 * tox_inst) + (0.92 * est.vpin_ema), 4)
        if not mef.evaluar_freno_lyapunov('LONG', acel_lyap, cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO)[0]:
            est.ultimo_shock_lyapunov_ts = ahora

        ema_macro = est.ventana_z.ema_macro if est.ventana_z.ema_macro > 0.0 else mid
        ema_prev = est.ventana_z.ema_macro_prev if est.ventana_z.ema_macro_prev > 0.0 else ema_macro
        ema900_dist_pct = (mid - ema_macro) / ema_macro if ema_macro > 0.0 else 0.0
        ema900_slope_pct = ((ema_macro - ema_prev) / ema_prev) * 100.0 if ema_prev > 0.0 else 0.0
        percentil_24h, etiqueta_p = calcular_percentil_intradia_24h(vol_bv, ahora)

        metrica = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
        if metrica is None:
            metrica = ram.MetricaTick(symbol=symbol)
            ram.ESTADO_GLOBAL.metricas_ticks[symbol] = metrica

        metrica.timestamp = ahora
        metrica.bid = best_bid
        metrica.ask = best_ask
        metrica.bid_qty = best_bid_qty
        metrica.ask_qty = best_ask_qty
        metrica.mid = mid
        metrica.micro_price = micro_price
        metrica.spread_pct = spread_pct
        metrica.z_score = z_score
        metrica.dp_pct = dp_pct
        metrica.ema_rapida = est.ventana_z.ema_rapida
        metrica.ema_macro = ema_macro
        metrica.ema900_dist_pct = ema900_dist_pct
        metrica.ema900_slope_pct = ema900_slope_pct
        metrica.ofi_profundo = ofi_inst
        metrica.ofi_5s = est.ofi_ema_5s
        metrica.ofi_ticks_consecutivos = max(est.ofi_ticks_pos, est.ofi_ticks_neg)
        metrica.hurst = hurst
        metrica.aceleracion_lyapunov = acel_lyap
        metrica.intensidad_hawkes = est.intensidad_hawkes
        metrica.vpin = est.vpin_ema
        metrica.volatilidad_bv = vol_bv
        metrica.percentil_24h = percentil_24h
        metrica.ultimo_shock_lyapunov_ts = est.ultimo_shock_lyapunov_ts
        metrica.ultimo_pulso_toxico_hawkes_ts = est.ultimo_pulso_toxico_ts

        if symbol == cfg.PAR_LIDER_MACRO:
            self._verificar_veto_macro_btc("LONG", ahora)
            return False, "MACRO_LEADER_UPDATED", None

        tri.evaluar_filtro_anti_luna(symbol, dp_pct, ofi_inst)

        if z_score <= -3.50 and acel_lyap < cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO:
            contagio, pares_c = ram.ESTADO_GLOBAL.registrar_evento_colapso(symbol, ahora)
            if contagio:
                ram.log_operativo(
                    f"[CIRCUIT BREAKER CONTAGION] {len(pares_c)} pairs collapsing simultaneously "
                    f"in <=10s ({', '.join(pares_c)})! Activating macro shield "
                    f"({int(cfg.PAUSA_MACRO_CONTAGIO_SEG)}s) and evacuating positions..."
                )
                return False, "CONTAGION_CIRCUIT_BREAKER", None

        if spread_pct > cfg.SPREAD_MAX_PERMITIDO_PCT:
            return False, "SPREAD_FRICTION_EXCEEDED", None

        if est.vpin_ema > cfg.VPIN_MAX_TOXICIDAD:
            return False, "VPIN_TOXICITY_EXCEEDED", None

        clase = cfg.obtener_clase_activo(symbol)
        es_hb = clase == cfg.CLASE_HIGH_BETA
        ctrl = ram.ESTADO_GLOBAL.controlador_autonomo

        # ======================================================================
        # PATH A: TERPSICHORA V1.0 PHASE-LATCHED LONG V-BOTTOM ENGINE (4.50s)
        # ======================================================================
        h_cap_long = cfg.HURST_MAX_ENTRADA_LONG if es_hb else cfg.HURST_MAX_ENTRADA_LONG_T1
        ofi_min_long = max(cfg.OFI_MIN_ENTRADA, min(0.16, float(ctrl.get("w1_ofi_long", cfg.OFI_MIN_ENTRADA))))

        if ema900_dist_pct > cfg.EMA900_MAX_SOBRECOMPRA_LONG and z_score < 0.0:
            return False, "ANTI_PUMP_TOP_VETO", None

        dislocacion_long_activa, latch_long_vigente = mep.evaluar_dislocacion_y_latch_long(
            es_hb, z_score, dp_pct, ema900_dist_pct, ahora, metrica
        )

        if (dislocacion_long_activa or latch_long_vigente) and mef.evaluar_coherencia_signo_rf06("LONG", z_score, dp_pct)[0]:
            vector_snap = {
                "z_entry": z_score,
                "dp_pct": round(dp_pct * 100.0, 4),
                "ema900_pct": round(ema900_dist_pct * 100.0, 4),
                "ofi_entry": ofi_inst,
                "hurst_entry": hurst,
                "hawkes_entry": est.intensidad_hawkes,
                "lyapunov_entry": acel_lyap,
                "volatilidad_bv": vol_bv,
                "percentil_24h": etiqueta_p,
            }

            if acel_lyap < cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO:
                if not cfg.es_modo_test() and (ahora - est.ultimo_log_warn_ts) >= 1.0:
                    est.ultimo_log_warn_ts = ahora
                    ram.log_operativo(
                        f"[WARN] [LYAPUNOV REPULSOR] {symbol} drop accelerating "
                        f"(a={acel_lyap * 100:+.4f}% < {cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO * 100:+.4f}%). Waiting for braking."
                    )
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "LONG", "LYAPUNOV_REPULSOR", f"a={acel_lyap:.5f}", mid, vector_snap
                )
                return False, "LYAPUNOV_ACCELERATING_DROP", None

            if ofi_inst < ofi_min_long or est.ofi_ticks_pos < cfg.OFI_TICKS_PERSISTENCIA_MIN:
                if not cfg.es_modo_test() and (ahora - est.ultimo_log_warn_ts) >= 1.0:
                    est.ultimo_log_warn_ts = ahora
                    ram.log_operativo(
                        f"[WARN] [MICROSTRUCTURE] {symbol} [LONG] waiting for bid absorption "
                        f"(OFI={ofi_inst:+.2f} [{est.ofi_ticks_pos}/{cfg.OFI_TICKS_PERSISTENCIA_MIN}t] req >={ofi_min_long:+.2f} | Z={z_score:+.2f} | H={hurst:.2f})."
                    )
                return False, "OFI_INSUFFICIENT_PERSISTENCE", None

            if ahora < ram.ESTADO_GLOBAL.btc_veto_long_hasta:
                m_b = ram.ESTADO_GLOBAL.metricas_ticks.get(cfg.PAR_LIDER_MACRO)
                if m_b is not None and mvb.puede_liberar_cooldown_btc_en_giro_sincronizado(
                    "LONG",
                    ram.ESTADO_GLOBAL.btc_veto_long_hasta - ahora,
                    m_b.z_score,
                    m_b.ofi_profundo,
                    ofi_inst,
                    hurst,
                    acel_lyap,
                    cfg.BTC_VETO_COOLDOWN_SEG,
                ):
                    ram.ESTADO_GLOBAL.btc_veto_long_hasta = 0.0
            ok_btc, motivo_btc = self._verificar_veto_macro_btc("LONG", ahora)
            if not ok_btc:
                if not cfg.es_modo_test() and (ahora - est.ultimo_log_warn_ts) >= 1.0:
                    est.ultimo_log_warn_ts = ahora
                    ram.log_operativo(f"[PHANTOM P-01 BTC-VETO] {symbol} [LONG] blocked BEFORE order ({motivo_btc}).")
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "LONG", "P-01_BTC_VETO", motivo_btc, mid, vector_snap
                )
                return False, motivo_btc, None

            if (
                not mef.evaluar_filtro_hurst_direccional('LONG', hurst, h_cap_long, h_cap_long)[0]
                and not mir.evaluar_override_climax_hurst('LONG', z_score, ofi_inst, est.intensidad_hawkes, acel_lyap, hurst)
            ):
                if not cfg.es_modo_test() and (ahora - est.ultimo_log_warn_ts) >= 1.0:
                    est.ultimo_log_warn_ts = ahora
                    ram.log_operativo(
                        f"[WARN] [HURST FILTER] {symbol} high trend persistence (H={hurst:.3f} > {h_cap_long:.3f}). Aborting."
                    )
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "LONG", "HURST_FILTER", f"H={hurst:.3f}>{h_cap_long:.3f}", mid, vector_snap
                )
                return False, "HURST_TREND_PERSISTENCE", None

            if est.intensidad_hawkes < cfg.HAWKES_INTENSIDAD_MIN_LONG:
                if not cfg.es_modo_test() and (ahora - est.ultimo_log_warn_ts) >= 1.0:
                    est.ultimo_log_warn_ts = ahora
                    ram.log_operativo(
                        f"[WARN] [HAWKES MEMORY] {symbol} absorption still weak "
                        f"(I_Hawkes={est.intensidad_hawkes:+.2f} < +{cfg.HAWKES_INTENSIDAD_MIN_LONG:.2f} | Z={z_score:+.2f})."
                    )
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "LONG", "HAWKES_MEMORY", f"I={est.intensidad_hawkes:.2f}", mid, vector_snap
                )
                return False, "HAWKES_WEAK_ABSORPTION", None

            t0_lk = time.perf_counter()
            perm_ok, motivo_perm = ram.ESTADO_GLOBAL.consultar_permiso_o1(symbol, "LONG", ahora)
            lat_us = (time.perf_counter() - t0_lk) * 1e6
            if not perm_ok:
                return False, motivo_perm, None

            z_eff = min(z_score, metrica.phase_latch_z_peak or z_score)
            metrica.phase_latched = False
            ram.log_operativo(
                f"[RADAR] {symbol} [LONG] Z={z_eff:+.2f} "
                f"({dp_pct * 100:+.2f}% | EMA900 {ema900_dist_pct * 100:+.2f}%) "
                f"OFI={ofi_inst:+.2f} ({est.ofi_ticks_pos}t) | H={hurst:.2f} | "
                f"I_Hawkes={est.intensidad_hawkes:+.2f} -> RAM SHIELD O(1): APPROVED ({lat_us:.1f} us)"
            )
            return True, "LONG", {
                "symbol": symbol,
                "side": "LONG",
                "precio_ref": mid,
                "bid": best_bid,
                "ask": best_ask,
                "micro_price": micro_price,
                "bid_qty": best_bid_qty,
                "ask_qty": best_ask_qty,
                "spread_pct": spread_pct,
                "z_score": z_eff,
                "dp_pct": dp_pct,
                "ema900_pct": ema900_dist_pct,
                "ofi": ofi_inst,
                "ofi_ticks": est.ofi_ticks_pos,
                "hurst": hurst,
                "hawkes": est.intensidad_hawkes,
                "lyapunov": acel_lyap,
                "volatilidad_bv": vol_bv,
                "percentil_24h": percentil_24h,
                "etiqueta_percentil": etiqueta_p,
            }

        # ======================================================================
        # PATH B: TERPSICHORA V1.0 EXHAUSTED-TOP & ROLLOVER SHORT-SNIPER ENGINE
        # ======================================================================
        h_cap_short = min(
            cfg.HURST_TECHO_DURO_ABSOLUTO,
            float(ctrl.get("hurst_cap_short_mod", cfg.HURST_MAX_ENTRADA_SHORT)),
        )

        sobreextension_short, latch_short_vigente, rollover_techo_vigente = (
            mep.evaluar_sobreextension_y_rollover_short(
                es_hb, z_score, dp_pct, ema900_dist_pct, mid, ofi_inst, ahora, metrica, est
            )
        )

        if sobreextension_short or latch_short_vigente or rollover_techo_vigente:
            vector_snap_s = {
                "z_entry": z_score,
                "dp_pct": round(dp_pct * 100.0, 4),
                "ema900_pct": round(ema900_dist_pct * 100.0, 4),
                "ofi_entry": ofi_inst,
                "hurst_entry": hurst,
                "hawkes_entry": est.intensidad_hawkes,
                "lyapunov_entry": acel_lyap,
                "volatilidad_bv": vol_bv,
                "percentil_24h": etiqueta_p,
            }

            if not mef.evaluar_freno_lyapunov("SHORT", acel_lyap, umbral_agotamiento_short=cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO)[0]:
                return False, "SHORT_NO_LYAPUNOV_EXHAUSTION", None

            if ofi_inst > cfg.OFI_MAX_ENTRADA_SHORT or est.ofi_ticks_neg < cfg.OFI_TICKS_PERSISTENCIA_MIN:
                return False, "SHORT_OFI_INSUFFICIENT", None

            if ahora < ram.ESTADO_GLOBAL.btc_veto_short_hasta:
                m_b = ram.ESTADO_GLOBAL.metricas_ticks.get(cfg.PAR_LIDER_MACRO)
                if m_b is not None and mvb.puede_liberar_cooldown_btc_en_giro_sincronizado(
                    "SHORT",
                    ram.ESTADO_GLOBAL.btc_veto_short_hasta - ahora,
                    m_b.z_score,
                    m_b.ofi_profundo,
                    ofi_inst,
                    hurst,
                    acel_lyap,
                    cfg.BTC_VETO_COOLDOWN_SEG,
                ):
                    ram.ESTADO_GLOBAL.btc_veto_short_hasta = 0.0
            ok_btc_s, motivo_btc_s = self._verificar_veto_macro_btc("SHORT", ahora)
            if not ok_btc_s:
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "SHORT", "P-01_BTC_VETO", motivo_btc_s, mid, vector_snap_s
                )
                return False, motivo_btc_s, None

            perm_par = ram.ESTADO_GLOBAL.whitelist_pares.get(symbol)
            if perm_par and ahora < perm_par.step_lock_short_until:
                if mid <= perm_par.step_lock_short_price * 1.0015 and ema900_slope_pct > 0.02:
                    return False, "ANTI_SQUEEZE_STEP_LOCK", None

            if (
                not mef.evaluar_filtro_hurst_direccional("SHORT", hurst, h_cap_short, h_cap_short)[0]
                and not mir.evaluar_override_climax_hurst("SHORT", z_score, ofi_inst, est.intensidad_hawkes, acel_lyap, hurst)
            ):
                est.ultimo_hurst_alto_short_ts = ahora
                if not cfg.es_modo_test() and (ahora - est.ultimo_log_warn_ts) >= 1.0:
                    est.ultimo_log_warn_ts = ahora
                    ram.log_operativo(
                        f"[PHANTOM P-02 PRE-ORDER] {symbol} [SHORT] blocked BEFORE sending order "
                        f"in {etiqueta_p} (H={hurst:.3f} > {h_cap_short:.3f})."
                    )
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "SHORT", "P-02_HURST_SHORT", f"H={hurst:.3f}>{h_cap_short:.3f}", mid, vector_snap_s
                )
                return False, "SHORT_HURST_EXCEEDED", None

            if (ahora - est.ultimo_hurst_alto_short_ts) < 15.0:
                return False, "SHORT_POST_HURST_COOLDOWN", None

            if est.intensidad_hawkes > cfg.HAWKES_INTENSIDAD_MAX_SHORT:
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "SHORT", "P-03_HAWKES_SHORT", f"I={est.intensidad_hawkes:+.2f}", mid, vector_snap_s
                )
                return False, "SHORT_BULLISH_HAWKES_MEMORY", None

            t0_lk = time.perf_counter()
            perm_ok_s, motivo_perm_s = ram.ESTADO_GLOBAL.consultar_permiso_o1(symbol, "SHORT", ahora)
            lat_us_s = (time.perf_counter() - t0_lk) * 1e6
            if not perm_ok_s:
                return False, motivo_perm_s, None

            ram.log_operativo(
                f"[RADAR] {symbol} [SHORT-SNIPER] EMA900={ema900_dist_pct * 100:+.2f}% | "
                f"OFI={ofi_inst:+.2f} ({est.ofi_ticks_neg}t) | H={hurst:.2f} | "
                f"a_Lyap={acel_lyap * 100:+.4f}% -> RAM SHIELD O(1): APPROVED ({lat_us_s:.1f} us)"
            )
            z_eff_s = max(z_score, metrica.phase_latch_z_peak or est.max_z_pump_short or z_score)
            metrica.phase_latched = False
            est.vigilancia_short_hasta_ts = 0.0
            return True, "SHORT", {
                "symbol": symbol,
                "side": "SHORT",
                "precio_ref": mid,
                "bid": best_bid,
                "ask": best_ask,
                "micro_price": micro_price,
                "bid_qty": best_bid_qty,
                "ask_qty": best_ask_qty,
                "spread_pct": spread_pct,
                "z_score": z_eff_s,
                "dp_pct": dp_pct,
                "ema900_pct": ema900_dist_pct,
                "ofi": ofi_inst,
                "ofi_ticks": est.ofi_ticks_neg,
                "hurst": hurst,
                "hawkes": est.intensidad_hawkes,
                "lyapunov": acel_lyap,
                "volatilidad_bv": vol_bv,
                "percentil_24h": percentil_24h,
                "etiqueta_percentil": etiqueta_p,
            }

        return False, "NO_SIGNAL", None


RADAR_GLOBAL = RadarVolatilidadHFT()
