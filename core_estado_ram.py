"""
Level 1 DAG: O(1) In-Memory State Machine, Persistent Line-Buffered Log I/O,
and +15.0s Counterfactual Forensic AI Vault for HFT Doctor Blythe Engine -
Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import collections
import dataclasses
import datetime
import json
import os
import pathlib
import sys
import time
from typing import Any, Deque, Dict, List, Optional, Tuple

import config_parametros as cfg

MODO_DIRECCIONAL_DUAL: str = "DUAL_ACTIVE"
MODO_DIRECCIONAL_SOLO_LONG: str = "LONG_ONLY"
MODO_DIRECCIONAL_SOLO_SHORT: str = "SHORT_ONLY"
MODO_DIRECCIONAL_VETO: str = "VETO_TOXIC"

_TZ_UTC = datetime.timezone.utc
_TZ_CHILE = datetime.timezone(datetime.timedelta(hours=-3))
_DESCRIPTORES_LOG: Dict[str, Any] = {}


def obtener_timestamp_dual() -> str:
    now_utc = datetime.datetime.now(_TZ_UTC)
    now_cl = now_utc.astimezone(_TZ_CHILE)
    ms = int(now_utc.microsecond / 1000)
    return (
        f"[{now_cl.strftime('%Y-%m-%d %H:%M:%S')}.{ms:03d} CL | "
        f"{now_utc.strftime('%H:%M:%S')} UTC]"
    )


def _obtener_stream_log(ruta: pathlib.Path) -> Any:
    key = str(ruta.resolve())
    fh = _DESCRIPTORES_LOG.get(key)
    if fh is None or fh.closed:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        fh = open(ruta, mode="a", encoding="utf-8", buffering=1)
        _DESCRIPTORES_LOG[key] = fh
    return fh


def cerrar_descriptores_log() -> None:
    for key, fh in list(_DESCRIPTORES_LOG.items()):
        try:
            if fh and not fh.closed:
                fh.flush()
                fh.close()
        except Exception:
            pass
        _DESCRIPTORES_LOG.pop(key, None)


def log_operativo(mensaje: str, consola: bool = True) -> str:
    linea = f"{obtener_timestamp_dual()} {mensaje}"
    if consola:
        try:
            sys.stdout.write(linea + "\n")
            sys.stdout.flush()
        except Exception:
            pass
    try:
        ruta_log = cfg.obtener_ruta_archivo("ARCHIVO_LOG")
        fh = _obtener_stream_log(ruta_log)
        fh.write(linea + "\n")
        if not cfg.es_modo_test():
            ruta_hist = cfg.obtener_ruta_archivo("ARCHIVO_LOG_HISTORICO")
            fh_h = _obtener_stream_log(ruta_hist)
            fh_h.write(linea + "\n")
    except Exception:
        pass
    return linea


@dataclasses.dataclass(slots=True)
class PermisoParRAM:
    symbol: str
    habilitado: bool = True
    modo_direccional: str = MODO_DIRECCIONAL_DUAL
    permitir_long: bool = True
    permitir_short: bool = True
    timestamp_actualizacion: float = dataclasses.field(default_factory=time.time)
    quarantine_until: float = 0.0
    cooldown_until: float = 0.0
    step_lock_short_price: float = 0.0
    step_lock_short_until: float = 0.0
    motivo_ultimo_bloqueo: str = "OK"

    def sincronizar_banderas(self) -> None:
        if not self.habilitado or self.modo_direccional == MODO_DIRECCIONAL_VETO:
            self.permitir_long = False
            self.permitir_short = False
        elif self.modo_direccional == MODO_DIRECCIONAL_SOLO_LONG:
            self.permitir_long = True
            self.permitir_short = False
        elif self.modo_direccional == MODO_DIRECCIONAL_SOLO_SHORT:
            self.permitir_long = False
            self.permitir_short = True
        else:
            self.permitir_long = True
            self.permitir_short = True


@dataclasses.dataclass(slots=True)
class MetricaTick:
    symbol: str
    timestamp: float = dataclasses.field(default_factory=time.time)
    bid: float = 0.0
    ask: float = 0.0
    bid_qty: float = 0.0
    ask_qty: float = 0.0
    mid: float = 0.0
    micro_price: float = 0.0
    spread_pct: float = 0.0
    z_score: float = 0.0
    dp_pct: float = 0.0
    ema_rapida: float = 0.0
    ema_macro: float = 0.0
    ema900_dist_pct: float = 0.0
    ema900_slope_pct: float = 0.0
    ofi_profundo: float = 0.0
    ofi_5s: float = 0.0
    ofi_ticks_consecutivos: int = 0
    hurst: float = 0.42
    aceleracion_lyapunov: float = 0.0
    intensidad_hawkes: float = 0.0
    vpin: float = 0.05
    volatilidad_bv: float = cfg.VOLATILIDAD_BV_PISO_MIN
    percentil_24h: float = 0.50
    ultimo_shock_lyapunov_ts: float = 0.0
    ultimo_pulso_toxico_hawkes_ts: float = 0.0
    phase_latched: bool = False
    phase_latch_ts: float = 0.0
    phase_latch_dir: str = ""
    phase_latch_z_peak: float = 0.0
    phase_latch_ema_dist: float = 0.0


@dataclasses.dataclass(slots=True)
class PosicionActiva:
    symbol: str
    side: str
    contratos: float
    contratos_iniciales: float
    precio_entrada: float
    timestamp_apertura: float = dataclasses.field(default_factory=time.time)
    orden_entrada_id: str = ""
    sl_interno: float = 0.0
    sl_bybit: float = 0.0
    tp_dinamico_pct: float = cfg.COSECHA_TRIZ_ACTIVACION_PCT
    trinquete_be_activo: bool = False
    cosecha_activa: bool = False
    cosecha_50_ejecutada: bool = False
    trailing_activo: bool = False
    max_precio_favorable: float = 0.0
    min_precio_adverso: float = 0.0
    max_pnl_pct_alcanzado: float = 0.0
    min_pnl_pct_alcanzado: float = 0.0
    pnl_realizado_parcial_usdt: float = 0.0
    fees_acumulados_usdt: float = 0.0
    es_entrada_maker: bool = True
    cerrada: bool = False
    en_proceso_cierre: bool = False
    orden_salida_id: str = ""
    ts_orden_salida: float = 0.0
    precio_orden_salida: float = 0.0
    motivo_salida_pendiente: str = ""
    ultimo_repeg_salida_ts: float = 0.0
    ultimo_poll_salida_ts: float = 0.0
    repeg_salida_count: int = 0
    kelly_usado: float = cfg.KELLY_FRACCION_BASE
    z_entrada: float = 0.0
    ofi_entrada: float = 0.0
    hurst_entrada: float = 0.42
    hawkes_entrada: float = 0.0
    lyapunov_entrada: float = 0.0
    ema900_entrada_pct: float = 0.0
    dp_entrada_pct: float = 0.0
    volatilidad_bv_entrada: float = cfg.VOLATILIDAD_BV_PISO_MIN
    percentil_entrada: float = 0.50
    latencia_rtt_ms: float = 0.0
    lambda_wald: float = 0.0
    trayectoria_pnl: Dict[str, float] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_precio_favorable <= 0.0:
            self.max_precio_favorable = self.precio_entrada
        if self.min_precio_adverso <= 0.0:
            self.min_precio_adverso = self.precio_entrada

    @property
    def direccion(self) -> str:
        s = self.side.upper()
        if s in ("BUY", "LONG"):
            return "LONG"
        return "SHORT"

    @property
    def nocional_entrada_usdt(self) -> float:
        return abs(self.contratos_iniciales * self.precio_entrada)

    @property
    def nocional_actual_usdt(self) -> float:
        return abs(self.contratos * self.precio_entrada)

    def calcular_pnl_bruto_pct(self, precio_actual: float) -> float:
        if self.precio_entrada <= 0.0 or precio_actual <= 0.0:
            return 0.0
        if self.direccion == "LONG":
            return (precio_actual - self.precio_entrada) / self.precio_entrada
        return (self.precio_entrada - precio_actual) / self.precio_entrada

    def actualizar_excursion(self, precio_actual: float, ahora: Optional[float] = None) -> float:
        pnl_pct = self.calcular_pnl_bruto_pct(precio_actual)
        if self.direccion == "LONG":
            if precio_actual > self.max_precio_favorable:
                self.max_precio_favorable = precio_actual
            if precio_actual < self.min_precio_adverso or self.min_precio_adverso <= 0.0:
                self.min_precio_adverso = precio_actual
        else:
            if precio_actual < self.max_precio_favorable or self.max_precio_favorable <= 0.0:
                self.max_precio_favorable = precio_actual
            if precio_actual > self.min_precio_adverso:
                self.min_precio_adverso = precio_actual

        if pnl_pct > self.max_pnl_pct_alcanzado:
            self.max_pnl_pct_alcanzado = pnl_pct
        if pnl_pct < self.min_pnl_pct_alcanzado:
            self.min_pnl_pct_alcanzado = pnl_pct

        ts_now = ahora if ahora is not None else time.time()
        edad = ts_now - self.timestamp_apertura
        for h_seg, key in ((5.0, "5s"), (15.0, "15s"), (18.0, "18s"), (30.0, "30s"), (45.0, "45s")):
            if edad >= h_seg and key not in self.trayectoria_pnl:
                self.trayectoria_pnl[key] = round(pnl_pct * 100.0, 4)
        return pnl_pct


@dataclasses.dataclass(slots=True)
class EventoForensePendiente:
    timestamp: float
    symbol: str
    direccion: str
    escudo: str
    motivo: str
    precio_ref: float
    vector_mercado: Dict[str, Any]


@dataclasses.dataclass(slots=True)
class EventoPostCierrePendiente:
    timestamp_cierre: float
    trade_id: int
    symbol: str
    side: str
    motivo_salida: str
    precio_entrada: float
    precio_salida: float
    pnl_usdt: float
    pnl_pct: float
    map_usdt: float
    px_15s: float = 0.0
    px_30s: float = 0.0



class EstadoGlobalRAM:
    """
    Deterministic O(1) in-memory state store for Doctor Blythe Terpsichora V1.0.
    Guarantees sub-microsecond permission lookup and lock-free L2 telemetry access.
    """

    def __init__(self) -> None:
        self.whitelist_pares: Dict[str, PermisoParRAM] = {}
        self.metricas_ticks: Dict[str, MetricaTick] = {}
        self.posiciones_activas: Dict[str, PosicionActiva] = {}
        self.locks_pre_fill: Dict[str, float] = {}
        self.eventos_colapso_recientes: Dict[str, float] = {}
        self.cola_forense_15s: Deque[EventoForensePendiente] = collections.deque(maxlen=256)
        self.cola_post_cierre_60s: Deque[EventoPostCierrePendiente] = collections.deque(maxlen=128)
        self.capital_total_uta: float = cfg.CAPITAL_BASE_HISTORICO_USDT
        self.capital_libre_uta: float = cfg.CAPITAL_BASE_HISTORICO_USDT
        self.capital_bloqueado_uta: float = 0.0
        self.multiplicador_kelly_ia: float = cfg.MULTIPLICADOR_IA_DEFAULT
        self.modelo_lpu_activo: str = "allam-2-7b"
        self.pausa_macro_hasta: float = 0.0
        self.btc_veto_long_hasta: float = 0.0
        self.btc_veto_short_hasta: float = 0.0
        self.ultimo_sync_uta_ts: float = 0.0
        self.controlador_autonomo: Dict[str, float] = {
            "w1_ofi_long": cfg.OFI_MIN_ENTRADA,
            "w2_btc_beta": cfg.BTC_VETO_OFI_UMBRAL,
            "w3_tp_maker_pct": cfg.COSECHA_TRIZ_ACTIVACION_PCT,
            "w4_unwind_seg": float(cfg.obtener_aux("EARLY_UNWIND_TIEMPO_SEG", 42.0)),
            "w4_sl_decay_pct": 0.0032,
            "w5_kelly_short": cfg.KELLY_SHORT_SNIPER_FRACCION,
            "w5_kelly_long": cfg.KELLY_LONG_TIER1_FRACCION,
            "hurst_cap_short_mod": cfg.HURST_MAX_ENTRADA_SHORT,
            "mfe_stall_harvest_pct": cfg.COSECHA_ESTANCAMIENTO_MFE_PCT,
            "sesgo_escudo_long": 0.0,
            "sesgo_escudo_short": 0.0,
            "sens_ofi_abort_cola": -0.35,
            "sens_q_l1_hold_ratio": 0.55,
            "sens_scratch_edad_rebote_seg": 32.0,
            "sens_climax_hurst_override": 1.0,
        }
        self.inicializar_whitelist_campeones()

    def inicializar_whitelist_campeones(self) -> None:
        self.whitelist_pares.clear()
        self.eventos_colapso_recientes.clear()
        self.locks_pre_fill.clear()
        self.pausa_macro_hasta = 0.0
        self.btc_veto_long_hasta = 0.0
        self.btc_veto_short_hasta = 0.0
        for par in cfg.UNIVERSO_PARES_TOTAL:
            self.whitelist_pares[par] = PermisoParRAM(symbol=par)
            if par not in self.metricas_ticks:
                self.metricas_ticks[par] = MetricaTick(symbol=par)
        if not (sys.argv and sys.argv[0] == "-c"):
            log_operativo(
                f"[RAM SHIELD] O(1) Whitelist initialized with {len(cfg.PARES_CAMPEONES)} "
                f"Alpha Champion pairs (+1 Macro Leader)."
            )

    @property
    def total_usdt(self) -> float:
        return self.capital_total_uta

    @property
    def free_usdt(self) -> float:
        return self.capital_libre_uta

    @property
    def locked_usdt(self) -> float:
        return self.capital_bloqueado_uta

    def actualizar_auditoria_uta(self, total: float, free: float, locked: Optional[float] = None) -> None:
        self.capital_total_uta = max(0.0, float(total))
        self.capital_libre_uta = max(0.0, float(free))
        if locked is not None:
            self.capital_bloqueado_uta = max(0.0, float(locked))
        else:
            self.capital_bloqueado_uta = max(0.0, self.capital_total_uta - self.capital_libre_uta)
        self.ultimo_sync_uta_ts = time.time()

    def consultar_permiso_o1(
        self,
        symbol: str,
        direccion: str = "LONG",
        ahora: Optional[float] = None,
    ) -> Tuple[bool, str]:
        ahora = float(ahora) if ahora is not None else time.time()
        if ahora < self.pausa_macro_hasta:
            return False, "MACRO_CONTAGION_PAUSE"

        perm = self.whitelist_pares.get(symbol)
        if perm is None:
            return False, "SYMBOL_NOT_WHITELISTED"

        if not perm.habilitado or perm.modo_direccional == MODO_DIRECCIONAL_VETO:
            return False, "VETO_TOXIC_LPU"

        if ahora < perm.quarantine_until:
            rem = int(perm.quarantine_until - ahora)
            return False, f"ACTIVE_QUARANTINE_{rem}S"

        if ahora < perm.cooldown_until:
            rem = int(perm.cooldown_until - ahora)
            return False, f"ACTIVE_QUARANTINE_{rem}S"

        dir_norm = direccion.upper()
        if dir_norm in ("BUY", "LONG"):
            if ahora < self.btc_veto_long_hasta:
                return False, "BTC_MACRO_COOLDOWN_LONG"
            if not perm.permitir_long:
                return False, f"LPU_MODE_{perm.modo_direccional}"
        else:
            if ahora < self.btc_veto_short_hasta:
                return False, "BTC_MACRO_COOLDOWN_SHORT"
            if not perm.permitir_short:
                return False, f"LPU_MODE_{perm.modo_direccional}"

        return True, "APPROVED"

    def aplicar_matriz_direccional_lpu(self, symbol: str, modo: str, motivo: str = "LPU_SYNC") -> None:
        perm = self.whitelist_pares.get(symbol)
        if perm is None:
            perm = PermisoParRAM(symbol=symbol)
            self.whitelist_pares[symbol] = perm
        perm.modo_direccional = modo
        perm.habilitado = modo != MODO_DIRECCIONAL_VETO
        perm.motivo_ultimo_bloqueo = motivo
        perm.timestamp_actualizacion = time.time()
        perm.sincronizar_banderas()

    def activar_cuarentena_par(self, symbol: str, segundos: float, motivo: str = "POST_LOSS_QUARANTINE") -> None:
        perm = self.whitelist_pares.get(symbol)
        if perm is not None:
            perm.quarantine_until = max(perm.quarantine_until, time.time() + max(0.0, segundos))
            perm.motivo_ultimo_bloqueo = motivo

    def activar_cooldown_par(self, symbol: str, segundos: float, motivo: str = "POST_CLOSE_COOLDOWN") -> None:
        perm = self.whitelist_pares.get(symbol)
        if perm is not None:
            perm.cooldown_until = max(perm.cooldown_until, time.time() + max(0.0, segundos))
            perm.motivo_ultimo_bloqueo = motivo

    def adquirir_lock_pre_fill(self, symbol: str, ttl_seg: float = 6.0) -> bool:
        ahora = time.time()
        expira = self.locks_pre_fill.get(symbol, 0.0)
        if ahora < expira or symbol in self.posiciones_activas:
            return False
        self.locks_pre_fill[symbol] = ahora + ttl_seg
        return True

    def liberar_lock_pre_fill(self, symbol: str) -> None:
        self.locks_pre_fill.pop(symbol, None)

    def tiene_capacidad_slot(self, direccion: str = "LONG") -> bool:
        activas = [p for p in self.posiciones_activas.values() if not p.cerrada]
        if len(activas) >= cfg.SLOTS_CONCURRENTES_MAX:
            return False
        dir_norm = "LONG" if direccion.upper() in ("BUY", "LONG") else "SHORT"
        misma_dir = [p for p in activas if p.direccion == dir_norm]
        return len(misma_dir) < cfg.MAX_POSICIONES_POR_DIRECCION

    def registrar_evento_colapso(self, symbol: str, ahora: Optional[float] = None) -> Tuple[bool, List[str]]:
        ts = ahora if ahora is not None else time.time()
        self.eventos_colapso_recientes[symbol] = ts
        ventana = cfg.CONTAGIO_VENTANA_SEG
        activos = [
            par for par, t_ev in list(self.eventos_colapso_recientes.items())
            if (ts - t_ev) <= ventana and par != cfg.PAR_LIDER_MACRO
        ]
        activos.sort()
        if len(activos) >= cfg.CONTAGIO_PARES_SIMULTANEOS:
            self.pausa_macro_hasta = max(self.pausa_macro_hasta, ts + cfg.PAUSA_MACRO_CONTAGIO_SEG)
            return True, activos
        return False, activos

    def encolar_auditoria_forense_15s(
        self,
        symbol: str,
        direccion: str,
        escudo: str,
        motivo: str,
        precio_ref: float,
        vector_mercado: Optional[Dict[str, Any]] = None,
    ) -> None:
        if precio_ref <= 0.0:
            return
        for ev in self.cola_forense_15s:
            if ev.symbol == symbol and ev.escudo == escudo and (time.time() - ev.timestamp) < 4.0:
                return
        self.cola_forense_15s.append(
            EventoForensePendiente(
                timestamp=time.time(),
                symbol=symbol,
                direccion=direccion,
                escudo=escudo,
                motivo=motivo,
                precio_ref=precio_ref,
                vector_mercado=dict(vector_mercado or {}),
            )
        )

    def procesar_cola_forense_15s(self, ahora: Optional[float] = None) -> int:
        ts_now = ahora if ahora is not None else time.time()
        procesados = 0
        while self.cola_forense_15s and (ts_now - self.cola_forense_15s[0].timestamp) >= 15.0:
            ev = self.cola_forense_15s.popleft()
            m = self.metricas_ticks.get(ev.symbol)
            precio_15s = m.mid if (m and m.mid > 0.0) else ev.precio_ref
            if ev.direccion.upper() in ("BUY", "LONG"):
                excursion_pct = (precio_15s - ev.precio_ref) / ev.precio_ref
            else:
                excursion_pct = (ev.precio_ref - precio_15s) / ev.precio_ref

            if excursion_pct <= -0.0018:
                veredicto = "CAPITAL_SAVED_TRUE_SHIELD"
            elif excursion_pct >= 0.0024:
                veredicto = "FALSE_REJECTION_OPPORTUNITY_LOST"
            else:
                veredicto = "NEUTRAL_CHOP_FILTERED"

            registro = {
                "tipo_evento": "AUDITORIA_ESCUDO_15S",
                "timestamp": round(ev.timestamp, 3),
                "fecha_utc": datetime.datetime.fromtimestamp(ev.timestamp, _TZ_UTC).strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": ev.symbol,
                "direccion": ev.direccion,
                "escudo": ev.escudo,
                "motivo": ev.motivo,
                "precio_bloqueo": ev.precio_ref,
                "precio_15s": precio_15s,
                "excursion_15s_pct": round(excursion_pct * 100.0, 4),
                "ahorro_estimado_usdt": round(max(0.0, -excursion_pct) * 15.5, 4),
                "veredicto_oraculo_15s": veredicto,
                "vector_entrada": ev.vector_mercado,
            }
            guardar_registro_baul_forense(registro)
            procesados += 1
        procesados += self.procesar_cola_post_cierre_60s(ts_now)
        return procesados

    def encolar_auditoria_post_cierre(self, registro_trade: Dict[str, Any]) -> None:
        try:
            px_out = float(registro_trade.get("precio_salida", 0.0))
            if px_out <= 0.0:
                return
            self.cola_post_cierre_60s.append(
                EventoPostCierrePendiente(
                    timestamp_cierre=float(registro_trade.get("timestamp", time.time())),
                    trade_id=int(registro_trade.get("trade_id", 0)),
                    symbol=str(registro_trade.get("symbol", "")),
                    side=str(registro_trade.get("side", "LONG")),
                    motivo_salida=str(registro_trade.get("motivo_salida", "")),
                    precio_entrada=float(registro_trade.get("precio_entrada", px_out)),
                    precio_salida=px_out,
                    pnl_usdt=float(registro_trade.get("pnl_usdt", 0.0)),
                    pnl_pct=float(registro_trade.get("pnl_pct", 0.0)),
                    map_usdt=float(registro_trade.get("map_usdt", 15.5) or 15.5),
                )
            )
        except Exception:
            pass

    def procesar_cola_post_cierre_60s(self, ahora: Optional[float] = None) -> int:
        ts_now = ahora if ahora is not None else time.time()
        completados = 0
        for ev in list(self.cola_post_cierre_60s):
            edad = ts_now - ev.timestamp_cierre
            m = self.metricas_ticks.get(ev.symbol)
            px_now = m.mid if (m and m.mid > 0.0) else ev.precio_salida
            if edad >= 15.0 and ev.px_15s <= 0.0:
                ev.px_15s = px_now
            if edad >= 30.0 and ev.px_30s <= 0.0:
                ev.px_30s = px_now

        while self.cola_post_cierre_60s and (ts_now - self.cola_post_cierre_60s[0].timestamp_cierre) >= 60.0:
            ev = self.cola_post_cierre_60s.popleft()
            m = self.metricas_ticks.get(ev.symbol)
            px_60s = m.mid if (m and m.mid > 0.0) else ev.precio_salida
            px_15 = ev.px_15s if ev.px_15s > 0.0 else px_60s
            px_30 = ev.px_30s if ev.px_30s > 0.0 else px_60s
            es_long = ev.side.upper() in ("BUY", "LONG")
            signo = 1.0 if es_long else -1.0

            cont_15 = signo * ((px_15 - ev.precio_salida) / ev.precio_salida) * 100.0
            cont_30 = signo * ((px_30 - ev.precio_salida) / ev.precio_salida) * 100.0
            cont_60 = signo * ((px_60s - ev.precio_salida) / ev.precio_salida) * 100.0

            es_sc = "SCRATCH" in ev.motivo_salida.upper()
            ahorro_sc = 0.0
            if es_sc and cont_60 < 0.0:
                ahorro_sc = round(abs(cont_60 / 100.0) * ev.map_usdt, 4)

            if es_sc:
                veredicto = "SCRATCH_SAVED_DUMP" if cont_60 <= -0.08 else ("SCRATCH_EARLY_REBOUND" if cont_60 >= 0.18 else "SCRATCH_NEUTRAL")
            elif ev.pnl_usdt > 0.0:
                veredicto = "WALD_CREST_OPTIMAL" if cont_30 <= 0.05 else "WALD_RUNNER_CONTINUED"
            else:
                veredicto = "LOSS_CONTAINED"

            guardar_registro_baul_forense(
                {
                    "tipo_evento": "AUDITORIA_POST_CIERRE_60S",
                    "timestamp": round(ts_now, 3),
                    "fecha_utc": datetime.datetime.fromtimestamp(ts_now, _TZ_UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    "trade_id": ev.trade_id,
                    "symbol": ev.symbol,
                    "side": ev.side,
                    "motivo_salida": ev.motivo_salida,
                    "precio_entrada": ev.precio_entrada,
                    "precio_salida": ev.precio_salida,
                    "pnl_usdt": ev.pnl_usdt,
                    "continuation_15s_pct": round(cont_15, 4),
                    "continuation_30s_pct": round(cont_30, 4),
                    "continuation_60s_pct": round(cont_60, 4),
                    "ahorro_post_scratch_usdt": ahorro_sc,
                    "veredicto_post_cierre": veredicto,
                }
            )
            completados += 1
        return completados


def guardar_registro_baul_forense(registro: Dict[str, Any]) -> None:
    if cfg.es_modo_test():
        return
    try:
        ruta = cfg.obtener_ruta_archivo("ARCHIVO_BAUL_IA_JSONL")
        with open(ruta, mode="a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=True) + "\n")
    except Exception:
        pass


ESTADO_GLOBAL = EstadoGlobalRAM()
