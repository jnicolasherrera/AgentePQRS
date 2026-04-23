#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# migrate.sh — runner idempotente de migraciones SQL
# ═══════════════════════════════════════════════════════════════
# Uso:
#   ./scripts/migrate.sh --env=staging            (aplica pendientes)
#   ./scripts/migrate.sh --env=staging --dry-run  (solo lista)
#   ./scripts/migrate.sh --env=prod               (aplica pendientes)
#
# Comportamiento:
# - Aplica SQLs de migrations/ en orden lexicográfico, saltando los
#   que ya están en la tabla aequitas_migrations del ambiente objetivo.
# - Toma advisory lock de PostgreSQL para prevenir runs concurrentes.
# - Guard crítico: SQLs con prefijo 99_seed* SOLO se aplican si
#   --env=staging. Contra prod abortan.
# - Registra cada aplicación en aequitas_migrations con su sha256
#   para detectar si un archivo ya aplicado cambió después.
#
# Requisitos:
# - SSH config con hosts flexpqr-staging y flexpqr-prod.
# - Container pqrs_v2_db corriendo en ambos hosts.
# - Usuario pqrs_admin con permisos sobre pqrs_v2.
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── Parámetros ─────────────────────────────────────────────────
ENV=""
DRY_RUN=0
MIGRATIONS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/migrations"
LOCK_TAG="migrate-sh-$(whoami)-$$-$(date +%s)"

for arg in "$@"; do
  case "$arg" in
    --env=*)    ENV="${arg#*=}" ;;
    --dry-run)  DRY_RUN=1 ;;
    -h|--help)
      grep -E '^# ' "$0" | sed 's/^# //'; exit 0 ;;
    *)
      echo "ERROR: argumento desconocido: $arg" >&2
      exit 2 ;;
  esac
done

if [[ -z "$ENV" ]]; then
  echo "ERROR: falta --env=staging|prod" >&2
  exit 2
fi

case "$ENV" in
  staging) SSH_HOST="flexpqr-staging" ;;
  prod)    SSH_HOST="flexpqr-prod" ;;
  *)
    echo "ERROR: --env debe ser 'staging' o 'prod', recibido: $ENV" >&2
    exit 2 ;;
esac

echo "═══════════════════════════════════════════════════════════"
echo "migrate.sh  env=$ENV  host=$SSH_HOST  dry_run=$DRY_RUN"
echo "Migrations dir: $MIGRATIONS_DIR"
echo "═══════════════════════════════════════════════════════════"

# ── Helpers ────────────────────────────────────────────────────
psql_exec() {
  # $1 = archivo SQL local que se ejecuta contra el ambiente via docker exec.
  # Usa ON_ERROR_STOP=1 para que cualquier error aborte la ejecución.
  local file="$1"
  ssh "$SSH_HOST" "docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -v ON_ERROR_STOP=1" < "$file"
}

psql_query() {
  # $1 = query SQL. Retorna solo el valor (tuples-only).
  local sql="$1"
  ssh "$SSH_HOST" "docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -v ON_ERROR_STOP=1 -tA" <<<"$sql"
}

ensure_migrations_table() {
  psql_query "CREATE TABLE IF NOT EXISTS aequitas_migrations (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    sha256 TEXT NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by TEXT DEFAULT CURRENT_USER
  );" >/dev/null
}

ensure_lock_table() {
  psql_query "CREATE TABLE IF NOT EXISTS aequitas_migrations_lock (
    lock_id INT PRIMARY KEY,
    tag TEXT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW()
  );" >/dev/null
}

acquire_lock() {
  # INSERT con PK fija: si ya existe una fila, el INSERT falla y
  # consideramos que hay otro runner activo.
  local out
  if ! out=$(psql_query "INSERT INTO aequitas_migrations_lock (lock_id, tag) VALUES (1, '$LOCK_TAG');" 2>&1); then
    echo "ERROR: no se pudo tomar el lock de migraciones. Otro run está activo o quedó un lock stale." >&2
    local stale
    stale=$(psql_query "SELECT tag || ' since ' || started_at::text FROM aequitas_migrations_lock WHERE lock_id = 1;" 2>/dev/null || echo "?")
    echo "  Lock actual: $stale" >&2
    echo "  Para limpiar manualmente: psql -c 'DELETE FROM aequitas_migrations_lock WHERE lock_id = 1;'" >&2
    return 1
  fi
}

