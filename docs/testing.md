# Testing: pos_cash_denomination_control

## Bringing the stack up

```bash
docker compose build odoo          # first time, or after Dockerfile changes
docker compose up -d db odoo       # dev instance, reachable at http://localhost:8069
```

The compose project is named `caja-boveda` (see `name:` in `docker-compose.yml`),
so its containers/volumes/network are isolated from anything else on the host
(`caja-boveda-db-1`, `caja-boveda-odoo-1`, `caja-boveda_pgdata`,
`caja-boveda_odoo-data`, `caja-boveda_default`). Only Odoo's `8069` is
published to the host; Postgres is reachable only from other containers on
the compose network.

Stop it with `docker compose down` (add `-v` to also drop the named volumes,
i.e. wipe the dev database and filestore).

## Running tests

```bash
scripts/test.sh                              # install + full addon test suite
scripts/test.sh pos_hr                       # coexistence run, also installs pos_hr
scripts/test.sh "" -- --test-tags /pos_cash_denomination_control:pcdc_domain
```

`scripts/test.sh` always drops and recreates a disposable `pcdc_test`
database via `docker compose run --rm`, so it never touches the `db`
volume/data used by the `up -d` dev instance. Anything after `--` replaces
the default `--test-tags` value, which is the fast way to run one phase's
tag during development (for example `:pcdc_domain`, `:pcdc_cash_in`, ...).

**Known gotcha**: if the long-running dev `odoo` container (`up -d`) is
attached to the same Postgres server while a `scripts/test.sh` run tries to
`dropdb pcdc_test`, Postgres may refuse with "database is being accessed by
other users" if the dev instance ever queried `pcdc_test` (e.g. an earlier
manual test run against it). Stop the dev instance first (`docker compose
stop odoo`) if that happens, then bring it back with `docker compose up -d
odoo`.

### Fast domain-only loop (Phase 2 onward)

```bash
scripts/test.sh "" -- --test-tags /pos_cash_denomination_control:pcdc_domain
```

This runs only the pure-Python domain tests (`odoo.tests.BaseCase`, no
database access), which is the fastest feedback loop while iterating on
`domain/*.py`.

### `pos_hr` coexistence run

```bash
scripts/test.sh pos_hr
```

Installs `pos_cash_denomination_control,pos_hr` together and re-runs the
full suite, to catch any conflict between this addon's patches and `pos_hr`'s
own overrides of the same extension points (`try_cash_in_out`,
`_set_opening_control_data`, `CashMovePopup`, ...).

## Confirmed image facts (Phase 1, task 1.6–1.9)

- `from odoo.tests import BaseCase` exists; MRO is `odoo.tests.common.BaseCase
  → odoo.tests.case.TestCase → unittest.case.TestCase → object`. It is a
  plain `unittest.TestCase` with no cursor/env, so `--test-tags` and
  `@tagged(...)` both work; tags are stored on the class as `test_tags`, not
  `_tags`. Confirmed by decorating a throwaway `BaseCase` subclass with
  `@tagged("at_install", "pcdc", "pcdc_domain")` and reading `.test_tags`
  back inside the container.
- The Hoot runner (`odoo/addons/web/tests/test_js.py`,
  `web/static/lib/hoot/core/config.js`) accepts a `filter` URL query param
  (alias `name`) that matches a test/suite's full name **or its tags** as a
  search string, plus a `tag`/`tags` param for exact tag matching. For a
  standalone `HttpCase.browser_js` call (Phase 13's `tests/test_hoot.py`),
  use:
  - URL: `/web/tests?headless&loglevel=2&preset=desktop&filter=@pos_cash_denomination_control`
  - success signal: `[HOOT] Test suite succeeded`
  - error checker: `odoo.addons.web.tests.test_js.unit_test_error_checker`
    (returns `True` — i.e. "stop on this log line" — for any line that does
    **not** contain `[HOOT]`, so genuine JS/console errors abort the run
    instead of being swallowed).
  These come from the image's `odoo/addons/web/tests/test_js.py` (not present
  in the sparse `odoo-src/` clone) and its `HOOTCommon.test_unit_desktop`
  reference implementation.
- Demo-data flag: `without_demo = False` in `docker/odoo.conf` resolves
  internally to `with_demo = True` (demo data installed), confirmed by
  loading the config with `odoo.tools.config.parse_config(['-c',
  '/etc/odoo/odoo.conf'])` and reading `config.get('with_demo')`. This is
  also the default when neither `--with-demo` nor `--without-demo` is passed
  at all. Demo data is required for the core `point_of_sale` tours this
  addon's own tours are modeled on.
- Headless Chrome tours work inside the container, **but only after adding
  the Python `websocket-client` package** to the image (`docker/Dockerfile`).
  Without it, `HttpCase.start_pos_tour`/`browser_js` silently **skip** the
  test with `"websocket-client module is not installed"` instead of failing
  or running through Chrome — this is easy to mistake for a passing test.
  Confirmed fixed by installing a `point_of_sale` demo tour
  (`TestUi.test_01_pos_basic_order`, tour `pos_pricelist`) end-to-end:
  `╔══ TOUR pos_pricelist SUCCEEDED ══╗`, `0 failed, 0 error(s)`.
- amd64-only constraint: Google does not publish an arm64 `google-chrome-stable`
  `.deb`, so `docker/Dockerfile` only builds on amd64 hosts. An ARM host
  needs a different headless-browser strategy (e.g. `chromium` from a
  non-snap source, or Playwright's bundled Chromium) — out of scope for this
  change; documented here as a known limitation.

## Confirmed image path for `odoo.tests.BaseCase` and Hoot lookups

For reference, the container image paths this doc's findings were read from:

- `/usr/lib/python3/dist-packages/odoo/addons/web/tests/test_js.py`
- `/usr/lib/python3/dist-packages/odoo/addons/web/static/lib/hoot/core/config.js`
- `/usr/lib/python3/dist-packages/odoo/addons/point_of_sale/tests/test_frontend.py`
