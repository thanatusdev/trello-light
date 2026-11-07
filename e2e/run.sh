#!/usr/bin/env bash
# Starts the isolated e2e stack, waits for it, runs Playwright, and tears it down.
# Usually run through `make test-e2e` (args="..." are passed to `playwright test`).
#
#   e2e/run.sh                     # whole suite (Chromium)
#   e2e/run.sh tests/auth.spec.ts  # extra args go to `playwright test`
#   E2E_ALL_BROWSERS=1 e2e/run.sh  # also Firefox and WebKit
#   KEEP_STACK=1 e2e/run.sh        # leave the stack up afterwards (debugging, repeated runs)
#   E2E_SKIP_BUILD=1 e2e/run.sh    # use already-built images (CI pre-builds them with build-push-action)
#   E2E_LOGS_DIR=logs e2e/run.sh   # on failure, save the stack's logs there before teardown
#   E2E_PROJECT=name e2e/run.sh    # compose project name (default trello-e2e)
set -euo pipefail

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$E2E_DIR")"
export E2E_PORT="${E2E_PORT:-8081}"
export E2E_BASE_URL="${E2E_BASE_URL:-http://localhost:${E2E_PORT}}"
HEALTH_URL="${E2E_BASE_URL}/api/v1/health"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"
E2E_PROJECT="${E2E_PROJECT:-trello-e2e}"

# The base compose file interpolates these for the db service; the e2e override replaces
# the values, so placeholders only keep compose from warning when no root .env exists.
export POSTGRES_USER="${POSTGRES_USER:-unused}" POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-unused}" POSTGRES_DB="${POSTGRES_DB:-unused}"

compose() {
  docker compose -p "$E2E_PROJECT" --project-directory "$ROOT_DIR" \
    -f "$ROOT_DIR/docker-compose.yml" -f "$ROOT_DIR/docker-compose.e2e.yml" "$@"
}

teardown() {
  local status=$?
  if [[ "$status" -ne 0 && -n "${E2E_LOGS_DIR:-}" ]]; then
    mkdir -p "$E2E_LOGS_DIR"
    compose ps -a >"$E2E_LOGS_DIR/compose-ps.txt" 2>&1 || true
    compose logs --no-color --timestamps >"$E2E_LOGS_DIR/compose.log" 2>&1 || true
  fi
  if [[ "${KEEP_STACK:-0}" == "1" ]]; then
    echo "KEEP_STACK=1: stack left running. Stop it with:"
    echo "  docker compose -p ${E2E_PROJECT} -f docker-compose.yml -f docker-compose.e2e.yml down -v"
  else
    echo "Tearing down the e2e stack..."
    compose down -v --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap teardown EXIT

echo "Starting the e2e stack..."
if [[ "${E2E_SKIP_BUILD:-0}" == "1" ]]; then
  compose up -d --no-build --wait
else
  compose up -d --build --wait
fi

echo "Waiting for ${HEALTH_URL}..."
deadline=$((SECONDS + HEALTH_TIMEOUT))
until curl -fsS "$HEALTH_URL" >/dev/null 2>&1; do
  if ((SECONDS >= deadline)); then
    echo "The stack did not become healthy within ${HEALTH_TIMEOUT}s." >&2
    compose ps >&2
    compose logs --tail=50 api >&2
    exit 1
  fi
  sleep 2
done
echo "Stack is healthy."

cd "$E2E_DIR"
[[ -d node_modules ]] || npm ci
# CI runners also need the browsers' OS packages; locally they are assumed present.
npx playwright install $([[ -n "${CI:-}" ]] && echo --with-deps) chromium \
  $([[ "${E2E_ALL_BROWSERS:-0}" == "1" ]] && echo firefox webkit) >/dev/null

status=0
npx playwright test "$@" || status=$?
exit "$status"
