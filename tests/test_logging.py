"""Guards on how much this integration writes to the log.

Home Assistant logs at INFO by default and rotates only its own
home-assistant.log, so a polling integration that logs progress at INFO -- or
that installs a file handler of its own, or that lets a library retry a request
it already knows will fail -- writes to disk on every cycle.

Stdlib only (no Home Assistant, no router libraries) so CI can run it.
"""

import ast
import sys
import unittest
from pathlib import Path

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "zte_router"
sys.path.insert(0, str(INTEGRATION))

from log_util import describe_text, redact, redact_phone  # noqa: E402


def integration_modules():
    for path in sorted(INTEGRATION.glob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"))


def function_def(module, name):
    _, tree = next(p for p in integration_modules() if p[0].name == module)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name}() not found in {module}")


def is_main_guard(test):
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and any(
            isinstance(c, ast.Constant) and c.value == "__main__" for c in test.comparators
        )
    )


class RedactionTest(unittest.TestCase):
    """Values that must never reach the log verbatim."""

    def test_redact_hides_the_value_but_keeps_the_length(self):
        self.assertEqual(redact("s3cr3t-token"), "<redacted, 12 chars>")
        self.assertNotIn("s3cr3t", redact("s3cr3t-token"))

    def test_redact_reports_missing_secrets_distinctly(self):
        # "no token at all" and "token of the wrong shape" are different bugs.
        self.assertEqual(redact(""), "<empty>")
        self.assertEqual(redact(None), "<empty>")

    def test_redact_phone_keeps_only_the_last_two_digits(self):
        self.assertEqual(redact_phone("+38591234567"), "**********67")
        self.assertEqual(redact_phone("13909"), "***09")
        self.assertEqual(redact_phone("7"), "*")
        self.assertEqual(redact_phone(""), "<empty>")

    def test_describe_text_never_reveals_the_body(self):
        self.assertEqual(describe_text("hello world"), "<11 chars>")
        self.assertNotIn("hello", describe_text("hello world"))


class LoggingPolicyTest(unittest.TestCase):
    """Static guards so the fix cannot silently regress."""

    def test_module_loggers_are_named_after_their_module(self):
        """Any other name escapes the user's `logger:` settings for this integration."""
        offenders = []
        for path, tree in integration_modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "getLogger":
                    for arg in node.args:
                        if not (isinstance(arg, ast.Name) and arg.id == "__name__"):
                            offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(
            offenders, [], "getLogger() must be called with __name__: " + ", ".join(offenders)
        )

    def test_no_log_handlers_are_installed_on_import(self):
        """A handler attached at import writes outside HA's rotation, so it grows unbounded.

        The only handlers left in the package belong to the standalone CLI.
        """
        offenders = []
        for path, tree in integration_modules():
            main_blocks = [
                (node.lineno, node.end_lineno)
                for node in ast.walk(tree)
                if isinstance(node, ast.If) and is_main_guard(node.test)
            ]
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "addHandler"):
                    continue
                if not any(start <= node.lineno <= end for start, end in main_blocks):
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(
            offenders,
            [],
            "addHandler() outside an `if __name__ == '__main__'` guard: " + ", ".join(offenders),
        )


class ProtocolProbeTest(unittest.TestCase):
    """urllib3 logs a WARNING per retry, under its own logger name, so retrying a
    scheme the modem refuses floods home-assistant.log once per poll -- and the
    user's log level for this integration cannot mute it."""

    def test_the_scheme_probe_does_not_retry(self):
        retries = [
            kw.value
            for node in ast.walk(function_def("mc.py", "try_set_protocol"))
            if isinstance(node, ast.Call)
            for kw in node.keywords
            if kw.arg == "retries"
        ]
        self.assertTrue(retries, "the scheme probe must pass retries= explicitly")
        for value in retries:
            self.assertIsInstance(value, ast.Constant)
            self.assertIs(value.value, False)

    def test_red_crypto_does_not_hardcode_a_scheme(self):
        """It must follow what the probe found, not re-probe https on an http-only modem."""
        literals = [
            node.value
            for node in ast.walk(function_def("mc.py", "_setup_red_crypto"))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        self.assertEqual([lit for lit in literals if lit.startswith("https://")], [])


if __name__ == "__main__":
    unittest.main()
