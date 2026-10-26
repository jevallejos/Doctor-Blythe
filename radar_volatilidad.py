"""
Level 5 DAG: 25.0 Hz L2 Microstructural Radar, Bipower Variation Z-Score Engine,
24-Hour Elastic Seasonality Curve, Immutable SCAR_BASE (SCAR-LOCK-00..18),
4.50s Puppeteer Phase-Latched Envelope, and Top-Rollover SHORT-SNIPER Capture
for HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import collections
import datetime
import math
import time
from typing import Any, Deque, Dict, List, Optional, Tuple

import config_parametros as cfg
import core_estado_ram as ram
import escudo_tricortex as tri

_TZ_UTC = datetime.timezone.utc

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

_CURVA_ESTACIONAL_24H_UTC: Tuple[float, ...] = (
    0.58, 0.55, 0.52, 0.48, 0.45, 0.46,
    0.52, 0.64, 0.72, 0.75, 0.70, 0.66,
    0.74, 0.88, 0.94, 0.92, 0.85, 0.76,
    0.68, 0.64, 0.62, 0.60, 0.59, 0.58,
)


def calcular_percentil_intradia_24h(
    volatilidad_bv: float,
    timestamp_utc: Optional[float] = None,
) -> Tuple[float, str]:
    ts = timestamp_utc if timestamp_utc is not None else time.time()
    hora_utc = datetime.datetime.fromtimestamp(ts, _TZ_UTC).hour
    base_estacional = _CURVA_ESTACIONAL_24H_UTC[hora_utc % 24]
    sigma_ref = max(float(volatilidad_bv), cfg.VOLATILIDAD_BV_PISO_MIN)
    ratio_vol = min(1.45, max(0.65, sigma_ref / 0.00075))
    percentil = max(
        cfg.PERCENTIL_DIA_MIN,
        min(cfg.PERCENTIL_DIA_MAX, base_estacional * ratio_vol),
    )
    etiqueta = f"P{int(round(percentil * 100)):02d}_ELASTICO"
    return round(percentil, 4), etiqueta


class VentanaZ:
    """
    Jump-Robust Bipower Variation Z-Score & Horizon-Synchronized Excursion Engine.
    """

    def __init__(
        self,
        maxlen: int = cfg.VENTANA_Z_TICKS,
        piso_volatilidad: float = cfg.VOLATILIDAD_BV_PISO_MIN,
    ) -> None:
        self.maxlen: int = max(30, int(maxlen))
        self.piso_volatilidad: float = max(0.00035, float(piso_volatilidad))
        self.precios: Deque[float] = collections.deque(maxlen=self.maxlen)
        self.retornos: Deque[float] = collections.deque(maxlen=self.maxlen)
        self.ema_rapida: float = 0.0
        self.ema_macro: float = 0.0
        self.ema_macro_prev: float = 0.0
        self.volatilidad_bv: float = self.piso_volatilidad
        self.z_score: float = 0.0
        self.dp_pct: float = 0.0

    def actualizar(self, precio: float, timestamp: Optional[float] = None) -> Tuple[float, float, float]:
        p = float(precio)
        if p <= 0.0:
            return self.z_score, self.dp_pct, self.volatilidad_bv

        if self.precios:
            prev = self.precios[-1]
            ret = (p - prev) / prev if prev > 0.0 else 0.0
            if abs(ret) > 1e-9:
                self.retornos.append(ret)
        self.precios.append(p)

        alpha_fast = 2.0 / (cfg.EMA_RAPIDA_TICKS + 1.0)
        alpha_macro = 2.0 / (cfg.EMA_MACRO_TICKS + 1.0)
        if self.ema_rapida <= 0.0:
            self.ema_rapida = p
            self.ema_macro = p
            self.ema_macro_prev = p
        else:
            self.ema_rapida = (alpha_fast * p) + ((1.0 - alpha_fast) * self.ema_rapida)
            self.ema_macro_prev = self.ema_macro
            self.ema_macro = (alpha_macro * p) + ((1.0 - alpha_macro) * self.ema_macro)

        if len(self.precios) < 4:
            return 0.0, 0.0, self.volatilidad_bv

        p_base = self.precios[0]
        self.dp_pct = (p - p_base) / p_base if p_base > 0.0 else 0.0

        rets_activos = [abs(r) for r in self.retornos if abs(r) > 1e-9]
        if len(rets_activos) >= 4:
            pares_bv = [
                rets_activos[i] * rets_activos[i - 1]
                for i in range(1, len(rets_activos))
            ]
            media_bv = (math.pi / 2.0) * (sum(pares_bv) / len(pares_bv))
            sigma_tick = math.sqrt(max(0.0, media_bv))
            sigma_horizonte = sigma_tick * math.sqrt(min(12.0, float(len(rets_activos))))
            self.volatilidad_bv = max(self.piso_volatilidad, min(0.00110, sigma_horizonte))
        else:
            self.volatilidad_bv = max(self.piso_volatilidad, cfg.VOLATILIDAD_BV_PISO_MIN)

        desviacion_compuesta = 0.72 * self.dp_pct + 0.28 * ((p - self.ema_rapida) / self.ema_rapida)
        self.z_score = round(desviacion_compuesta / self.volatilidad_bv, 4)
        return self.z_score, round(self.dp_pct, 6), round(self.volatilidad_bv, 6)


def calcular_ofi_profundo(
    bids_prev: List[Tuple[float, float]],
    asks_prev: List[Tuple[float, float]],
    bids_curr: List[Tuple[float, float]],
    asks_curr: List[Tuple[float, float]],
) -> float:
    pesos = cfg.OFI_PESOS_NIVELES
    niveles = min(cfg.OFI_NIVELES_PROFUNDO, len(pesos))
    num = 0.0
    den = 0.0

    for idx in range(niveles):
        w = pesos[idx]
        bp, bq_p = bids_prev[idx] if idx < len(bids_prev) else (0.0, 0.0)
        ap, aq_p = asks_prev[idx] if idx < len(asks_prev) else (0.0, 0.0)
        bc, bq_c = bids_curr[idx] if idx < len(bids_curr) else (0.0, 0.0)
        ac, aq_c = asks_curr[idx] if idx < len(asks_curr) else (0.0, 0.0)

        if bc > bp:
            delta_b = bq_c
        elif bc == bp:
            delta_b = bq_c - bq_p
        else:
            delta_b = -bq_p

        if ac < ap:
            delta_a = aq_c
        elif ac == ap:
            delta_a = aq_c - aq_p
        else:
            delta_a = -aq_p

        ofi_lvl = delta_b - delta_a
        cap_lvl = bq_c + aq_c + bq_p + aq_p + 1e-9
        num += w * ofi_lvl
        den += w * (cap_lvl * 0.5)

    if den <= 1e-9:
        return 0.0
    est = max(-1.0, min(1.0, num / den))
    return round(est, 4)


def calcular_exponente_hurst(precios_activos: List[float], z_score_actual: float = 0.0) -> float:
    cambios = [precios_activos[0]] if precios_activos else []
    for p in precios_activos[1:]:
        if abs(p - cambios[-1]) > 1e-12:
            cambios.append(p)

    if len(cambios) < 8:
        return 0.40

    ventana = cambios[-max(12, cfg.HURST_VENTANA_TICKS):]
    rets = [
        math.log(ventana[i] / ventana[i - 1])
        for i in range(1, len(ventana))
        if ventana[i] > 0.0 and ventana[i - 1] > 0.0
    ]
    if len(rets) < 6:
        return 0.40

    abs_rets = sorted(abs(r) for r in rets if abs(r) > 0.0)
    med = abs_rets[len(abs_rets) // 2] if abs_rets else 1e-4
    cap = max(med * 2.5, 1e-5)
    r_clip = [max(-cap, min(cap, r)) for r in rets]

    tramo_local = r_clip[-16:]
    media_local = sum(tramo_local) / len(tramo_local)
    frenado_activo = (r_clip[-1] * media_local) <= 0.0 or abs(r_clip[-1]) < abs(media_local) * 0.65
    serie_eval = [r - media_local for r in tramo_local] if frenado_activo else r_clip

    denom = sum(r * r for r in serie_eval)
    if denom <= 1e-15:
        return 0.38

    num = sum(serie_eval[i] * serie_eval[i - 1] for i in range(1, len(serie_eval)))
    rho1 = max(-0.45, min(0.75, num / denom))
    h_raw = 0.50 + (0.50 * (math.log(max(0.25, 1.0 + rho1)) / math.log(2.0)))

    if len(rets) >= 5 and (all(r > 0.0 for r in rets[-5:]) or all(r < 0.0 for r in rets[-5:])):
        h_raw = max(h_raw, 0.56)

    if z_score_actual >= cfg.Z_SCORE_IGNICION_SHORT_VETO and ventana[-1] >= max(ventana[:-1]):
        h_raw = max(h_raw, 0.58)

    return round(max(0.20, min(0.80, h_raw)), 4)


def calcular_aceleracion_lyapunov(precios: List[float], spread_pct: float = 0.0) -> float:
    """
    Tick-Aware Multi-Step Second-Order Price Kinematics (Lyapunov Acceleration/Braking).
    Suppresses single-tick micro-noise on low-priced assets (ZEREBRO/WAL) while
    catching genuine multi-tick waterfalls.
    """
    if len(precios) < 5:
        return 0.0
    ventana = precios[-max(5, cfg.LYAPUNOV_VENTANA_TICKS):]
    p0, p_mid, p_end = ventana[0], ventana[len(ventana) // 2], ventana[-1]
    if p0 <= 0.0 or p_mid <= 0.0:
        return 0.0
    v1 = (p_mid - p0) / p0
    v2 = (p_end - p_mid) / p_mid
    acel = v2 - v1
    # Suppress single-tick micro-noise in LONG when v2 is within 1.25x spread
    if acel < 0.0 and v2 < 0.0 and spread_pct > 0.0 and abs(v2) <= (spread_pct * 1.15):
        return round(max(acel, cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO * 0.5), 6)
    return round(acel, 6)


class EstadoRadarPar:
    def __init__(self, symbol: str) -> None:
        self.symbol: str = symbol
        self.ventana_z: VentanaZ = VentanaZ()
        self.bids_prev: List[Tuple[float, float]] = []
        self.asks_prev: List[Tuple[float, float]] = []
        self.precios_activos: Deque[float] = collections.deque(maxlen=64)
        self.ofi_ema_5s: float = 0.0
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
                (m_btc.ofi_profundo <= -umbral_ofi_btc)
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
                (m_btc.ofi_profundo >= umbral_ofi_btc)
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

        ofi_inst = (
            calcular_ofi_profundo(est.bids_prev, est.asks_prev, bids, asks)
            if est.bids_prev and est.asks_prev
            else 0.0
        )
        est.bids_prev = bids
        est.asks_prev = asks

        alpha_5s = min(1.0, dt / 2.5)
        est.ofi_ema_5s = round((alpha_5s * ofi_inst) + ((1.0 - alpha_5s) * est.ofi_ema_5s), 4)

        if ofi_inst >= cfg.OFI_MIN_ENTRADA:
            est.ofi_ticks_pos += 1
            est.ofi_ticks_neg = 0
        elif ofi_inst <= -cfg.OFI_MIN_ENTRADA:
            est.ofi_ticks_neg += 1
            est.ofi_ticks_pos = 0
        else:
            est.ofi_ticks_pos = max(0, est.ofi_ticks_pos - 1)
            est.ofi_ticks_neg = max(0, est.ofi_ticks_neg - 1)

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
        if acel_lyap < cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO:
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
        z_umbral_long = cfg.Z_SCORE_UMBRAL_HIGH_BETA if es_hb else cfg.Z_SCORE_UMBRAL_TIER1
        dp_min_long = cfg.DP_MIN_EXCURSION_LONG_HB if es_hb else cfg.DP_MIN_EXCURSION_LONG_T1
        ema_piso_base = cfg.EMA900_DISTANCIA_MIN_LONG_HB if es_hb else cfg.EMA900_DISTANCIA_MIN_LONG_T1
        recorrido_req = min(dp_min_long, ema_piso_base * 0.85)
        piso_anti_ruido = -0.0018 if es_hb else -0.0014
        h_cap_long = cfg.HURST_MAX_ENTRADA_LONG if es_hb else cfg.HURST_MAX_ENTRADA_LONG_T1
        ofi_min_long = max(cfg.OFI_MIN_ENTRADA, min(0.18, float(ctrl.get("w1_ofi_long", cfg.OFI_MIN_ENTRADA))))

        if ema900_dist_pct > cfg.EMA900_MAX_SOBRECOMPRA_LONG and z_score < 0.0:
            return False, "ANTI_PUMP_TOP_VETO", None

        excursion_dual_ok = (
            min(dp_pct, ema900_dist_pct) <= recorrido_req
            and max(dp_pct, ema900_dist_pct) <= piso_anti_ruido
        )
        dislocacion_long_activa = (
            z_score <= z_umbral_long
            and dp_pct < 0.0
            and excursion_dual_ok
        )
        if dislocacion_long_activa:
            metrica.phase_latched = True
            metrica.phase_latch_ts = ahora
            metrica.phase_latch_dir = "LONG"
            metrica.phase_latch_z_peak = min(metrica.phase_latch_z_peak or z_score, z_score)
            metrica.phase_latch_ema_dist = min(metrica.phase_latch_ema_dist or ema900_dist_pct, ema900_dist_pct)

        latch_long_vigente = (
            metrica.phase_latched
            and metrica.phase_latch_dir == "LONG"
            and (ahora - metrica.phase_latch_ts) <= cfg.PHASE_LATCH_VENTANA_SEG
            and z_score <= (z_umbral_long * 0.72)
            and dp_pct <= (dp_min_long * 0.70)
            and min(dp_pct, ema900_dist_pct) <= (recorrido_req * 0.80)
            and ema900_dist_pct <= (piso_anti_ruido * 0.85)
        )

        if dislocacion_long_activa or latch_long_vigente:
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
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "LONG", "LYAPUNOV_REPULSOR", f"a={acel_lyap:.5f}", mid, vector_snap
                )
                return False, "LYAPUNOV_ACCELERATING_DROP", None

            if ofi_inst < ofi_min_long or est.ofi_ticks_pos < cfg.OFI_TICKS_PERSISTENCIA_MIN:
                return False, "OFI_INSUFFICIENT_PERSISTENCE", None

            ok_btc, motivo_btc = self._verificar_veto_macro_btc("LONG", ahora)
            if not ok_btc:
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "LONG", "P-01_BTC_VETO", motivo_btc, mid, vector_snap
                )
                return False, motivo_btc, None

            if hurst > h_cap_long:
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol, "LONG", "HURST_FILTER", f"H={hurst:.3f}>{h_cap_long:.3f}", mid, vector_snap
                )
                return False, "HURST_TREND_PERSISTENCE", None

            if est.intensidad_hawkes < cfg.HAWKES_INTENSIDAD_MIN_LONG:
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
        ema_min_short = cfg.EMA900_SOBREEXTENSION_SHORT_HB if es_hb else cfg.EMA900_SOBREEXTENSION_SHORT_T1
        dp_min_short = cfg.DP_MIN_EXCURSION_SHORT_HB if es_hb else cfg.DP_MIN_EXCURSION_SHORT_T1
        h_cap_short = min(
            cfg.HURST_TECHO_DURO_ABSOLUTO,
            float(ctrl.get("hurst_cap_short_mod", cfg.HURST_MAX_ENTRADA_SHORT)),
        )

        sobreextension_short = (
            ema900_dist_pct >= ema_min_short
            and z_score >= cfg.Z_SCORE_SHORT_UMBRAL
            and dp_pct >= dp_min_short
        )
        if sobreextension_short:
            metrica.phase_latched = True
            metrica.phase_latch_ts = ahora
            metrica.phase_latch_dir = "SHORT"
            metrica.phase_latch_z_peak = max(metrica.phase_latch_z_peak or z_score, z_score)
            metrica.phase_latch_ema_dist = max(metrica.phase_latch_ema_dist or ema900_dist_pct, ema900_dist_pct)
            est.vigilancia_short_hasta_ts = ahora + 15.0
            est.max_z_pump_short = max(est.max_z_pump_short, z_score)
            est.max_ema_pump_short = max(est.max_ema_pump_short, ema900_dist_pct)
            est.px_pico_pump_short = max(est.px_pico_pump_short, mid)

        latch_short_vigente = (
            metrica.phase_latched
            and metrica.phase_latch_dir == "SHORT"
            and (ahora - metrica.phase_latch_ts) <= cfg.PHASE_LATCH_VENTANA_SEG
            and z_score > 0.0
            and dp_pct >= (dp_min_short * 0.65)
            and ema900_dist_pct >= (ema_min_short * 0.85)
        )

        # Top-Rollover Capture (Catch-22 Fix): captures the initial roll off the pump top
        # while still >= 85% overextended above EMA900, but blocks stale dumps (dp < -0.05%).
        rollover_techo_vigente = (
            ahora <= est.vigilancia_short_hasta_ts
            and est.max_z_pump_short >= cfg.Z_SCORE_SHORT_UMBRAL
            and ema900_dist_pct >= (ema_min_short * 0.88)
            and dp_pct >= -0.0005
            and mid <= (est.px_pico_pump_short * 0.9998)
            and ofi_inst <= (cfg.OFI_MAX_ENTRADA_SHORT - 0.06)
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

            if acel_lyap > cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO:
                return False, "SHORT_NO_LYAPUNOV_EXHAUSTION", None

            if ofi_inst > cfg.OFI_MAX_ENTRADA_SHORT or est.ofi_ticks_neg < cfg.OFI_TICKS_PERSISTENCIA_MIN:
                return False, "SHORT_OFI_INSUFFICIENT", None

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

            if hurst > h_cap_short:
                est.ultimo_hurst_alto_short_ts = ahora
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
