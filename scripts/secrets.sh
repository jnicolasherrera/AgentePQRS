#!/usr/bin/env bash
# Regenera el/los .env reales desde 1Password (vault Dev) a partir de los .env*.tpl.
# Requiere: op (1Password CLI) con la integracion de la app de escritorio activada.
set -euo pipefail
cd "$(dirname "$0")/.."
mapfile -t tpls < <(find . -name '*.tpl' -path '*.env*' \
  -not -path '*/node_modules/*' -not -path '*/.git/*')
[ ${#tpls[@]} -gt 0 ] || { echo "No hay .env*.tpl"; exit 0; }
for tpl in "${tpls[@]}"; do
  out="${tpl%.tpl}"
  op inject -i "$tpl" -o "$out" -f && echo "OK: $out"
done
