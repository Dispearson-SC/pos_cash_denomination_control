"""AST purity check: no `domain/*.py` module may import `odoo`.

Design.md "Test discovery": this test enforces the "no ORM in the domain
layer" boundary by parsing every `domain/*.py` file with `ast` and failing on
any `import odoo` / `from odoo...` statement.
"""

import ast
import os

from odoo.tests import BaseCase, tagged

_DOMAIN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "domain")


def _find_odoo_imports(file_path):
    with open(file_path, "r", encoding="utf-8") as fobj:
        tree = ast.parse(fobj.read(), filename=file_path)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "odoo" or alias.name.startswith("odoo."):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "odoo" or node.module.startswith("odoo.")):
                violations.append(node.module)
    return violations


@tagged("at_install", "pcdc", "pcdc_domain")
class TestDomainPurity(BaseCase):
    def test_no_domain_module_imports_odoo(self):
        offenders = {}
        for filename in sorted(os.listdir(_DOMAIN_DIR)):
            if not filename.endswith(".py"):
                continue
            violations = _find_odoo_imports(os.path.join(_DOMAIN_DIR, filename))
            if violations:
                offenders[filename] = violations
        self.assertEqual(offenders, {}, f"domain modules importing odoo: {offenders}")
