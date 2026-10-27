#!/usr/bin/env python3
"""
Gate 0 Static Auditor for HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0.
Verifies pure UTF-8 (no BOM), Unix LF line endings, AST compilation, and the
exact 100-uppercase-constant contract (AST_100_CONSTANTES_OK) across all 17 canonical files.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys
from typing import List, Tuple

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent

ARCHIVOS_CANONICOS: Tuple[Tuple[str, str], ...] = (
    (".gitignore", "TEXT"),
    ("README.md", "TEXT"),
    ("requirements.txt", "TEXT"),
    ("config_parametros.py", "CFG_100"),
    ("core_estado_ram.py", "PY"),
    ("telemetria_telegram.py", "PY"),
    ("stats_tracker.py", "PY"),
    ("escudo_tricortex.py", "PY"),
    ("radar_volatilidad.py", "PY"),
    ("ejecutor_sniper.py", "PY"),
    ("gestor_posiciones.py", "PY"),
    ("ofensiva/__init__.py", "PY"),
    ("ofensiva/micro_motor_maker.py", "PY"),
    ("ofensiva/micro_motor_wald_exit.py", "PY"),
    ("ofensiva/micro_sizing_kelly.py", "PY"),
    ("ofensiva/micro_cotizador_stoikov.py", "PY"),
    ("ofensiva/micro_cresta_convexo_sprt.py", "PY"),
    ("ofensiva/micro_conviccion_kelly.py", "PY"),
    ("ofensiva/micro_enganche_fase.py", "PY"),
    ("ofensiva/micro_impulso_runner.py", "PY"),
    ("defensiva/__init__.py", "PY"),
    ("defensiva/micro_escudos_fisicos.py", "PY"),
    ("defensiva/micro_veto_macro_btc.py", "PY"),
    ("defensiva/micro_cortafuegos_contagio.py", "PY"),
    ("defensiva/micro_evacuador_scratch.py", "PY"),
    ("apoyo/__init__.py", "PY"),
    ("apoyo/micro_cinematica_l2.py", "PY"),
    ("apoyo/micro_paridad_lvr_uta.py", "PY"),
    ("apoyo/micro_hud_ansi_telegram.py", "PY"),
    ("apoyo/micro_gemelo_digital_oos.py", "PY"),
    ("apoyo/micro_higiene_disco.py", "PY"),
    ("apoyo/micro_inspector_forense.py", "PY"),
    ("apoyo/micro_sensibilidad_autonoma.py", "PY"),
    ("main.py", "PY"),
    ("evaluador_cuantico_oos.py", "PY"),
    ("instalar_infraestructura.sh", "SH"),
    ("test_tribrain_v1_suite.py", "PY"),
    ("tools/validate_pool.py", "PY"),
    ("calibracion_oos.json", "JSON"),
)


def auditar_archivo(rel_path: str, tipo: str, auto_sanitize: bool = True) -> Tuple[bool, str]:
    ruta = ROOT_DIR / rel_path
    if not ruta.exists():
        return False, "MISSING_FILE"

    raw = ruta.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        if auto_sanitize:
            raw = raw[3:]
            ruta.write_bytes(raw)
        else:
            return False, "UTF8_BOM_DETECTED"

    if b"\r\n" in raw:
        if auto_sanitize:
            raw = raw.replace(b"\r\n", b"\n")
            ruta.write_bytes(raw)
        else:
            return False, "CRLF_DETECTED"

    try:
        texto = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False, "INVALID_UTF8"

    if tipo == "CFG_100":
        tree = ast.parse(texto, filename=rel_path)
        constantes: List[str] = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.isupper() and not t.id.startswith("_"):
                        constantes.append(t.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id.isupper() and not node.target.id.startswith("_"):
                    constantes.append(node.target.id)
        duplicados = [k for k in set(constantes) if constantes.count(k) > 1]
        if duplicados:
            return False, f"DUPLICATE_CONSTANTS:{duplicados}"
        if len(constantes) != 100:
            return False, f"EXPECTED_100_GOT_{len(constantes)}"
        return True, "AST_100_CONSTANTES_OK"

    if tipo == "PY":
        ast.parse(texto, filename=rel_path)
        return True, "AST_OK"

    if tipo == "SH":
        return True, "SH_LF_OK"

    if tipo == "JSON":
        json.loads(texto)
        return True, "JSON_OK"

    return True, "CLEAN_UTF8_LF"


def main() -> int:
    print("=" * 90)
    print(" [GATE 0] STATIC UTF-8 / LF / AST INTEGRITY AUDIT -- DOCTOR-BLYTHE TERPSICHORA V1.0")
    print("=" * 90)
    errores = 0
    for rel_path, tipo in ARCHIVOS_CANONICOS:
        ok, estado = auditar_archivo(rel_path, tipo, auto_sanitize=True)
        tag = "[OK]   " if ok else "[ERROR]"
        print(f" {tag}  {rel_path:<32} -> {estado}")
        if not ok:
            errores += 1
    print("=" * 90)
    if errores == 0:
        print(" FINAL RESULT: 0 ERRORS DETECTED | DOCTOR-BLYTHE TERPSICHORA V1.0 (39/39) CERTIFIED")
        print("=" * 90)
        return 0
    print(f" FINAL RESULT: {errores} FILE(S) WITH VALIDATION ERRORS")
    print("=" * 90)
    return 1


if __name__ == "__main__":
    sys.exit(main())
