# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #1: Motores Matematicos L2 de Variacion Bipower (VentanaZ),
OFI Profundo de 5 Niveles, Exponente de Hurst, Cinematica de Lyapunov y Curva 24h.
"""
import collections
import datetime
import math
import time
from typing import Deque, List, Optional, Tuple
import config_parametros as cfg

_TZ_UTC = datetime.timezone.utc

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
        flujo_activo = abs(delta_b) + abs(delta_a)
        reg_liquidez = (bq_c + aq_c) * 0.035
        num += w * ofi_lvl
        den += w * max(flujo_activo + reg_liquidez, 1e-9)
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
    if len(precios) < 5:
        return 0.0
    ventana = precios[-max(5, cfg.LYAPUNOV_VENTANA_TICKS):]
    p0, p_mid, p_end = ventana[0], ventana[len(ventana) // 2], ventana[-1]
    if p0 <= 0.0 or p_mid <= 0.0:
        return 0.0
    v1 = (p_mid - p0) / p0
    v2 = (p_end - p_mid) / p_mid
    acel = v2 - v1
    umbral_tick = max(spread_pct * 1.25, 0.00042)
    if acel < 0.0 and (v2 >= 0.0 or abs(v2) <= umbral_tick):
        if v1 > umbral_tick and v2 <= 0.0:
            return round(acel, 6)
        return round(max(acel, cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO * 0.4), 6)
    return round(acel, 6)
