#!/usr/bin/env bash
set -euo pipefail

# Script per creare un dump SQL del DB SQLite
# Posiziona il file di dump in db/init/bilancio_dump.sql

DB_FILE="db/bilancio.db"
DUMP_DIR="db/init"
DUMP_FILE="$DUMP_DIR/bilancio_dump.sql"

if [ ! -f "$DB_FILE" ]; then
  echo "Errore: il file DB '$DB_FILE' non esiste." >&2
  exit 2
fi

mkdir -p "$DUMP_DIR"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "Errore: sqlite3 non è installato. Installa sqlite3 per usare questo script." >&2
  exit 3
fi

echo "Creazione dump SQL da '$DB_FILE' in '$DUMP_FILE'..."
sqlite3 "$DB_FILE" ".dump" > "$DUMP_FILE"

echo "Dump creato: $DUMP_FILE"
exit 0
