#!/usr/bin/env bash
# Demo-Server starten: TSV Hotzenplotz, Port 1946
# Voraussetzung: .env.demo ausgefüllt, config/demo/field_config.json befüllt

set -euo pipefail

export ENV_FILE=.env
export CONFIG_DIR=config

exec .venv/bin/uvicorn web.main:app --reload --reload-include "*.html" --reload-include "*.css" --reload-include "*.json" --port 1947
