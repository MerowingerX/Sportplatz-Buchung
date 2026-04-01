#!/usr/bin/env bash
# Deploy-Script: baut das Docker-Image mit Git-Infos und startet den Container.
set -e

export GIT_COMMIT=$(git log -1 --format=%h)
export GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
export GIT_DATE=$(git log -1 --format=%ci | cut -c1-16)

echo "Deploying: commit=${GIT_COMMIT} branch=${GIT_BRANCH} date=${GIT_DATE}"

docker compose up -d --build
