#!/usr/bin/env bash
# ==============================================================================
# HFT DOCTOR BLYTHE ENGINE - PRODUCTION BASELINE TERPSICHORA V1.0
# Low-Jitter Linux Infrastructure & Native Python Colorized HUD (verbot)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="${REPO_DIR}/venv/bin/python"

if [ ! -x "${VENV_PY}" ]; then
    python3 -m venv "${REPO_DIR}/venv"
    "${REPO_DIR}/venv/bin/pip" install --upgrade pip
    "${REPO_DIR}/venv/bin/pip" install -r "${REPO_DIR}/requirements.txt"
fi

sed -i '/# === DOCTOR-BLYTHE CLI START ===/,/# === DOCTOR-BLYTHE CLI END ===/d' "${HOME}/.bashrc" 2>/dev/null || true

cat << 'EOF' >> "${HOME}/.bashrc"
# === DOCTOR-BLYTHE CLI START ===
verbot() {
    local repo_dir
    if [ -d "${HOME}/Doctor-Blythe" ]; then
        repo_dir="${HOME}/Doctor-Blythe"
    else
        repo_dir="${HOME}/Tri-Brain-Sniper"
    fi
    (
        set +e
        cd "${repo_dir}" || exit 0
        if [ "${1}" = "-s" ]; then
            ./venv/bin/python -u -c "import gestor_posiciones as gp; gp.imprimir_hud_verbot_cli(lineas_log=22)"
        elif [ "${1}" = "-q" ]; then
            ./venv/bin/python -u evaluador_cuantico_oos.py
        elif [ "${1}" = "-l" ]; then
            ./venv/bin/python -u evaluador_cuantico_oos.py --lab
        else
            ./venv/bin/python -u -c "import gestor_posiciones as gp; gp.seguir_log_en_vivo_cli(lineas_iniciales=16)"
        fi
    )
}
# === DOCTOR-BLYTHE CLI END ===
EOF

echo "[OK] Native Python Colorized verbot HUD configured for Doctor Blythe V1.0"
