#!/usr/bin/env bash
# Run intentionally after Supabase schema + Render/Fly service setup. Never echo secrets or enable xtrace.
set +x
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
platform=${1:-render}
case "$platform" in
  render)
    if ! command -v render >/dev/null 2>&1; then
      cat >&2 <<'HELP'
Render CLI missing. Install and log in yourself:
  curl -fsSL https://raw.githubusercontent.com/render-oss/cli/refs/heads/main/bin/install.sh | sh
  render login
Then create a Blueprint from render.yaml at https://dashboard.render.com/blueprints
Apply cloud/migrations/postgres/001_initial.sql to the target Supabase project first.
Select the intended Git branch and set DATABASE_URL plus distinct device/admin secrets in Render.
Export RENDER_SERVICE_ID, DATABASE_URL and the same two tokens privately; rerun bash cloud/deploy.sh render.
HELP
      exit 1
    fi
    ;;
  fly)
    if ! command -v flyctl >/dev/null 2>&1; then
      cat >&2 <<'HELP'
Fly CLI missing. Install and log in yourself:
  curl -L https://fly.io/install.sh | sh
  export PATH="$HOME/.fly/bin:$PATH"
  flyctl auth login
  flyctl apps create <unique-app-name>
Apply the Postgres schema; export KAEW_FLY_APP, DATABASE_URL and two distinct private tokens; rerun bash cloud/deploy.sh fly.
Fly may require billing; see cloud/README.md before creating resources.
HELP
      exit 1
    fi
    ;;
  *) echo 'Usage: bash cloud/deploy.sh [render|fly]' >&2; exit 2 ;;
esac
if [[ -z ${KAEW_DEVICE_TOKEN:-} || -z ${KAEW_ADMIN_TOKEN:-} || ${KAEW_DEVICE_TOKEN:-} == "${KAEW_ADMIN_TOKEN:-}" ]]; then
  echo 'Set distinct nonempty KAEW_DEVICE_TOKEN and KAEW_ADMIN_TOKEN privately first.' >&2
  exit 1
fi
if [[ -z ${DATABASE_URL:-} ]]; then
  echo 'Set DATABASE_URL privately from Supabase with sslmode=require; apply the schema first.' >&2
  exit 1
fi
# Reject newlines before sending KEY=VALUE records to the Fly secret importer.
if [[ $DATABASE_URL == *$'\n'* || $KAEW_DEVICE_TOKEN == *$'\n'* || $KAEW_ADMIN_TOKEN == *$'\n'* ]]; then
  echo 'Database URL and tokens must be single-line values.' >&2; exit 1
fi
if [[ $platform == render ]]; then
  : "${RENDER_SERVICE_ID:?Set RENDER_SERVICE_ID from the prepared Blueprint service}"
  # DATABASE_URL and both Render tokens must already be set in Dashboard; this triggers the configured remote branch.
  exec render deploys create "$RENDER_SERVICE_ID" --wait --confirm
else
  : "${KAEW_FLY_APP:?Set KAEW_FLY_APP to your existing app name}"
  printf 'KAEW_DEVICE_TOKEN=%s\nKAEW_ADMIN_TOKEN=%s\nDATABASE_URL=%s\n' "$KAEW_DEVICE_TOKEN" "$KAEW_ADMIN_TOKEN" "$DATABASE_URL" |
    flyctl secrets import --app "$KAEW_FLY_APP" --stage
  exec flyctl deploy . --config cloud/fly.toml --app "$KAEW_FLY_APP" --remote-only --ha=false
fi
