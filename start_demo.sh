#!/usr/bin/env bash
# Demo-Server starten: TSV Hotzenplotz, Port 1946
# Voraussetzung: .env.demo ausgefüllt, config/demo/field_config.json befüllt

set -euo pipefail

export ENV_FILE=.env.demo
export CONFIG_DIR=config/demo

exec .venv/bin/uvicorn web.main:app --reload --port 1946
