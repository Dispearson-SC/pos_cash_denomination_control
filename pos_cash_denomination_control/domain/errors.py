"""Typed domain errors.

Pure Python, no `odoo` import (enforced by `tests/test_domain_purity.py`).
Each error carries a stable machine `code` plus free-form `params` used by
`models/domain_errors.py` to build a translated, parameterized user message.
Error messages themselves never live here.
"""


class DomainError(Exception):
    """Base class for every domain-layer error."""

    def __init__(self, code, **params):
        self.code = code
        self.params = params
        super().__init__(code)


class BreakdownError(DomainError):
    """Denomination breakdown validation failure.

    Codes: MISSING, MALFORMED, NON_INTEGER_QUANTITY, NEGATIVE_QUANTITY,
    BILL_NOT_ALLOWED, DUPLICATE_BILL, TOTAL_MISMATCH.
    """


class ReasonError(DomainError):
    """Cash-move reason validation failure.

    Codes: MISSING, NOT_FOUND, INACTIVE, WRONG_COMPANY, DIRECTION_MISMATCH,
    VAULT_NOT_OUT.
    """


class MoveTypeError(DomainError):
    """Cash-move type validation failure.

    Codes: UNKNOWN_TYPE, CASH_IN_DISABLED.
    """
