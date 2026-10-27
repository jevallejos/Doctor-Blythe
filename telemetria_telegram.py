"""
Level 2 DAG: Non-Blocking 1:1 Transactional Telegram Notifier with Startup Service Alert,
12s Canonical Deduplication, Bounded Background Executor Dispatch, Status Icons,
and Zero-Spam Test Inbox for HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import urllib.request
from typing import Any, Dict, List, Tuple
from dotenv import load_dotenv

import config_parametros as cfg
import core_estado_ram as ram

load_dotenv(cfg.obtener_ruta_base() / ".env")

ICONO_VERDE: str = "\U0001f7e9"
ICONO_ROJO: str = "\U0001f534"
ICONO_AMARILLO: str = "\U0001f7e8"
ICONO_DIAMANTE: str = "\U0001f48e"
ICONO_COHETE: str = "\U0001f680"

BUZON_TEST: List[Dict[str, Any]] = []
_CACHE_DEDUP_12S: Dict[str, float] = {}
_APERTURAS_CONFIRMABLES: Dict[str, Dict[str, Any]] = {}
_CREDENCIALES_CACHE: Tuple[str, str] | None = None
_EXECUTOR_TELEGRAM = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tg_nonblock")


def _purgar_dedup(ahora: float) -> None:
    expirados = [k for k, ts in _CACHE_DEDUP_12S.items() if (ahora - ts) > 12.0]
    for k in expirados:
        _CACHE_DEDUP_12S.pop(k, None)


def _obtener_credenciales_telegram() -> Tuple[str, str]:
    global _CREDENCIALES_CACHE
    if _CREDENCIALES_CACHE is not None and _CREDENCIALES_CACHE[0] and _CREDENCIALES_CACHE[1]:
        return _CREDENCIALES_CACHE
    token = (
        os.environ.get("TELEGRAM_BOT_TOKEN")
        or os.environ.get("TELEGRAM_TOKEN")
        or ""
    ).strip()
    chat_id = (
        os.environ.get("TELEGRAM_CHAT_ID")
        or os.environ.get("CHAT_ID")
        or ""
    ).strip()
    if token and chat_id:
        _CREDENCIALES_CACHE = (token, chat_id)
    return token, chat_id


def _enviar_http_telegram_sync(url: str, body: bytes) -> bool:
    for intento in range(2):
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status == 200:
                    return True
        except Exception as exc:
            if intento == 1:
                ram.log_operativo(f"[WARN] [TELEGRAM NET ERROR] {exc}")
    return False


def _enviar_http_telegram(texto: str, bloqueante: bool = False) -> bool:
    if cfg.es_modo_test() or cfg.MODO_PAPER_TRADING:
        return True
    token, chat_id = _obtener_credenciales_telegram()
    if not token or not chat_id:
        ram.log_operativo("[WARN] [TELEGRAM] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": texto}).encode("utf-8")
    if bloqueante:
        return _enviar_http_telegram_sync(url, body)
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(_EXECUTOR_TELEGRAM, _enviar_http_telegram_sync, url, body)
        return True
    except RuntimeError:
        return _enviar_http_telegram_sync(url, body)


def notificar_inicio_servicio(
    total_usdt: float,
    free_usdt: float,
    nocional_usdt: float,
    pid: int,
) -> bool:
    msg = (
        f"{ICONO_COHETE} [DOCTOR-BLYTHE TERPSICHORA V1.0 ONLINE]\n"
        f"PID: {pid} | Radar: {cfg.FRECUENCIA_RADAR_HZ:.1f}Hz (L2 orderbook.50)\n"
        f"UTA Balance: {total_usdt:.4f} USDT (Free: {free_usdt:.4f} USDT)\n"
        f"Notional 3x: ~{nocional_usdt:.2f} USDT | Champions: {len(cfg.PARES_CAMPEONES)}\n"
        f"Z_HB: {cfg.Z_SCORE_UMBRAL_HIGH_BETA} | Z_T1: {cfg.Z_SCORE_UMBRAL_TIER1} | "
        f"EarlyBE: +{cfg.COSECHA_ESTANCAMIENTO_MFE_PCT * 100:.2f}% | Harvest: +{cfg.COSECHA_TRIZ_ACTIVACION_PCT * 100:.2f}%"
    )
    if cfg.es_modo_test():
        BUZON_TEST.append({"tipo": "BOOT", "symbol": "GLOBAL", "texto": msg})
        return True
    ok = _enviar_http_telegram(msg, bloqueante=False)
    if ok:
        ram.log_operativo("[TELEGRAM] Startup notification queued successfully.")
    return ok


def notificar_apertura_confirmada(
    symbol: str,
    side: str,
    contratos: float,
    precio_entrada: float,
    sl_interno: float,
    kelly_frac: float,
    z_score: float,
    ofi: float,
    orden_id: str = "",
) -> bool:
    ahora = time.time()
    _purgar_dedup(ahora)
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
    clave = f"OPEN:{symbol}:{dir_norm}:{round(precio_entrada, 6)}"
    if clave in _CACHE_DEDUP_12S:
        return False
    _CACHE_DEDUP_12S[clave] = ahora
    nocional = round(abs(contratos * precio_entrada), 2)
    msg = (
        f"{ICONO_VERDE} [DOCTOR-BLYTHE V1.0] OPEN {dir_norm} {symbol}\n"
        f"Qty: {contratos} @ {precio_entrada} (~{nocional:.2f} USDT)\n"
        f"SL: {sl_interno} | Kelly: {kelly_frac * 100:.0f}% | Z: {z_score:+.2f} | OFI: {ofi:+.2f}\n"
        f"ID: {orden_id}"
    )
    _APERTURAS_CONFIRMABLES[symbol] = {
        "symbol": symbol,
        "side": dir_norm,
        "precio_entrada": precio_entrada,
        "orden_id": orden_id,
        "timestamp": ahora,
    }
    if cfg.es_modo_test():
        BUZON_TEST.append({"tipo": "OPEN", "symbol": symbol, "side": dir_norm, "texto": msg})
        return True
    return _enviar_http_telegram(msg, bloqueante=False)


def notificar_cosecha_parcial(
    symbol: str,
    contratos_cerrados: float,
    precio_cosecha: float,
    pnl_pct: float,
    pnl_usdt: float,
) -> bool:
    ahora = time.time()
    _purgar_dedup(ahora)
    clave = f"HARVEST50:{symbol}:{round(precio_cosecha, 6)}"
    if clave in _CACHE_DEDUP_12S:
        return False
    _CACHE_DEDUP_12S[clave] = ahora
    msg = (
        f"{ICONO_DIAMANTE} [DOCTOR-BLYTHE V1.0] 50% TRIZ HARVEST {symbol}\n"
        f"Closed: {contratos_cerrados} @ {precio_cosecha} ({pnl_pct * 100:+.2f}% | {pnl_usdt:+.4f} USDT)"
    )
    if cfg.es_modo_test():
        BUZON_TEST.append({"tipo": "HARVEST_50", "symbol": symbol, "pnl_usdt": pnl_usdt, "texto": msg})
        return True
    return _enviar_http_telegram(msg, bloqueante=False)


def notificar_cierre_confirmado(
    symbol: str,
    side: str,
    precio_entrada: float,
    precio_salida: float,
    pnl_pct: float,
    pnl_usdt: float,
    motivo: str,
    duracion_seg: float,
    balance_uta: float,
) -> bool:
    ahora = time.time()
    _purgar_dedup(ahora)
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
    clave = f"CLOSE:{symbol}:{dir_norm}:{motivo}:{round(pnl_usdt, 4)}"
    if clave in _CACHE_DEDUP_12S:
        return False
    _CACHE_DEDUP_12S[clave] = ahora
    _APERTURAS_CONFIRMABLES.pop(symbol, None)
    if pnl_usdt > 0.0:
        tipo_ev = "CLOSE_WIN"
        icono = f"{ICONO_VERDE} [WIN]"
    elif "SCRATCH" in motivo.upper():
        tipo_ev = "CLOSE_SCRATCH"
        icono = f"{ICONO_AMARILLO} [SCRATCH]"
    else:
        tipo_ev = "CLOSE_LOSS"
        icono = f"{ICONO_ROJO} [LOSS]"
    msg = (
        f"{icono} [DOCTOR-BLYTHE V1.0] CLOSE {dir_norm} {symbol} [{motivo}]\n"
        f"{precio_entrada} -> {precio_salida} | {pnl_pct * 100:+.2f}% ({pnl_usdt:+.4f} USDT) in {int(duracion_seg)}s\n"
        f"UTA Balance: {balance_uta:.4f} USDT"
    )
    if cfg.es_modo_test():
        BUZON_TEST.append({"tipo": tipo_ev, "symbol": symbol, "motivo": motivo, "pnl_usdt": pnl_usdt, "texto": msg})
        return True
    return _enviar_http_telegram(msg, bloqueante=False)


def notificar_digest_ejecutivo(
    resumen_stats: Dict[str, Any],
    salvamentos_15s: int,
    ahorro_escudos_usdt: float,
) -> bool:
    msg = (
        f"{ICONO_DIAMANTE} [DOCTOR-BLYTHE V1.0 - 4H EXECUTIVE DIGEST]\n"
        f"UTA Balance: {resumen_stats.get('real_usdt', 0.0):.4f} USDT (1:1 Parity)\n"
        f"Session Trades: {resumen_stats.get('trades', 0)} "
        f"(W:{resumen_stats.get('wins', 0)} / L:{resumen_stats.get('losses', 0)} / S:{resumen_stats.get('scratches', 0)})\n"
        f"Net PnL: {resumen_stats.get('total_pnl_usdt', 0.0):+.4f} USDT | LVR: {resumen_stats.get('lvr', 0.0):.4f}\n"
        f"Shield Interceptions (+15s): {salvamentos_15s} saved (+{ahorro_escudos_usdt:.4f} USDT est.)"
    )
    if cfg.es_modo_test():
        BUZON_TEST.append({"tipo": "DIGEST_4H", "symbol": "GLOBAL", "texto": msg})
        return True
    return _enviar_http_telegram(msg, bloqueante=False)
