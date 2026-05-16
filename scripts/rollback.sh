#!/usr/bin/env bash
set -euo pipefail
INSTALL_DIR="${INSTALL_DIR:-$(pwd)}"

echo "==> SYLION v6.2.0 rollback → v6.0.0"

BACKUP_DIR=$(ls -td "$INSTALL_DIR"/.backup-* 2>/dev/null | head -1 || echo "")
if [ -z "$BACKUP_DIR" ]; then
  echo "ERROR: brak katalogu .backup-* — rollback manual wymagany (zobacz ROLLBACK.md)"
  exit 1
fi

echo "    [INFO] Używam backupu: $BACKUP_DIR"
pkill -f 'uvicorn app:app' 2>/dev/null || true
sleep 2

cp -r "$BACKUP_DIR"/* "$INSTALL_DIR"/ 2>/dev/null || true

BAK_DB=$(ls "$INSTALL_DIR"/src/sylion-pipeline/*.bak-v600 "$INSTALL_DIR"/*.bak-v600 2>/dev/null | head -1 || echo "")
if [ -n "$BAK_DB" ]; then
  cp "$BAK_DB" "${SYLION_DB_PATH:-$INSTALL_DIR/sylion_aeis.db}"
  echo "    [OK] DB przywrócona z $BAK_DB"
fi

echo "$INSTALL_DIR" > /dev/null
echo "6.0.0" > "$INSTALL_DIR/src/sylion-pipeline/VERSION"

echo "==> Rollback zakończony. Zrestartuj serwer wg poprzedniej procedury v6.0.0."
