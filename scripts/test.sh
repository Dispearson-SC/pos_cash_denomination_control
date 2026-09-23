#!/usr/bin/env bash
# Thin wrapper over the workspace's shared test runner. Only works inside
# the odoo-dev workspace (needs ../../dev/scripts/test.sh to exist).
#
# Usage: scripts/test.sh [extra_modules] [-- extra odoo args...]
#   scripts/test.sh
#   scripts/test.sh pos_hr
#   scripts/test.sh "" -- --test-tags pcdc_domain/pos_cash_denomination_control
set -euo pipefail
exec "$(cd "$(dirname "$0")/.." && pwd)/../../dev/scripts/test.sh" pos_cash_denomination_control "$@"
