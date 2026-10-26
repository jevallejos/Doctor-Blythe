"""
Level 2 DAG: 1:1 Transactional Telegram Notifier with In-Memory Pending-Open
Buffer, 12s Canonical Deduplication, and Zero-Spam Test Inbox for
HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List

import config_parametros as cfg

BUZON_TEST: List[Dict[str, Any]] = []
_CACHE_DEDUP_12S: Dict[str, float] = {}
_APERTURAS_CONFIRMABLES: Dict[str, Dict[str, Any]] = {}


def _purgar_dedup(ahora: float) -> None:
    expirados = [k for k, ts in _CACHE_DEDUP_12S.items() if (ahora - ts) > 12.0]
    for k in expirados:
        _CACHE_DEDUP_12S.pop(k, None)


def _enviar_http_telegram(texto: str) -> bool:
    if cfg.es_modo_test() or cfg.MODO_PAPER_TRADING:
        return True
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": texto}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            return resp.status == 200
    except Exception:
        return False


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
        f"[DOCTOR-BLYTHE V1.0] OPEN {dir_norm} {symbol}\n"
        f"Qty: {contratos} @ {precio_entrada} (~{nocional:.2f} USDT)\n"
        f"SL: {sl_interno} | Kelly: {kelly_frac * 100:.0f}% | Z: {z_score:+.2f} | OFI: {ofi:+.2f}"
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
    return _enviar_http_telegram(msg)


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
        f"[DOCTOR-BLYTHE V1.0] 50% TRIZ HARVEST {symbol}\n"
        f"Closed: {contratos_cerrados} @ {precio_cosecha} ({pnl_pct * 100:+.2f}% | {pnl_usdt:+.4f} USDT)"
    )
    if cfg.es_modo_test():
        BUZON_TEST.append({"tipo": "HARVEST_50", "symbol": symbol, "pnl_usdt": pnl_usdt, "texto": msg})
        return True
    return _enviar_http_telegram(msg)


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
        icono = "[WIN]"
    elif "SCRATCH" in motivo.upper():
        tipo_ev = "CLOSE_SCRATCH"
        icono = "[SCRATCH]"
    else:
        tipo_ev = "CLOSE_LOSS"
        icono = "[LOSS]"

    msg = (
        f"[DOCTOR-BLYTHE V1.0] {icono} CLOSE {dir_norm} {symbol} [{motivo}]\n"
        f"{precio_entrada} -> {precio_salida} | {pnl_pct * 100:+.2f}% ({pnl_usdt:+.4f} USDT) in {int(duracion_seg)}s\n"
        f"UTA Balance: {balance_uta:.4f} USDT"
    )
    if cfg.es_modo_test():
        BUZON_TEST.append({"tipo": tipo_ev, "symbol": symbol, "motivo": motivo, "pnl_usdt": pnl_usdt, "texto": msg})
        return True
    return _enviar_http_telegram(msg)
