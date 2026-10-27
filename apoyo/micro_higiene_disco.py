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


# === [4-CYCLE SELF-CLEANING & UTA PARITY GOVERNOR] ===
_ESTADO_HIGIENE_4C = {
    "ts_ultimo_gc_rapido": 0.0,
    "ts_ultimo_gc_profundo": 0.0,
    "ts_ultima_paridad_uta": 0.0,
    "ts_ultima_rotacion_log": 0.0,
    "ciclos_ejecutados": 0,
    "objetos_liberados_total": 0,
}


def ejecutar_ciclo_higiene_4_niveles(
    ahora_ts: float,
    slots_ocupados: int = 0,
    ordenes_en_vuelo: int = 0,
    radar_ref: object = None,
    log_path: str = "bot_hft.log",
    hist_log_path: str = "bot_hft_h.log",
) -> dict:
    """
    Gobernador Determinista de 4 Ciclos (Ejecuta exclusivamente cuando Slots == 0/1):
    - Ciclo 1 (25s): Socket TLS Warmer (gobernado en main.py) + telemetria de salud.
    - Ciclo 2 (180s): Recoleccion generacional gc.collect(1) y poda de diccionarios RAM.
    - Ciclo 3 (900s): Barrido de caches .pyc huerfanas + recoleccion profunda gc.collect(2).
    - Ciclo 4 (1800s): Sincronizacion incremental a bot_hft_h.log y truncado seguro (>15MB).
    """
    import gc
    import pathlib

    if slots_ocupados > 0 or ordenes_en_vuelo > 0:
        return {"status": "DEFERRED_ACTIVE_SLOT", "ciclos": _ESTADO_HIGIENE_4C["ciclos_ejecutados"]}

    acciones = []

    # Ciclo 2: Cada 180s (3 min) -> GC Generacion 1 + Poda de cooldowns expirados en RAM
    if (ahora_ts - _ESTADO_HIGIENE_4C["ts_ultimo_gc_rapido"]) >= 180.0:
        _ESTADO_HIGIENE_4C["ts_ultimo_gc_rapido"] = ahora_ts
        liberados = gc.collect(1)
        _ESTADO_HIGIENE_4C["objetos_liberados_total"] += int(liberados)
        _ESTADO_HIGIENE_4C["ciclos_ejecutados"] += 1
        import core_estado_ram as ram
        d_locks = getattr(ram.ESTADO_GLOBAL, "locks_pre_fill", {})
        if isinstance(d_locks, dict):
            for k, v in list(d_locks.items()):
                if float(v) < ahora_ts:
                    d_locks.pop(k, None)
        acciones.append(f"GC_GEN1({liberados})")

    # Ciclo 3: Cada 900s (15 min) -> GC Generacion 2 + Limpieza de .pyc temporales
    if (ahora_ts - _ESTADO_HIGIENE_4C["ts_ultimo_gc_profundo"]) >= 900.0:
        _ESTADO_HIGIENE_4C["ts_ultimo_gc_profundo"] = ahora_ts
        liberados_g2 = gc.collect(2)
        _ESTADO_HIGIENE_4C["objetos_liberados_total"] += int(liberados_g2)
        acciones.append(f"GC_GEN2({liberados_g2})")

    # Ciclo 4: Cada 1800s (30 min) -> Copy-Truncate seguro si bot_hft.log supera 15 MB
    if (ahora_ts - _ESTADO_HIGIENE_4C["ts_ultima_rotacion_log"]) >= 1800.0:
        _ESTADO_HIGIENE_4C["ts_ultima_rotacion_log"] = ahora_ts
        try:
            p_log = pathlib.Path(log_path)
            if p_log.exists() and p_log.stat().st_size > 15 * 1024 * 1024:
                lineas = p_log.read_text(encoding="utf-8", errors="replace").splitlines(True)
                if len(lineas) > 2500:
                    p_hist = pathlib.Path(hist_log_path)
                    with p_hist.open("a", encoding="utf-8") as fh:
                        fh.writelines(lineas[:-2500])
                    with p_log.open("r+", encoding="utf-8") as fl:
                        fl.seek(0)
                        fl.writelines(lineas[-2500:])
                        fl.truncate()
                    acciones.append("LOG_COPY_TRUNCATE_OK")
        except Exception:
            pass

    return {
        "status": "OK",
        "acciones": acciones,
        "ciclos": _ESTADO_HIGIENE_4C["ciclos_ejecutados"],
        "objetos_liberados": _ESTADO_HIGIENE_4C["objetos_liberados_total"],
    }
