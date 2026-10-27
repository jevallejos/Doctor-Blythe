# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #5: Higiene Automatica de Disco (Log Rotation .gz Zero-Jitter)
y Compactacion de Memoria cuando Slots == 0/1.
"""
import datetime
import gc
import gzip
import pathlib
import shutil
import time
from typing import Any
import config_parametros as cfg

_TZ_UTC = datetime.timezone.utc
_ULTIMA_HIGIENE_TS: float = 0.0
_LIMITE_BYTES_LOG: int = 15 * 1024 * 1024  # 15 MB


def ejecutar_mantenimiento_silencioso_disco(estado_ram: Any, forzar: bool = False) -> bool:
    """
    Verifica cada 15 minutos (solo cuando no hay posiciones abiertas ni locks pre-fill)
    si bot_hft.log o bot_hft_h.log superan 15 MB. De ser asi, comprime una copia en
    backups_epoca_anterior/ y trunca el archivo activo sin detener el demonio.
    """
    global _ULTIMA_HIGIENE_TS
    if cfg.es_modo_test():
        return False

    ahora = time.time()
    if not forzar and (ahora - _ULTIMA_HIGIENE_TS) < 900.0:
        return False

    pos_activas = getattr(estado_ram, "posiciones_activas", {}) or {}
    locks = getattr(estado_ram, "locks_pre_fill", {}) or {}
    if len(pos_activas) > 0 or len(locks) > 0:
        return False

    _ULTIMA_HIGIENE_TS = ahora
    rotado = False
    base_dir = cfg.obtener_ruta_base()
    backup_dir = base_dir / "backups_epoca_anterior"

    for clave in ("ARCHIVO_LOG", "ARCHIVO_LOG_HISTORICO"):
        ruta = cfg.obtener_ruta_archivo(clave)
        if not ruta.exists():
            continue
        try:
            tamano = ruta.stat().st_size
            if tamano < _LIMITE_BYTES_LOG:
                continue
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts_str = datetime.datetime.now(_TZ_UTC).strftime("%Y%m%d_%H%M%S")
            destino_gz = backup_dir / f"{ruta.name}.{ts_str}.gz"
            with open(ruta, "rb") as f_in, gzip.open(destino_gz, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
            with open(ruta, "r+", encoding="utf-8") as f_trunc:
                f_trunc.truncate(0)
            rotado = True
        except Exception:
            continue

    # Purgar colas de colapso antiguas (> 120s) en RAM
    eventos_col = getattr(estado_ram, "eventos_colapso_recientes", {})
    if isinstance(eventos_col, dict):
        expirados = [k for k, t_ev in list(eventos_col.items()) if (ahora - t_ev) > 120.0]
        for k in expirados:
            eventos_col.pop(k, None)

    # Ejecutar recoleccion rapida de generacion 0/1 fuera del camino critico (Slots == 0/1)
    try:
        gc.collect(1)
    except Exception:
        pass
    return rotado
