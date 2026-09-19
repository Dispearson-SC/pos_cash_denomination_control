"""Expected-cash computation and the vault withdrawal threshold rule.

Pure Python: no `odoo` import. See specs/vault-withdrawal-alert/spec.md.
"""

from dataclasses import dataclass
from decimal import Decimal

from .money import compare_amounts


def compute_expected_cash(opening, cash_payment_amounts, statement_line_amounts):
    """opening + sum(cash_payment_amounts) + sum(statement_line_amounts).

    Same order and inputs as the core `get_closing_control_data` formula, so
    a parity test can assert the two stay in sync.
    """
    total = Decimal(str(opening))
    for amount in cash_payment_amounts:
        total += Decimal(str(amount))
    for amount in statement_line_amounts:
        total += Decimal(str(amount))
    return float(total)


def is_withdrawal_required(expected, threshold, rounding):
    """A withdrawal is required only when `threshold` is positive and
    `expected` is at or above it, compared with currency rounding."""
    if threshold <= 0:
        return False
    return compare_amounts(expected, threshold, rounding) >= 0


@dataclass(frozen=True)
class VaultState:
    expected_cash: float
    threshold: float
    required: bool