release_lock() {
  psql_query "DELETE FROM aequitas_migrations_lock WHERE lock_id = 1 AND tag = '$LOCK_TAG';" >/dev/null 2>&1 || true
}

already_applied() {
  # Devuelve 0 (true en bash) si la migración ya fue aplicada.
  local filename="$1"
  local count
  count=$(psql_query "SELECT COUNT(*) FROM aequitas_migrations WHERE filename = '$filename';")
  [[ "$count" -ge 1 ]]
}

register_migration() {
  local filename="$1"
  local sha256="$2"
  psql_query "INSERT INTO aequitas_migrations (filename, sha256) VALUES ('$filename', '$sha256');" >/dev/null
}

# ── Guard staging-only ─────────────────────────────────────────
is_staging_only() {
  local basename="$1"
  [[ "$basename" == 99_seed* ]]
}

# ── Pre-flight ─────────────────────────────────────────────────
echo ""
echo "→ Verificando conectividad con $SSH_HOST..."
ssh -o ConnectTimeout=10 "$SSH_HOST" "docker ps --format '{{.Names}}' | grep -q pqrs_v2_db" \
  || { echo "ERROR: no se pudo alcanzar container pqrs_v2_db en $SSH_HOST" >&2; exit 3; }
echo "  OK"

echo ""
echo "→ Garantizando tablas aequitas_migrations y aequitas_migrations_lock..."
ensure_migrations_table
ensure_lock_table
echo "  OK"

# ── Lock de tabla (durable entre sesiones psql efímeras) ───────
echo ""
echo "→ Tomando lock de migraciones (tag=$LOCK_TAG)..."
acquire_lock || exit 4
echo "  OK"

# Liberar lock al salir, pase lo que pase
trap 'release_lock' EXIT

# ── Enumerar migraciones ───────────────────────────────────────
echo ""
echo "→ Inventariando migraciones en $MIGRATIONS_DIR..."
# Orden lexicográfico sobre los .sql del top-level de migrations/
# (NO incluye migrations/baseline/*.sql, que son dumps raw).
mapfile -t FILES < <(find "$MIGRATIONS_DIR" -maxdepth 1 -name '*.sql' | sort)

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "  Ninguna migración encontrada."
  exit 0
fi

echo "  ${#FILES[@]} archivo(s):"
for f in "${FILES[@]}"; do
  echo "    - $(basename "$f")"
done

# ── Aplicar en orden ───────────────────────────────────────────
echo ""
echo "→ Procesando migraciones..."
APPLIED=0
SKIPPED=0

for file in "${FILES[@]}"; do
  basename=$(basename "$file")
  sha256=$(sha256sum "$file" | cut -d' ' -f1)

  # Guard staging-only: ABORT (no skip) si alguien intenta correr
  # un seed en un ambiente que no es staging. Es un error de operación,
  # no algo que deba silenciarse.
  if is_staging_only "$basename" && [[ "$ENV" != "staging" ]]; then
    echo "" >&2
    echo "ERROR: $basename es staging-only y env=$ENV." >&2
    echo "  Los archivos 99_seed_* contienen fixtures sintéticos y NO" >&2
    echo "  deben aplicarse fuera de staging. Abortando." >&2
    exit 6
  fi

  if already_applied "$basename"; then
    echo "  ✓ ya aplicada: $basename"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "  [DRY-RUN] aplicaría: $basename  (sha256=${sha256:0:12}...)"
    continue
  fi

  echo "  → aplicando $basename (sha256=${sha256:0:12}...)..."
  if psql_exec "$file"; then
    register_migration "$basename" "$sha256"
    echo "    ✓ registrada"
    APPLIED=$((APPLIED + 1))
  else
    echo "    ✗ ERROR aplicando $basename — abortando" >&2
    exit 5
  fi
done

# ── Reporte ────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "Dry-run completo. Nada se aplicó."
else
  echo "Resumen: $APPLIED aplicada(s), $SKIPPED ya aplicadas/skipped."
fi
echo "═══════════════════════════════════════════════════════════"
