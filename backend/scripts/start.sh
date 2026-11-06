#!/bin/sh
set -eu

printf '%s\n' 'INFO: Datenbankmigrationen starten.'
alembic upgrade head

printf '%s\n' 'INFO: Synthetische Demo-Daten laden.'
python -m app.seed

printf '%s\n' 'INFO: Wissensbasis einlesen.'
if ! python -m app.rag.ingest; then
    printf '%s\n' 'WARNING: Wissensbasis konnte nicht geladen werden. Der Server startet trotzdem.' >&2
fi

printf '%s\n' 'INFO: Backend starten.'
exec python -m app.main
