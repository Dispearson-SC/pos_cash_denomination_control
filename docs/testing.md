# Testing: pos_cash_denomination_control

## Bringing the stack up

The test/dev runner is shared across every module in the `odoo-dev`
workspace and lives at the workspace root, in `dev/`:

```bash
cd ../../dev                       # from this module's repository root
docker compose build odoo          # first time, or after Dockerfile changes
docker compose up -d db odoo       # optional dev instance, reachable at http://localhost:8069
```

The compose project is named `odoo-workspace` (see `name:` in
`dev/docker-compose.yml`), so its containers/volumes/network are isolated
from anything else on the host. Only Odoo's `8069` is published, bound to
`127.0.0.1` only; Postgres is reachable only from other containers on the
compose network.

Stop it with `docker compose down` from `dev/` (add `-v` to also drop the
named volumes, i.e. wipe the dev database and filestore).

## Running tests

From this module's repository root:

```bash
scripts/test.sh                              # install + full addon test suite
scripts/test.sh pos_hr                       # coexistence run, also installs pos_hr
scripts/test.sh "" -- --test-tags pcdc_domain/pos_cash_denomination_control
scripts/test.sh "" -- --test-tags pcdc_hoot/pos_cash_denomination_control
```

or, equivalently, from the workspace root:

```bash
dev/scripts/test.sh pos_cash_denomination_control
dev/scripts/test.sh pos_cash_denomination_control pos_hr
dev/scripts/test.sh pos_cash_denomination_control "" -- --test-tags pcdc_domain/pos_cash_denomination_control
```

`scripts/test.sh` is a thin wrapper that pre-fills the module name and
delegates to `dev/scripts/test.sh`. Every run uses its own database,
**`test_pos_cash_denomination_control`**, dropped and recreated on each run
via `docker compose run --rm`; it never touches the `db` volume/data used by
a `docker compose up -d` dev instance. Anything after `--` replaces the
default `--test-tags` value, which is the fast way to run one phase's tag
during development.

### Hoot suite runs as part of the default `scripts/test.sh`

