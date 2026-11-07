#!/usr/bin/env bash
# Runs once, on first initialisation of the Postgres data volume.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	CREATE DATABASE "${TEST_POSTGRES_DB:-kanban_test}";
EOSQL
