# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #5: Higiene Automatica de Disco en carpeta Logs/ (Rotacion
Diaria UTC + Por Tamano .gz Zero-Jitter con Reemplazo Atomico, Retencion
Estratificada de baul_ia_forense.jsonl [14d Cierres / 72h Escudos] y Purga 30d).
"""
import datetime
import gc
import gzip
import json
import os
import pathlib
import shutil
import tempfile
import time
from typing import Any, Dict, List

import config_parametros as cfg
import core_estado_ram as ram

_TZ_UTC = datetime.timezone.utc
_ULTIMA_HIGIENE_TS: float = 0.0
_LIMITE_BYTES_LOG: int = 15 * 1024 * 1024      # 15 MB tope intradia para .log
_LIMITE_BYTES_BAUL: int = 12 * 1024 * 1024     # 12 MB tope intradia para .jsonl
_RETENCION_TRADES_SEG: float = 14.0 * 86400.0  # 14 dias para CIERRE_OPERACION_REAL y POST_CIERRE_60S
_RETENCION_ESCUDOS_SEG: float = 3.0 * 86400.0  # 72 horas (3 dias) para AUDITORIA_ESCUDO_15S
_RETENCION_GZ_LOGS_SEG: float = 30.0 * 86400.0 # 30 dias de retencion fria en carpeta Logs/


class _GestorRotacionEstratificada:
    """Encapsula las operaciones atomicas de archivo sin exponer funciones huerfanas."""

    @staticmethod
    def purgar_locks_respetando_gracia(d_locks: Any, ahora_ts: float, gracia_seg: float = 6.0) -> int:
        if not isinstance(d_locks, dict):
            return 0
        vigentes = 0
        for k_lk, v_lk in list(d_locks.items()):
            if not isinstance(v_lk, (int, float)):
                d_locks.pop(k_lk, None)
                continue
            val = float(v_lk)
            if val > 0.0:
                if ahora_ts < val:
                    vigentes += 1
                else:
                    d_locks.pop(k_lk, None)
            else:
                if (ahora_ts - abs(val)) <= gracia_seg:
                    vigentes += 1
                else:
                    d_locks.pop(k_lk, None)
        return vigentes

    @staticmethod
    def reemplazar_lineas_atomico(ruta: pathlib.Path, lineas: List[str]) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_str = tempfile.mkstemp(prefix=f".tmp_{ruta.name}_", dir=str(ruta.parent))
        tmp_path = pathlib.Path(tmp_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.writelines(lineas)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(str(tmp_path), str(ruta))
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    @classmethod
    def compactar_baul_estratificado(
        cls,
        ruta_baul: pathlib.Path,
        logs_dir: pathlib.Path,
        ahora_ts: float,
        forzar_diario: bool = False,
    ) -> bool:
        if not ruta_baul.exists():
            return False
        try:
            tamano = ruta_baul.stat().st_size
            if tamano == 0:
                return False
            if not forzar_diario and tamano < _LIMITE_BYTES_BAUL:
                return False

            logs_dir.mkdir(parents=True, exist_ok=True)
            ts_str = datetime.datetime.fromtimestamp(ahora_ts, tz=_TZ_UTC).strftime("%Y-%m-%d_%H%M%S_UTC")
            destino_gz = logs_dir / f"baul_ia_forense_{ts_str}.jsonl.gz"
            with open(ruta_baul, "rb") as f_in, gzip.open(destino_gz, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)

            corte_trades = ahora_ts - _RETENCION_TRADES_SEG
            corte_escudos = ahora_ts - _RETENCION_ESCUDOS_SEG
            cierres_y_post: List[str] = []
            escudos_15s: List[str] = []

            for ln in ruta_baul.read_text(encoding="utf-8", errors="replace").splitlines():
                s = ln.strip()
                if not s:
                    continue
                es_cierre = ('"CIERRE_OPERACION_REAL"' in s) or ('"AUDITORIA_POST_CIERRE_60S"' in s)
                ts_reg = ahora_ts
                try:
                    obj = json.loads(s)
                    if isinstance(obj, dict):
                        ts_val = obj.get("timestamp") or obj.get("ts_epoch") or obj.get("timestamp_epoch") or 0.0
                        if isinstance(ts_val, (int, float)) and float(ts_val) > 0.0:
                            ts_reg = float(ts_val)
                except Exception:
                    ts_reg = ahora_ts

                if es_cierre:
                    if ts_reg >= corte_trades:
                        cierres_y_post.append(s + "\n")
                else:
                    if ts_reg >= corte_escudos:
                        escudos_15s.append(s + "\n")

            conservadas = cierres_y_post[-1500:] + escudos_15s[-2500:]
            cls.reemplazar_lineas_atomico(ruta_baul, conservadas)
            return True
        except Exception:
            return False

    @staticmethod
    def purgar_archivos_antiguos_logs(logs_dir: pathlib.Path, ahora_ts: float) -> None:
        if not logs_dir.exists():
            return
        for archivo_gz in logs_dir.glob("*.gz"):
            try:
                if (ahora_ts - archivo_gz.stat().st_mtime) > _RETENCION_GZ_LOGS_SEG:
                    archivo_gz.unlink(missing_ok=True)
            except Exception:
                continue


def ejecutar_mantenimiento_silencioso_disco(estado_ram: Any, forzar: bool = False) -> bool:
    """
    Verifica cada 15 minutos (solo cuando Slots == 0/1 y sin locks pre-fill vigentes):
    1. Si cambio el dia UTC (00:00 UTC) o si bot_hft.log / bot_hft_h.log superan 15 MB,
       comprime copia en Logs/bot_hft_YYYY-MM-DD_HHMMSS_UTC.log.gz y conserva 2,500 lineas.
    2. Si cambio el dia UTC o si baul_ia_forense.jsonl supera 12 MB, archiva copia integra
       en Logs/baul_ia_forense_YYYY-MM-DD_HHMMSS_UTC.jsonl.gz y aplica retencion estratificada
       (14 dias de cierres reales / 72 horas de auditorias de escudos 15s).
    3. Purga archivos .gz en Logs/ con mas de 30 dias de antiguedad.
    """
    global _ULTIMA_HIGIENE_TS
    if cfg.es_modo_test():
        return False
    ahora = time.time()
    if not forzar and (ahora - _ULTIMA_HIGIENE_TS) < 900.0:
        return False

    d_locks = getattr(estado_ram, "locks_pre_fill", None)
    locks_vigentes = _GestorRotacionEstratificada.purgar_locks_respetando_gracia(d_locks, ahora, gracia_seg=6.0)
    pos_activas = getattr(estado_ram, "posiciones_activas", {}) or {}
    if len(pos_activas) > 0 or locks_vigentes > 0:
        return False

    _ULTIMA_HIGIENE_TS = ahora
    rotado = False
    base_dir = cfg.obtener_ruta_base()
    logs_dir = base_dir / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    hoy_utc = datetime.datetime.fromtimestamp(ahora, tz=_TZ_UTC).strftime("%Y-%m-%d")
    marcador_fecha = logs_dir / ".ultima_rotacion_utc.txt"
    cambio_dia_utc = False
    try:
        if marcador_fecha.exists():
            fecha_previa = marcador_fecha.read_text(encoding="utf-8", errors="replace").strip()
            if fecha_previa and fecha_previa != hoy_utc:
                cambio_dia_utc = True
        else:
            marcador_fecha.write_text(hoy_utc + "\n", encoding="utf-8")
    except Exception:
        cambio_dia_utc = False

    ts_str = datetime.datetime.fromtimestamp(ahora, tz=_TZ_UTC).strftime("%Y-%m-%d_%H%M%S_UTC")
    for clave in ("ARCHIVO_LOG", "ARCHIVO_LOG_HISTORICO"):
        ruta = cfg.obtener_ruta_archivo(clave)
        if not ruta.exists():
            continue
        try:
            tamano = ruta.stat().st_size
            if tamano == 0:
                continue
            if not cambio_dia_utc and tamano < _LIMITE_BYTES_LOG:
                continue
            stem = ruta.stem
            destino_gz = logs_dir / f"{stem}_{ts_str}.log.gz"
            ram.cerrar_descriptores_log()
            with open(ruta, "rb") as f_in, gzip.open(destino_gz, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
            cola_lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines(True)[-2500:]
            _GestorRotacionEstratificada.reemplazar_lineas_atomico(ruta, cola_lineas)
            rotado = True
        except Exception:
            continue

    ruta_baul = cfg.obtener_ruta_archivo("ARCHIVO_BAUL_IA_JSONL")
    if _GestorRotacionEstratificada.compactar_baul_estratificado(
        ruta_baul, logs_dir, ahora, forzar_diario=cambio_dia_utc
    ):
        rotado = True

    if cambio_dia_utc:
        try:
            marcador_fecha.write_text(hoy_utc + "\n", encoding="utf-8")
        except Exception:
            pass

    _GestorRotacionEstratificada.purgar_archivos_antiguos_logs(logs_dir, ahora)

    eventos_col = getattr(estado_ram, "eventos_colapso_recientes", {})
    if isinstance(eventos_col, dict):
        expirados = [k for k, t_ev in list(eventos_col.items()) if (ahora - t_ev) > 120.0]
        for k in expirados:
            eventos_col.pop(k, None)
    try:
        gc.collect(1)
    except Exception:
        pass
    return rotado


_ESTADO_HIGIENE_4C: Dict[str, Any] = {
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
    - Ciclo 1 (25s): Socket TLS Warmer (gobernado en main.py) + poda respetando gracia 6.0s.
    - Ciclo 2 (180s): Recoleccion generacional gc.collect(1) y poda de diccionarios RAM.
    - Ciclo 3 (900s): Poda de vigilancia vencida en radar_ref + recoleccion profunda gc.collect(2).
    - Ciclo 4 (1800s): Sincronizacion incremental a bot_hft_h.log y truncado atomico (>15MB).
    """
    d_locks = getattr(ram.ESTADO_GLOBAL, "locks_pre_fill", None)
    locks_vigentes = _GestorRotacionEstratificada.purgar_locks_respetando_gracia(
        d_locks, ahora_ts, gracia_seg=6.0
    )
    if slots_ocupados > 0 or ordenes_en_vuelo > 0 or locks_vigentes > 0:
        return {"status": "DEFERRED_ACTIVE_SLOT", "ciclos": _ESTADO_HIGIENE_4C["ciclos_ejecutados"]}

    acciones = []
    if (ahora_ts - _ESTADO_HIGIENE_4C["ts_ultimo_gc_rapido"]) >= 180.0:
        _ESTADO_HIGIENE_4C["ts_ultimo_gc_rapido"] = ahora_ts
        liberados = gc.collect(1)
        _ESTADO_HIGIENE_4C["objetos_liberados_total"] += int(liberados)
        _ESTADO_HIGIENE_4C["ciclos_ejecutados"] += 1
        acciones.append(f"GC_GEN1({liberados})")

    if (ahora_ts - _ESTADO_HIGIENE_4C["ts_ultimo_gc_profundo"]) >= 900.0:
        _ESTADO_HIGIENE_4C["ts_ultimo_gc_profundo"] = ahora_ts
        estados_par = getattr(radar_ref, "estados_par", None) if radar_ref is not None else None
        if isinstance(estados_par, dict):
            for est_p in estados_par.values():
                if getattr(est_p, "vigilancia_short_hasta_ts", 0.0) > 0.0 and ahora_ts > est_p.vigilancia_short_hasta_ts:
                    est_p.vigilancia_short_hasta_ts = 0.0
                    est_p.max_z_pump_short = 0.0
                    est_p.max_ema_pump_short = 0.0
                    est_p.px_pico_pump_short = 0.0
        liberados_g2 = gc.collect(2)
        _ESTADO_HIGIENE_4C["objetos_liberados_total"] += int(liberados_g2)
        acciones.append(f"GC_GEN2({liberados_g2})")

    if (ahora_ts - _ESTADO_HIGIENE_4C["ts_ultima_rotacion_log"]) >= 1800.0:
        _ESTADO_HIGIENE_4C["ts_ultima_rotacion_log"] = ahora_ts
        try:
            p_log = cfg.obtener_ruta_archivo("ARCHIVO_LOG") if log_path == "bot_hft.log" else pathlib.Path(log_path)
            if p_log.exists() and p_log.stat().st_size > _LIMITE_BYTES_LOG:
                ram.cerrar_descriptores_log()
                lineas = p_log.read_text(encoding="utf-8", errors="replace").splitlines(True)
                if len(lineas) > 2500:
                    p_hist = cfg.obtener_ruta_archivo("ARCHIVO_LOG_HISTORICO") if hist_log_path == "bot_hft_h.log" else pathlib.Path(hist_log_path)
                    with p_hist.open("a", encoding="utf-8") as fh:
                        fh.writelines(lineas[:-2500])
                    _GestorRotacionEstratificada.reemplazar_lineas_atomico(p_log, lineas[-2500:])
                    acciones.append("LOG_COPY_TRUNCATE_OK")
        except Exception:
            pass

    return {
        "status": "OK",
        "acciones": acciones,
        "ciclos": _ESTADO_HIGIENE_4C["ciclos_ejecutados"],
        "objetos_liberados": _ESTADO_HIGIENE_4C["objetos_liberados_total"],
    }
