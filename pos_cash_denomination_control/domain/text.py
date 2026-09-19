"""Pure text composition for the `payment_ref` reason segment.

Pure Python: no `odoo` import. See specs/cash-move-reasons/spec.md
(Requirement: Reason Storage And `payment_ref` Composition).
"""


def compose_payment_text(reason_name, note):
    """"Vault" or "Vault: note" when a non-empty note is given."""
    if note:
        return f"{reason_name}: {note}"
    return reason_name
