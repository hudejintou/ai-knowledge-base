from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
import tempfile

from agent.tools import calculator, file_reader


class CalculatorTests(TestCase):
    def test_basic_arithmetic(self):
        self.assertEqual(calculator.calculate("3 * (4 + 5)")["result"], 27)

    def test_negative_and_division(self):
        self.assertEqual(calculator.calculate("-(4 + 5) / 3")["result"], -3.0)

    def test_empty_is_invalid(self):
        self.assertEqual(calculator.calculate("  ")["error"], "invalid_expression")

    def test_too_long_is_invalid(self):
        self.assertEqual(calculator.calculate("1+" * 150 + "1")["error"], "invalid_expression")

    def test_names_and_calls_rejected(self):
        for expr in ["__import__('os')", "abc", "print(1)", "2 ** 3", "[1]"]:
            with self.subTest(expr=expr):
                self.assertEqual(calculator.calculate(expr)["error"], "invalid_expression")

    def test_division_by_zero(self):
        self.assertEqual(calculator.calculate("1 / 0")["error"], "division_by_zero")


class FileReaderTests(TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        (self.base / "a.txt").write_text("hello", encoding="utf-8")
        (self.base / "big.txt").write_bytes(b"x" * (file_reader.MAX_BYTES + 1))
        (self.base / "bin.dat").write_bytes(b"\xff\xfe\x00")
        patcher = patch.object(file_reader, "BASE_DIR", self.base)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_read_ok(self):
        self.assertEqual(file_reader.read_file("a.txt")["content"], "hello")

    def test_path_traversal_rejected(self):
        for name in ["../secret", "/etc/passwd", "sub/a.txt", ".."]:
            with self.subTest(name=name):
                self.assertEqual(file_reader.read_file(name)["error"], "invalid_path")

    def test_missing_file(self):
        self.assertEqual(file_reader.read_file("nope.txt")["error"], "file_not_found")

    def test_too_large(self):
        self.assertEqual(file_reader.read_file("big.txt")["error"], "file_too_large")

    def test_not_text(self):
        self.assertEqual(file_reader.read_file("bin.dat")["error"], "not_text")

    def test_empty_name(self):
        self.assertEqual(file_reader.read_file("")["error"], "invalid_input")