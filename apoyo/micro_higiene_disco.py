# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #5: Higiene Automatica de Disco (Log Rotation .gz Zero-Jitter
con Reemplazo Atomico, Compactacion Estratificada de baul_ia_forense.jsonl sin
Perdida de Cierres Reales y Preservacion de Ventana de Gracia Post-Lock 6.0s)
para HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
import datetime
import gc
import gzip
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
_LIMITE_BYTES_LOG: int = 15 * 1024 * 1024   # 15 MB
_LIMITE_BYTES_BAUL: int = 12 * 1024 * 1024  # 12 MB


def _purgar_locks_expirados_respetando_gracia(d_locks: Any, ahora_ts: float, gracia_seg: float = 6.0) -> int:
    """
    Limpia de locks_pre_fill unicamente los candados vencidos:
    - Si v > 0.0: orden en vuelo activa mientras ahora_ts < v.
    - Si v < 0.0: marca de liberacion (-time.time()); se conserva durante gracia_seg (6.0s)
      para que micro_sizing_kelly y micro_escape_reconciliador detecten cancelaciones
      o fills recientes sin borrar su rastro prematuramente.
    Retorna el numero de locks activos o en ventana de gracia vigentes.
    """
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


def _reemplazar_lineas_atomico(ruta: pathlib.Path, lineas: List[str]) -> None:
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


def _compactar_baul_forense_estratificado(ruta_baul: pathlib.Path, backup_dir: pathlib.Path) -> bool:
    """
    Si baul_ia_forense.jsonl supera 12 MB:
    1. Archiva una copia integra comprimida (.gz) en backups_epoca_anterior/.
    2. Conserva el 100% de CIERRE_OPERACION_REAL y AUDITORIA_POST_CIERRE_60S
       recientes mas los ultimos 2,500 registros de AUDITORIA_ESCUDO_15S.
    """
    if not ruta_baul.exists():
        return False
    try:
        if ruta_baul.stat().st_size < _LIMITE_BYTES_BAUL:
            return False
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.datetime.now(_TZ_UTC).strftime("%Y%m%d_%H%M%S")
        destino_gz = backup_dir / f"{ruta_baul.name}.{ts_str}.gz"
        with open(ruta_baul, "rb") as f_in, gzip.open(destino_gz, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)

        lineas_raw = ruta_baul.read_text(encoding="utf-8", errors="replace").splitlines()
        cierres_y_post: List[str] = []
        escudos_15s: List[str] = []
        for ln in lineas_raw:
            s = ln.strip()
            if not s:
                continue
            if '"CIERRE_OPERACION_REAL"' in s or '"AUDITORIA_POST_CIERRE_60S"' in s:
                cierres_y_post.append(s + "\n")
            else:
                escudos_15s.append(s + "\n")

        conservadas = cierres_y_post[-1000:] + escudos_15s[-2500:]
        _reemplazar_lineas_atomico(ruta_baul, conservadas)
        return True
    except Exception:
        return False


def ejecutar_mantenimiento_silencioso_disco(estado_ram: Any, forzar: bool = False) -> bool:
    """
    Verifica cada 15 minutos (solo cuando no hay posiciones abiertas ni locks pre-fill)
    si bot_hft.log, bot_hft_h.log (>15 MB) o baul_ia_forense.jsonl (>12 MB) requieren
    rotacion comprimida en backups_epoca_anterior/ y truncado atomico sin jitter.
    """
    global _ULTIMA_HIGIENE_TS
    if cfg.es_modo_test():
        return False
    ahora = time.time()
    if not forzar and (ahora - _ULTIMA_HIGIENE_TS) < 900.0:
        return False

    d_locks = getattr(estado_ram, "locks_pre_fill", None)
    locks_vigentes = _purgar_locks_expirados_respetando_gracia(d_locks, ahora, gracia_seg=6.0)
    pos_activas = getattr(estado_ram, "posiciones_activas", {}) or {}
    if len(pos_activas) > 0 or locks_vigentes > 0:
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
            ram.cerrar_descriptores_log()
            with open(ruta, "rb") as f_in, gzip.open(destino_gz, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
            cola_lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines(True)[-2500:]
            _reemplazar_lineas_atomico(ruta, cola_lineas)
            rotado = True
        except Exception:
            continue

    ruta_baul = cfg.obtener_ruta_archivo("ARCHIVO_BAUL_IA_JSONL")
    if _compactar_baul_forense_estratificado(ruta_baul, backup_dir):
        rotado = True

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
    locks_vigentes = _purgar_locks_expirados_respetando_gracia(d_locks, ahora_ts, gracia_seg=6.0)
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
            p_log = pathlib.Path(log_path)
            if p_log.exists() and p_log.stat().st_size > _LIMITE_BYTES_LOG:
                ram.cerrar_descriptores_log()
                lineas = p_log.read_text(encoding="utf-8", errors="replace").splitlines(True)
                if len(lineas) > 2500:
                    p_hist = pathlib.Path(hist_log_path)
                    with p_hist.open("a", encoding="utf-8") as fh:
                        fh.writelines(lineas[:-2500])
                    _reemplazar_lineas_atomico(p_log, lineas[-2500:])
                    acciones.append("LOG_COPY_TRUNCATE_OK")
        except Exception:
            pass

    return {
        "status": "OK",
        "acciones": acciones,
        "ciclos": _ESTADO_HIGIENE_4C["ciclos_ejecutados"],
        "objetos_liberados": _ESTADO_HIGIENE_4C["objetos_liberados_total"],
    }
