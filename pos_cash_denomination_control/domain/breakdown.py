"""Denomination breakdown parsing and validation.

Pure Python: no `odoo` import. See specs/denomination-breakdown-domain/spec.md.
"""

from dataclasses import dataclass
from decimal import Decimal

from .errors import BreakdownError
from .money import compare_amounts


@dataclass(frozen=True)
class BreakdownLine:
    bill_id: int
    bill_value: float
    quantity: int


@dataclass(frozen=True)
class Breakdown:
    lines: tuple
    total: float


def _is_integral_quantity(quantity):
    """True for `int` or an integral `float`; `bool` and `str` are rejected."""
    if isinstance(quantity, bool):
        return False
    if isinstance(quantity, int):
        return True
    if isinstance(quantity, float):
        return quantity.is_integer()
    return False


def parse_lines(raw, allowed_bills):
    """Parse and validate raw `{"bill_id", "quantity"}` dicts.

    `allowed_bills` maps `bill_id -> bill_value`. Duplicates, negative or
    non-integer quantities, and bills outside `allowed_bills` are rejected.
    Zero-quantity lines are dropped from the result.
    """
    seen_bill_ids = set()
    lines = []
    for entry in raw:
        bill_id = entry.get("bill_id")
        quantity = entry.get("quantity")

        if bill_id not in allowed_bills:
            raise BreakdownError("BILL_NOT_ALLOWED", bill_id=bill_id)

        if bill_id in seen_bill_ids:
            raise BreakdownError("DUPLICATE_BILL", bill_id=bill_id)
        seen_bill_ids.add(bill_id)

        if not _is_integral_quantity(quantity):
            raise BreakdownError("NON_INTEGER_QUANTITY", bill_id=bill_id, quantity=quantity)

        quantity = int(quantity)
        if quantity < 0:
            raise BreakdownError("NEGATIVE_QUANTITY", bill_id=bill_id, quantity=quantity)

        if quantity == 0:
            continue

        lines.append(
            BreakdownLine(bill_id=bill_id, bill_value=allowed_bills[bill_id], quantity=quantity)
        )
    return tuple(lines)


def compute_total(lines):
    """Sum(quantity * bill_value) over `lines`, computed with `Decimal`."""
    total = Decimal("0")
    for line in lines:
        total += Decimal(str(line.bill_value)) * Decimal(line.quantity)
    return float(total)


def validate_breakdown(raw, amount, allowed_bills, rounding, required):
    """Validate a raw breakdown against a declared `amount`.

    - `raw is None` and `required` -> `BreakdownError("MISSING")`.
    - `raw is None` and not `required` -> `None` (stock path, no breakdown).
    - Otherwise parse the lines, compute the total, and reject a mismatch
      against `amount` beyond `rounding` tolerance, regardless of `required`.
    """
    if raw is None:
        if required:
            raise BreakdownError("MISSING")
        return None

    lines = parse_lines(raw, allowed_bills)
    total = compute_total(lines)
    if compare_amounts(total, amount, rounding) != 0:
        raise BreakdownError("TOTAL_MISMATCH", total=total, amount=amount)
    return Breakdown(lines=lines, total=total)
