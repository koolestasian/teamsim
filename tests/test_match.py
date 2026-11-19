"""Tests for form matching (engine spec section 6.2)."""

import ast
import pathlib
import unittest

from teamsim import match

SOURCE = pathlib.Path(__file__).parent.parent / "teamsim" / "match.py"


class Normalise(unittest.TestCase):
    def test_case_fold(self):
        self.assertEqual(match.normalise("Friday"), "friday")
        self.assertEqual(match.normalise("STRASSE"), match.normalise("straße"))

    def test_nfkc(self):
        self.assertEqual(match.normalise("ｆｒｉｄａｙ"), "friday")  # full width
        self.assertEqual(match.normalise("ﬁle"), "file")  # ligature
        self.assertEqual(match.normalise("é"), "é")  # combining accent

    def test_whitespace_collapses(self):
        self.assertEqual(match.normalise("  due\tthe \n\n 14th  "), "due the 14th")
        self.assertEqual(match.normalise("a b"), "a b")  # no-break space

    def test_not_a_string(self):
        with self.assertRaises(TypeError):
            match.normalise(b"bytes")


class Contains(unittest.TestCase):
    def test_simple(self):
        self.assertTrue(match.contains("The launch is on Friday.", "friday"))
        self.assertFalse(match.contains("The launch is on Thursday.", "friday"))

    def test_word_boundaries(self):
        self.assertFalse(match.contains("Fridays are quiet", "friday"))
        self.assertFalse(match.contains("unfriday", "friday"))
        self.assertFalse(match.contains("ticket_42", "42"))
        self.assertTrue(match.contains("ticket 42 is open", "42"))
        self.assertFalse(match.contains("1420", "42"))

    def test_later_occurrence_on_a_boundary_counts(self):
        self.assertTrue(match.contains("Fridays, but this Friday too", "friday"))

    def test_punctuation_edges_do_not_need_boundaries(self):
        self.assertTrue(match.contains("cost:$4,200.", "$4,200"))
        self.assertTrue(match.contains("budget=$4,200", "$4,200"))
        self.assertFalse(match.contains("$4,2001", "$4,200"))

    def test_multiword_form_across_odd_spacing(self):
        self.assertTrue(match.contains("ship it on\n  March   14", "march 14"))

    def test_unicode_letters_are_word_characters(self):
        self.assertFalse(match.contains("açaí", "aç"))
        self.assertTrue(match.contains("ваш код: ЗЕЛЁНЫЙ.", "зелёный"))

    def test_edges_of_text(self):
        self.assertTrue(match.contains("friday", "Friday"))
        self.assertFalse(match.contains("", "friday"))

    def test_empty_form_is_an_error(self):
        for form in ["", "   ", "\n"]:
            with self.subTest(form=form), self.assertRaises(ValueError):
                match.contains("anything", form)

    def test_find_returns_the_normalised_index(self):
        self.assertEqual(match.find("  Due  FRIDAY", "friday"), 4)
        self.assertEqual(match.find("Fridays", "friday"), -1)


class Pure(unittest.TestCase):
    def test_imports_only_unicodedata(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or ".")
        self.assertEqual(imported, {"unicodedata"})


if __name__ == "__main__":
    unittest.main()
