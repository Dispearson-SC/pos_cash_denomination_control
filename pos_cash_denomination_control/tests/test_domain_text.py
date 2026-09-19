"""Domain-unit tests for `compose_payment_text`.

Covers the pure-function extraction of spec `cash-move-reasons`'s
`payment_ref` text-composition scenarios (Requirement: Reason Storage And
`payment_ref` Composition). Full `payment_ref` composition and storage is
verified at the TransactionCase level in Phase 4.
"""

from odoo.tests import BaseCase, tagged

from odoo.addons.pos_cash_denomination_control.domain.text import compose_payment_text


@tagged("at_install", "pcdc", "pcdc_domain")
class TestDomainText(BaseCase):
    def test_payment_text_contains_only_the_reason_name_when_no_note_is_given(self):
        self.assertEqual(compose_payment_text("Vault", None), "Vault")

    def test_payment_text_contains_the_reason_name_followed_by_the_note_when_given(self):
        self.assertEqual(compose_payment_text("Vault", "till audit"), "Vault: till audit")

    def test_payment_text_with_empty_string_note_behaves_as_no_note(self):
        self.assertEqual(compose_payment_text("Vault", ""), "Vault")
