#!/usr/bin/env bash
# ==============================================================================
# HFT DOCTOR BLYTHE ENGINE - PRODUCTION BASELINE TERPSICHORA V1.0
# Low-Jitter Linux Infrastructure & Live CLI HUD Installer (verbot)
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
        trap 'echo -e "
 [OK] Live HUD closed safely (Doctor Blythe daemon continues running in background)."; exit 0' INT TERM
        cd "${repo_dir}" || exit 1
        if [ "${1}" = "-s" ]; then
            ./venv/bin/python -c "import gestor_posiciones as gp; gp.imprimir_hud_verbot_cli(lineas_log=20)"
        elif [ "${1}" = "-q" ]; then
            ./venv/bin/python evaluador_cuantico_oos.py
        elif [ "${1}" = "-l" ]; then
            ./venv/bin/python evaluador_cuantico_oos.py --lab
        else
            ./venv/bin/python -c "import gestor_posiciones as gp; gp.imprimir_hud_verbot_cli(lineas_log=15)"
            echo " [STREAMING LIVE TELEMETRY - Press Ctrl+C to exit view without stopping bot]"
            tail -f "${repo_dir}/bot_hft.log"
        fi
    )
}
# === DOCTOR-BLYTHE CLI END ===
EOF

echo "[OK] Infrastructure & verbot CLI configured for HFT Doctor Blythe Engine - Terpsichora V1.0"