`tests/test_hoot.py::TestHoot.test_hoot_suite` is a permanent `HttpCase` that
runs `browser_js` against
`/web/tests?headless&loglevel=2&preset=desktop&filter=@pos_cash_denomination_control`
and fails the Python test whenever any Hoot assertion under this addon's `@`
tag fails. It is tagged `post_install, -at_install` (same as
`point_of_sale`'s own `TestUi` tour tests), and per the tag-union behavior
documented below it still matches the bare `/pos_cash_denomination_control`
filter, so a plain `scripts/test.sh` run with no override exercises the
addon's Hoot suite too.

**Known gotcha**: if a long-running dev `odoo` container (`up -d`) is
attached to the same Postgres server while a `scripts/test.sh` run tries to
drop `test_pos_cash_denomination_control`, Postgres may refuse with
"database is being accessed by other users" if the dev instance ever queried
that database. Stop the dev instance first (`docker compose stop odoo` from
`dev/`) if that happens, then bring it back with `docker compose up -d odoo`.

### Fast domain-only loop

```bash
scripts/test.sh "" -- --test-tags pcdc_domain/pos_cash_denomination_control
```

This runs only the pure-Python domain tests (`odoo.tests.BaseCase`, no
database access), which is the fastest feedback loop while iterating on
`domain/*.py`.

**Tag filter syntax gotcha (confirmed empirically)**: Odoo's `--test-tags`
grammar is `[+-]tag[/module][:class][.method]` — the custom **tag comes
first**, then an optional `/module`, then an optional `:class`. Writing
`/pos_cash_denomination_control:pcdc_domain` (module first, tag after the
colon) does **not** filter by the `pcdc_domain` tag: it is parsed as
`module=pos_cash_denomination_control, class=pcdc_domain`, which matches no
class named literally `pcdc_domain` and silently runs **zero tests**
("0 failed, 0 error(s) of 0 tests" — logged as if everything passed).
Always check that the reported test count is **greater than zero** before
trusting a green result. The correct form is `tag/module`, e.g.
`pcdc_domain/pos_cash_denomination_control`. The full default suite
(`scripts/test.sh`, no override) is unaffected because it uses the bare
`/pos_cash_denomination_control` filter with no class segment, which
correctly matches every `standard`-tagged test in the module (the `tagged()`
decorator unions with, rather than replaces, the default `{"standard",
"at_install"}` tags that `odoo.tests.common.BaseCase.__init_subclass__`
assigns).

### `pos_hr` coexistence run

```bash
scripts/test.sh pos_hr
```

Installs `pos_cash_denomination_control,pos_hr` together and re-runs the
full suite, to catch any conflict between this addon's patches and `pos_hr`'s
own overrides of the same extension points (`try_cash_in_out`,
`_set_opening_control_data`, `CashMovePopup`, ...).

### End-to-end browser tours

```bash
scripts/test.sh "" -- --test-tags /pos_cash_denomination_control:TestPcdcHttpCommon
```

`tests/test_frontend.py::TestPcdcHttpCommon` (tagged `post_install,
-at_install, pcdc_tours`) runs one real headless-Chrome tour per scenario:
opening/cash-out/closing with a denomination breakdown, cash-in disabled,
reason/denomination rejection, the vault withdrawal alert's full lifecycle
(including the one-click cash-out and, where applicable, register
blocking), and a dedicated tour confirming the offline replay queue is
memory-only. These run as part of the default `scripts/test.sh` (no tag
override needed); the command above is the fast way to re-run only this
class during development. Every tour except the opening one logs in as
`pos_admin`: the "Cash In/Out" menu option and the one-click vault cash-out
both require `_has_cash_move_permission()` (`group_pos_manager` or
`account.group_account_invoice`), which the plain `pos_user` fixture lacks
— see `CLAUDE.md`'s "Deferred: cashier vault-withdrawal permission" note.

## Verified baselines

- `dev/scripts/test.sh pos_cash_denomination_control` (standalone) — 61
  modules loaded, 0 failed of 171 tests.
- `dev/scripts/test.sh cash_vault -- --test-tags /cash_vault,/pos_cash_denomination_control`
  (together with `cash_vault`) — 62 modules loaded, 0 failed of 294 tests.

## Confirmed image facts

- `from odoo.tests import BaseCase` exists; MRO is `odoo.tests.common.BaseCase
  → odoo.tests.case.TestCase → unittest.case.TestCase → object`. It is a
  plain `unittest.TestCase` with no cursor/env, so `--test-tags` and
  `@tagged(...)` both work; tags are stored on the class as `test_tags`, not
  `_tags`.
- The Hoot runner (`odoo/addons/web/tests/test_js.py`,
  `web/static/lib/hoot/core/config.js`) accepts a `filter` URL query param
  (alias `name`) that matches a test/suite's full name **or its tags** as a
  search string, plus a `tag`/`tags` param for exact tag matching. For a
  standalone `HttpCase.browser_js` call (`tests/test_hoot.py`), use:
  - URL: `/web/tests?headless&loglevel=2&preset=desktop&filter=@pos_cash_denomination_control`
  - success signal: `[HOOT] Test suite succeeded`
  - error checker: `odoo.addons.web.tests.test_js.unit_test_error_checker`
    (returns `True` — i.e. "stop on this log line" — for any line that does
    **not** contain `[HOOT]`, so genuine JS/console errors abort the run
    instead of being swallowed).
- Demo-data flag: `without_demo = False` in `dev/odoo.conf` resolves
  internally to `with_demo = True` (demo data installed). Demo data is
  required for the core `point_of_sale` tours this addon's own tours are
  modeled on.
- Headless Chrome tours work inside the container, **but only after adding
  the Python `websocket-client` package** to the image (`dev/Dockerfile`).
  Without it, `HttpCase.start_pos_tour`/`browser_js` silently **skip** the
  test with `"websocket-client module is not installed"` instead of failing
  or running through Chrome — easy to mistake for a passing test.
- amd64-only constraint: Google does not publish an arm64
  `google-chrome-stable` `.deb`, so `dev/Dockerfile` only builds on amd64
  hosts. An ARM host needs a different headless-browser strategy — out of
  scope for this module, documented here as a known limitation.

## Confirmed image path for `odoo.tests.BaseCase` and Hoot lookups

For reference, the container image paths this doc's findings were read from:

- `/usr/lib/python3/dist-packages/odoo/addons/web/tests/test_js.py`
- `/usr/lib/python3/dist-packages/odoo/addons/web/static/lib/hoot/core/config.js`
- `/usr/lib/python3/dist-packages/odoo/addons/point_of_sale/tests/test_frontend.py`
