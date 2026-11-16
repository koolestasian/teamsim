"""Tests for the canonical form: golden vectors, rejected values, the strict reader."""

import hashlib
import json
import pathlib
import unittest
from collections import OrderedDict

from teamsim import canon
from teamsim.canon import CanonError

GOLDEN = pathlib.Path(__file__).parent / "golden" / "canon_vectors.json"

# A backslash followed by "u": the start of a JSON escape, spelled this way so
# that no escape in this file depends on how an editor treats the sequence.
U = "\\u"

E_ACUTE = "\xe9"  # U+00E9, precomposed: NFC
E_THEN_ACUTE = "e" + chr(0x0301)  # U+0065 U+0301, decomposed: not NFC
HIGH_SURROGATE = chr(0xD83D)
LOW_SURROGATE = chr(0xDE00)
BYTE_ORDER_MARK = chr(0xFEFF)


def unhex(text: str) -> bytes:
    return bytes.fromhex(text)


# Expected bytes written by hand for a subset of the golden vectors. They are
# compared with the golden file, so the file cannot drift from them unnoticed.
HAND_WRITTEN = {
    "string-empty": b'""',
    "string-ascii": b'"hello world"',
    "string-quote": rb'"say \"hi\""',
    "string-backslash": rb'"a\\b"',
    "string-solidus-not-escaped": b'"a/b"',
    "string-backspace": rb'"\b"',
    "string-form-feed": rb'"\f"',
    "string-line-feed": rb'"\n"',
    "string-carriage-return": rb'"\r"',
    "string-tab": rb'"\t"',
    # quote, backslash, u, 0, 0, 0, 0, quote
    "string-nul": unhex("22 5c 75 30 30 30 30 22"),
    "string-del-is-literal": unhex("22 7f 22"),
    "string-latin": unhex("22 63 61 66 c3 a9 22"),
    "string-cjk": unhex("22 e6 97 a5 e6 9c ac e8 aa 9e 22"),
    "string-astral-emoji": unhex("22 f0 9f 98 80 22"),
    "integer-zero": b"0",
    "integer-minus-one": b"-1",
    "integer-max": b"9007199254740991",
    "integer-min": b"-9007199254740991",
    "boolean-true": b"true",
    "boolean-false": b"false",
    "array-empty": b"[]",
    "object-empty": b"{}",
    "nested-empty-containers": b'[[],{},[[]],{"a":{}}]',
    "object-two-keys": b'{"a":2,"b":1}',
    "object-key-alphabet": b'{"-":8,".":7,"0":6,"9":5,":":4,"_":3,"a":2,"z":1}',
    "object-nested-sorting": b'{"a":"x","z":{"a":true,"b":[{"c":2,"d":1}]}}',
    "timeline-event": (
        b'{"actor":"ana","at":86400000,"discloses":["beta-date.2"],"id":"e041",'
        b'"kind":"post","surface":"general",'
        b'"text":"beta moves to tuesday 14 april, too many open crashes"}'
    ),
}

# RFC 8785 (https://www.rfc-editor.org/rfc/rfc8785, read 2026-11-15): the
# "string" member of the sample in section 3.2.2, and its bytes as listed in
# hexadecimal in section 3.2.4.
RFC_8785_STRING_TEXT = (
    f"\"{U}20ac${U}000F{U}000aA'{U}0042{U}0022{U}005c" + r'\\\"\/"'
)
RFC_8785_STRING_BYTES = unhex(
    "22 e2 82 ac 24 5c 75 30 30 30 66 5c 6e 41 27 42 5c 22 5c 5c 5c 5c 5c 22 2f 22"
)

# What the brief for the vectors asks for, by vector name.
REQUIRED_VECTORS = (
    "string-greek",
    "string-cyrillic",
    "string-arabic",
    "string-devanagari",
    "string-cjk",
    "string-hangul",
    "string-astral-emoji",
    "string-astral-three-planes",
    "string-quote",
    "string-backslash",
    "string-backspace",
    "string-form-feed",
    "string-line-feed",
    "string-carriage-return",
    "string-tab",
    "string-all-c0-controls",
    "string-del-is-literal",
    "object-nested-sorting",
    "object-key-alphabet",
    "array-empty",
    "object-empty",
    "integer-zero",
    "integer-minus-one",
    "integer-max",
    "integer-min",
    "boolean-true",
    "boolean-false",
    "rfc8785-3.2.2-string",
)


def load_vectors() -> list[dict]:
    # Read with the standard library, not with the reader under test.
    return json.loads(GOLDEN.read_bytes())["vectors"]


def reference_bytes(value: object) -> bytes:
    """Python's own serialiser, as an independent route to the same bytes."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text.encode("utf-8")


class GoldenVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vectors = load_vectors()
        cls.by_name = {vector["name"]: vector for vector in cls.vectors}

    def test_at_least_thirty_vectors_with_unique_names(self) -> None:
        self.assertGreaterEqual(len(self.vectors), 30)
        self.assertEqual(len(self.by_name), len(self.vectors))

    def test_required_cases_are_present(self) -> None:
        for name in REQUIRED_VECTORS:
            with self.subTest(name=name):
                self.assertIn(name, self.by_name)

    def test_canon_gives_the_expected_bytes(self) -> None:
        for vector in self.vectors:
            with self.subTest(name=vector["name"]):
                expected = bytes.fromhex(vector["canon_hex"])
                self.assertEqual(canon.canon(vector["value"]), expected)

    def test_hash_of_gives_the_expected_hash(self) -> None:
        for vector in self.vectors:
            with self.subTest(name=vector["name"]):
                self.assertEqual(canon.hash_of(vector["value"]), vector["sha256"])

    def test_file_hashes_are_the_sha256_of_the_file_bytes(self) -> None:
        for vector in self.vectors:
            with self.subTest(name=vector["name"]):
                expected = bytes.fromhex(vector["canon_hex"])
                self.assertEqual(hashlib.sha256(expected).hexdigest(), vector["sha256"])

    def test_hand_written_bytes_match_the_file(self) -> None:
        for name, expected in HAND_WRITTEN.items():
            with self.subTest(name=name):
                vector = self.by_name[name]
                self.assertEqual(bytes.fromhex(vector["canon_hex"]), expected)
                self.assertEqual(canon.canon(vector["value"]), expected)

    def test_expected_bytes_match_an_independent_serialiser(self) -> None:
        for vector in self.vectors:
            with self.subTest(name=vector["name"]):
                self.assertEqual(
                    reference_bytes(vector["value"]), bytes.fromhex(vector["canon_hex"])
                )

    def test_rfc_8785_string_example(self) -> None:
        vector = self.by_name["rfc8785-3.2.2-string"]
        self.assertEqual(vector["text"], RFC_8785_STRING_TEXT)
        self.assertEqual(bytes.fromhex(vector["canon_hex"]), RFC_8785_STRING_BYTES)
        value = canon.parse(RFC_8785_STRING_TEXT)
        self.assertEqual(value, json.loads(RFC_8785_STRING_TEXT))
        self.assertEqual(canon.canon(value), RFC_8785_STRING_BYTES)

    def test_rfc_8785_sample_without_null_and_numbers(self) -> None:
        vector = self.by_name["rfc8785-3.2.2-sample-without-null-and-numbers"]
        expected = (
            b'{"literals":[true,false],"string":' + RFC_8785_STRING_BYTES + b"}"
        )
        self.assertEqual(bytes.fromhex(vector["canon_hex"]), expected)
        self.assertEqual(canon.canon(canon.parse(vector["text"])), expected)

    def test_check_accepts_every_vector(self) -> None:
        for vector in self.vectors:
            with self.subTest(name=vector["name"]):
                self.assertIsNone(canon.check(vector["value"]))

    def test_parse_reads_the_canonical_bytes_back(self) -> None:
        for vector in self.vectors:
            with self.subTest(name=vector["name"]):
                expected = bytes.fromhex(vector["canon_hex"])
                self.assertEqual(canon.parse(expected), vector["value"])
                self.assertEqual(canon.parse(expected.decode("utf-8")), vector["value"])
                self.assertEqual(canon.canon(canon.parse(expected)), expected)

    def test_parse_reads_the_source_text(self) -> None:
        with_text = [vector for vector in self.vectors if "text" in vector]
        self.assertGreaterEqual(len(with_text), 5)
        for vector in with_text:
            with self.subTest(name=vector["name"]):
                self.assertEqual(canon.parse(vector["text"]), vector["value"])
                self.assertEqual(
                    canon.parse(vector["text"].encode("utf-8")), vector["value"]
                )

    def test_the_golden_file_is_itself_a_canonical_value(self) -> None:
        data = GOLDEN.read_bytes()
        self.assertTrue(data.isascii())
        self.assertEqual(canon.parse(data), json.loads(data))


class CanonBehaviourTests(unittest.TestCase):
    def test_canon_returns_bytes_and_hash_of_returns_lower_case_hex(self) -> None:
        self.assertIs(type(canon.canon({"a": 1})), bytes)
        digest = canon.hash_of({"a": 1})
        self.assertIs(type(digest), str)
        self.assertEqual(digest, hashlib.sha256(b'{"a":1}').hexdigest())
        self.assertEqual(digest, digest.lower())
        self.assertEqual(len(digest), 64)

    def test_key_insertion_order_does_not_matter(self) -> None:
        self.assertEqual(canon.canon({"b": 1, "a": 2}), canon.canon({"a": 2, "b": 1}))
        self.assertEqual(
            canon.hash_of({"b": 1, "a": 2}), canon.hash_of({"a": 2, "b": 1})
        )

    def test_array_order_matters(self) -> None:
        self.assertNotEqual(canon.canon([1, 2]), canon.canon([2, 1]))

    def test_a_boolean_is_never_an_integer(self) -> None:
        self.assertEqual(canon.canon(True), b"true")
        self.assertEqual(canon.canon(False), b"false")
        self.assertEqual(canon.canon(1), b"1")
        self.assertEqual(canon.canon(0), b"0")
        self.assertEqual(canon.canon([True, 1, False, 0]), b"[true,1,false,0]")
        self.assertNotEqual(canon.hash_of(True), canon.hash_of(1))

    def test_the_input_is_not_changed(self) -> None:
        value = {"b": [3, 1, 2], "a": {"z": "x", "y": True}}
        before = json.dumps(value)
        canon.canon(value)
        canon.check(value)
        self.assertEqual(json.dumps(value), before)
        self.assertEqual(list(value), ["b", "a"])

    def test_check_returns_nothing(self) -> None:
        self.assertIsNone(canon.check({"a": [1, "x", True]}))

    def test_nfc_text_is_accepted(self) -> None:
        self.assertEqual(canon.canon(E_ACUTE), unhex("22 c3 a9 22"))

    def test_an_astral_character_is_accepted(self) -> None:
        self.assertEqual(canon.canon(chr(0x1F600)), unhex("22 f0 9f 98 80 22"))

    def test_sixty_four_nested_containers_are_accepted(self) -> None:
        value: list = []
        for _ in range(canon.MAX_DEPTH - 1):
            value = [value]
        self.assertEqual(
            canon.canon(value), b"[" * canon.MAX_DEPTH + b"]" * canon.MAX_DEPTH
        )

    def test_limits_are_the_documented_ones(self) -> None:
        self.assertEqual(canon.MAX_INT, 2**53 - 1)
        self.assertEqual(canon.MIN_INT, -(2**53 - 1))
        self.assertEqual(canon.MAX_DEPTH, 64)


class CanonRejectTests(unittest.TestCase):
    """Each value outside the form is rejected by canon, check and hash_of."""

    def assert_rejected(self, value: object, path: str, fragment: str) -> None:
        for function in (canon.canon, canon.check, canon.hash_of):
            with self.subTest(function=function.__name__):
                with self.assertRaises(CanonError) as caught:
                    function(value)
                self.assertEqual(caught.exception.path, path)
                self.assertIn(fragment, caught.exception.reason)

    def test_float(self) -> None:
        self.assert_rejected(1.5, "$", "floating-point")

    def test_float_with_an_integer_value(self) -> None:
        self.assert_rejected(1.0, "$", "floating-point")

    def test_float_not_a_number_and_infinity(self) -> None:
        self.assert_rejected(float("nan"), "$", "floating-point")
        self.assert_rejected(float("inf"), "$", "floating-point")

    def test_none(self) -> None:
        self.assert_rejected(None, "$", "null")

    def test_none_inside_an_array(self) -> None:
        self.assert_rejected([1, None], "$[1]", "null")

    def test_string_not_in_nfc(self) -> None:
        self.assert_rejected(E_THEN_ACUTE, "$", "NFC")

    def test_string_not_in_nfc_inside_an_object(self) -> None:
        self.assert_rejected({"name": E_THEN_ACUTE}, '$["name"]', "NFC")

    def test_lone_high_surrogate(self) -> None:
        self.assert_rejected(
            "a" + HIGH_SURROGATE, "$", "lone surrogate U+D83D at index 1"
        )

    def test_lone_low_surrogate(self) -> None:
        self.assert_rejected(LOW_SURROGATE, "$", "lone surrogate U+DE00")

    def test_surrogate_pair_held_as_two_code_points(self) -> None:
        self.assert_rejected(HIGH_SURROGATE + LOW_SURROGATE, "$", "lone surrogate")

    def test_key_with_an_upper_case_letter(self) -> None:
        self.assert_rejected({"Key": 1}, "$", "does not match")

    def test_empty_key(self) -> None:
        self.assert_rejected({"": 1}, "$", "does not match")

    def test_key_with_a_space(self) -> None:
        self.assert_rejected({"a b": 1}, "$", "does not match")

    def test_key_with_a_non_ascii_letter(self) -> None:
        self.assert_rejected({"caf" + E_ACUTE: 1}, "$", "does not match")

    def test_key_with_other_punctuation(self) -> None:
        for key in ("a/b", "a,b", "a+b", "a@b", "a\nb", '"'):
            with self.subTest(key=key):
                self.assert_rejected({key: 1}, "$", "does not match")

    def test_bad_key_in_a_nested_object(self) -> None:
        self.assert_rejected(
            {"a": [{"ok": 1}, {"Bad": 2}]}, '$["a"][1]', "does not match"
        )

    def test_integer_key(self) -> None:
        self.assert_rejected({1: "a"}, "$", "is not a string (int)")

    def test_boolean_key(self) -> None:
        self.assert_rejected({True: "a"}, "$", "is not a string (bool)")

    def test_none_key(self) -> None:
        self.assert_rejected({None: "a"}, "$", "is not a string (NoneType)")

    def test_tuple_key(self) -> None:
        self.assert_rejected({("a",): 1}, "$", "is not a string (tuple)")

    def test_keys_of_mixed_types_do_not_reach_the_sort(self) -> None:
        self.assert_rejected({"a": 1, 2: 3}, "$", "is not a string (int)")

    def test_integer_above_the_range(self) -> None:
        self.assert_rejected(2**53, "$", "outside")

    def test_integer_below_the_range(self) -> None:
        self.assert_rejected(-(2**53), "$", "outside")

    def test_very_large_integer(self) -> None:
        self.assert_rejected(10**400, "$", "outside")

    def test_integer_out_of_range_inside_an_array(self) -> None:
        self.assert_rejected([0, [2**64]], "$[1][0]", "outside")

    def test_unsupported_types(self) -> None:
        for value, name in (
            (b"bytes", "bytes"),
            (bytearray(b"x"), "bytearray"),
            ({1, 2}, "set"),
            (frozenset(), "frozenset"),
            (3 + 4j, "complex"),
            (object(), "object"),
            (range(3), "range"),
        ):
            with self.subTest(type=name):
                self.assert_rejected(value, "$", f"unsupported type {name}")

    def test_tuple(self) -> None:
        self.assert_rejected((1, 2), "$", "unsupported type tuple")
        self.assert_rejected({"a": ("x",)}, '$["a"]', "unsupported type tuple")

    def test_subclass_of_str(self) -> None:
        class Text(str):
            pass

        self.assert_rejected(Text("a"), "$", "unsupported type Text")

    def test_subclass_of_int(self) -> None:
        class Number(int):
            pass

        self.assert_rejected(Number(1), "$", "unsupported type Number")

    def test_subclass_of_list(self) -> None:
        class Items(list):
            pass

        self.assert_rejected(Items([1]), "$", "unsupported type Items")

    def test_subclass_of_dict(self) -> None:
        self.assert_rejected(OrderedDict(a=1), "$", "unsupported type OrderedDict")

    def test_subclass_of_str_as_a_key(self) -> None:
        class Text(str):
            pass

        self.assert_rejected({Text("a"): 1}, "$", "is not a string (Text)")

    def test_nesting_deeper_than_the_limit(self) -> None:
        value: list = []
        for _ in range(canon.MAX_DEPTH):
            value = [value]
        self.assert_rejected(value, "$" + "[0]" * canon.MAX_DEPTH, "nested deeper")

    def test_a_list_that_holds_itself(self) -> None:
        value: list = []
        value.append(value)
        self.assert_rejected(value, "$" + "[0]" * canon.MAX_DEPTH, "nested deeper")

    def test_the_error_names_the_path_of_the_offending_element(self) -> None:
        value = {"actors": [{"id": "ana"}, {"id": "bo"}, {"id": 1.5}]}
        with self.assertRaises(CanonError) as caught:
            canon.canon(value)
        self.assertEqual(caught.exception.path, '$["actors"][2]["id"]')
        self.assertEqual(
            str(caught.exception),
            '$["actors"][2]["id"]: floating-point numbers are not allowed',
        )

    def test_the_error_is_a_value_error(self) -> None:
        self.assertTrue(issubclass(CanonError, ValueError))
        with self.assertRaises(ValueError):
            canon.canon(None)


class ParseAcceptTests(unittest.TestCase):
    def test_types_are_exact(self) -> None:
        self.assertIs(canon.parse("true"), True)
        self.assertIs(canon.parse("false"), False)
        self.assertIs(type(canon.parse("1")), int)
        self.assertIs(type(canon.parse('"a"')), str)
        self.assertIs(type(canon.parse("[]")), list)
        self.assertIs(type(canon.parse("{}")), dict)

    def test_whitespace_around_tokens(self) -> None:
        self.assertEqual(canon.parse(' \t\r\n{ "a" : [ 1 , 2 ] } \n'), {"a": [1, 2]})

    def test_keys_in_any_order(self) -> None:
        self.assertEqual(canon.parse('{"b":1,"a":2}'), {"a": 2, "b": 1})

    def test_every_short_escape(self) -> None:
        text = r'"\" \\ \/ \b \f \n \r \t"'
        self.assertEqual(canon.parse(text), '" \\ / \b \f \n \r \t')

    def test_hexadecimal_escape_in_either_case(self) -> None:
        self.assertEqual(canon.parse(f'"{U}00e9{U}00E9"'), E_ACUTE + E_ACUTE)

    def test_escaped_surrogate_pair_is_one_character(self) -> None:
        self.assertEqual(canon.parse(f'"{U}d83d{U}de00"'), chr(0x1F600))
        self.assertEqual(canon.parse(f'"{U}D83D{U}DE00"'), chr(0x1F600))

    def test_escaped_key(self) -> None:
        self.assertEqual(canon.parse(f'{{"{U}0061":1}}'), {"a": 1})

    def test_minus_zero_reads_as_zero(self) -> None:
        value = canon.parse("-0")
        self.assertEqual(value, 0)
        self.assertIs(type(value), int)
        self.assertEqual(canon.canon(value), b"0")

    def test_boundary_integers(self) -> None:
        self.assertEqual(canon.parse("9007199254740991"), 2**53 - 1)
        self.assertEqual(canon.parse("-9007199254740991"), -(2**53 - 1))

    def test_utf8_bytes(self) -> None:
        self.assertEqual(canon.parse(unhex("22 c3 a9 22")), E_ACUTE)

    def test_sixty_four_nested_containers(self) -> None:
        text = "[" * canon.MAX_DEPTH + "]" * canon.MAX_DEPTH
        self.assertEqual(canon.canon(canon.parse(text)), text.encode("ascii"))


class ParseRejectTests(unittest.TestCase):
    """Each text outside the form is rejected, as str and as UTF-8 bytes."""

    def assert_unreadable(self, text: str, fragment: str, path: str = "$") -> None:
        forms: list[str | bytes] = [text]
        try:
            forms.append(text.encode("utf-8"))
        except UnicodeEncodeError:
            pass
        for data in forms:
            with self.subTest(form=type(data).__name__):
                with self.assertRaises(CanonError) as caught:
                    canon.parse(data)
                self.assertIn(fragment, caught.exception.reason)
                self.assertEqual(caught.exception.path, path)

    # --- numbers

    def test_fraction(self) -> None:
        self.assert_unreadable("1.5", "fraction")

    def test_fraction_with_an_integer_value(self) -> None:
        self.assert_unreadable("1.0", "fraction")
        self.assert_unreadable("-0.0", "fraction")

    def test_exponent(self) -> None:
        self.assert_unreadable("1e3", "exponent")

    def test_exponent_upper_case(self) -> None:
        self.assert_unreadable("1E3", "exponent")

    def test_exponent_with_a_sign(self) -> None:
        self.assert_unreadable("1e-3", "exponent")
        self.assert_unreadable("1e+3", "exponent")

    def test_fraction_and_exponent(self) -> None:
        self.assert_unreadable("1.5e3", "fraction")

    def test_float_inside_an_object(self) -> None:
        self.assert_unreadable('{"a":[1,2.5]}', "fraction", '$["a"][1]')

    def test_integer_above_the_range(self) -> None:
        self.assert_unreadable("9007199254740992", "outside")

    def test_integer_below_the_range(self) -> None:
        self.assert_unreadable("-9007199254740992", "outside")

    def test_integer_with_many_digits(self) -> None:
        self.assert_unreadable("1" + "0" * 400, "outside")

    def test_integer_out_of_range_inside_an_array(self) -> None:
        self.assert_unreadable("[0,18446744073709551616]", "outside", "$[1]")

    def test_leading_zero(self) -> None:
        self.assert_unreadable("01", "leading zeros")
        self.assert_unreadable("-01", "leading zeros")
        self.assert_unreadable("00", "leading zeros")

    def test_minus_sign_alone(self) -> None:
        self.assert_unreadable("-", "digit must follow")
        self.assert_unreadable("-a", "digit must follow")

    def test_plus_sign(self) -> None:
        self.assert_unreadable("+1", "unexpected character")

    def test_fraction_without_an_integer_part(self) -> None:
        self.assert_unreadable(".5", "unexpected character")

    def test_hexadecimal_number(self) -> None:
        self.assert_unreadable("0x10", "trailing data")

    def test_not_a_number_and_infinity(self) -> None:
        self.assert_unreadable("NaN", "unexpected character")
        self.assert_unreadable("Infinity", "unexpected character")
        self.assert_unreadable("-Infinity", "digit must follow")

    # --- null and other literals

    def test_null(self) -> None:
        self.assert_unreadable("null", "null is not allowed")

    def test_null_inside_an_object(self) -> None:
        self.assert_unreadable('{"a":{"b":null}}', "null is not allowed", '$["a"]["b"]')

    def test_literals_in_other_spellings(self) -> None:
        for text in ("True", "FALSE", "None", "nul", "tru", "undefined"):
            with self.subTest(text=text):
                self.assert_unreadable(text, "unexpected character")

    # --- objects

    def test_duplicate_key(self) -> None:
        self.assert_unreadable('{"a":1,"a":2}', "duplicate key", '$["a"]')

    def test_duplicate_key_with_equal_values(self) -> None:
        self.assert_unreadable('{"a":1,"a":1}', "duplicate key", '$["a"]')

    def test_duplicate_key_written_with_an_escape(self) -> None:
        self.assert_unreadable(f'{{"a":1,"{U}0061":2}}', "duplicate key", '$["a"]')

    def test_duplicate_key_in_a_nested_object(self) -> None:
        self.assert_unreadable(
            '{"x":[{"k":1,"j":2,"k":3}]}', "duplicate key", '$["x"][0]["k"]'
        )

    def test_key_with_an_upper_case_letter(self) -> None:
        self.assert_unreadable('{"Key":1}', "does not match")

    def test_empty_key(self) -> None:
        self.assert_unreadable('{"":1}', "does not match")

    def test_key_with_a_non_ascii_letter(self) -> None:
        self.assert_unreadable('{"caf' + E_ACUTE + '":1}', "does not match")

    def test_key_with_a_space(self) -> None:
        self.assert_unreadable('{"a b":1}', "does not match")

    def test_bad_key_in_a_nested_object(self) -> None:
        self.assert_unreadable('{"a":[{"B":1}]}', "does not match", '$["a"][0]')

    def test_key_that_is_not_a_string(self) -> None:
        self.assert_unreadable("{1:2}", "expected a string key")
        self.assert_unreadable("{true:2}", "expected a string key")
        self.assert_unreadable("{a:2}", "expected a string key")

    def test_missing_colon(self) -> None:
        self.assert_unreadable('{"a" 1}', "expected ':'", '$["a"]')

    def test_missing_value(self) -> None:
        self.assert_unreadable('{"a":}', "unexpected character", '$["a"]')

    def test_trailing_comma_in_an_object(self) -> None:
        self.assert_unreadable('{"a":1,}', "expected a string key")

    def test_missing_comma_in_an_object(self) -> None:
        self.assert_unreadable('{"a":1 "b":2}', "expected ',' or '}'")

    def test_object_not_closed(self) -> None:
        self.assert_unreadable('{"a":1', "expected ',' or '}'")
        self.assert_unreadable("{", "expected a string key")

    # --- arrays

    def test_trailing_comma_in_an_array(self) -> None:
        self.assert_unreadable("[1,]", "unexpected character", "$[1]")

    def test_leading_comma_in_an_array(self) -> None:
        self.assert_unreadable("[,1]", "unexpected character", "$[0]")

    def test_missing_comma_in_an_array(self) -> None:
        self.assert_unreadable("[1 2]", "expected ',' or ']'")

    def test_array_not_closed(self) -> None:
        self.assert_unreadable("[1", "expected ',' or ']'")
        self.assert_unreadable("[", "unexpected end of input", "$[0]")

    def test_nesting_deeper_than_the_limit(self) -> None:
        depth = canon.MAX_DEPTH + 1
        self.assert_unreadable(
            "[" * depth + "]" * depth, "nested deeper", "$" + "[0]" * canon.MAX_DEPTH
        )

    def test_very_deep_nesting_is_an_error_not_a_crash(self) -> None:
        self.assert_unreadable(
            "[" * 100000, "nested deeper", "$" + "[0]" * canon.MAX_DEPTH
        )

    # --- strings

    def test_string_not_in_nfc(self) -> None:
        self.assert_unreadable('"' + E_THEN_ACUTE + '"', "NFC")

    def test_string_not_in_nfc_written_with_an_escape(self) -> None:
        self.assert_unreadable(f'"e{U}0301"', "NFC")

    def test_string_not_in_nfc_inside_an_object(self) -> None:
        self.assert_unreadable(f'{{"name":"e{U}0301"}}', "NFC", '$["name"]')

    def test_escaped_lone_high_surrogate(self) -> None:
        self.assert_unreadable(f'"{U}d800"', "lone surrogate")

    def test_escaped_lone_low_surrogate(self) -> None:
        self.assert_unreadable(f'"{U}dc00"', "lone surrogate")

    def test_escaped_high_surrogate_followed_by_another_character(self) -> None:
        self.assert_unreadable(f'"{U}d800{U}0041"', "lone surrogate")
        self.assert_unreadable(f'"{U}d800x"', "lone surrogate")

    def test_escaped_surrogates_in_the_wrong_order(self) -> None:
        self.assert_unreadable(f'"{U}de00{U}d83d"', "lone surrogate")

    def test_two_escaped_high_surrogates(self) -> None:
        self.assert_unreadable(f'"{U}d83d{U}d83d"', "lone surrogate")

    def test_raw_lone_surrogate_in_text(self) -> None:
        self.assert_unreadable('"' + HIGH_SURROGATE + '"', "lone surrogate")

    def test_raw_surrogate_pair_in_text(self) -> None:
        self.assert_unreadable(
            '"' + HIGH_SURROGATE + LOW_SURROGATE + '"', "lone surrogate"
        )

    def test_surrogate_encoded_in_bytes(self) -> None:
        with self.assertRaises(CanonError) as caught:
            canon.parse(unhex("22 ed a0 80 22"))
        self.assertIn("not UTF-8", caught.exception.reason)

    def test_raw_control_character_in_a_string(self) -> None:
        self.assert_unreadable('"a\nb"', "control character U+000A must be escaped")
        self.assert_unreadable('"a\x00b"', "control character U+0000 must be escaped")
        self.assert_unreadable('"a\tb"', "control character U+0009 must be escaped")

    def test_string_not_closed(self) -> None:
        self.assert_unreadable('"abc', "string is not closed")
        self.assert_unreadable('"abc\\"', "string is not closed")

    def test_invalid_escape(self) -> None:
        self.assert_unreadable(r'"\x41"', "invalid escape")
        self.assert_unreadable(r'"\a"', "invalid escape")
        self.assert_unreadable(r'"\'"', "invalid escape")
        self.assert_unreadable('"\\', "invalid escape")

    def test_short_hexadecimal_escape(self) -> None:
        self.assert_unreadable(f'"{U}12"', "four hexadecimal digits")
        self.assert_unreadable(f'"{U}"', "four hexadecimal digits")

    def test_hexadecimal_escape_with_other_characters(self) -> None:
        self.assert_unreadable(f'"{U}00zz"', "four hexadecimal digits")
        self.assert_unreadable(f'"{U}+0e9"', "four hexadecimal digits")
        self.assert_unreadable(f'"{U}d83d{U}zzzz"', "four hexadecimal digits")

    def test_single_quoted_string(self) -> None:
        self.assert_unreadable("'a'", "unexpected character")

    # --- the whole text

    def test_trailing_data(self) -> None:
        for text in ("1 2", "{} x", "[] []", "true,", '"a" "b"', "1\n1", "{}}", "[]]"):
            with self.subTest(text=text):
                self.assert_unreadable(text, "trailing data")

    def test_two_lines(self) -> None:
        self.assert_unreadable('{"a":1}\n{"a":2}\n', "trailing data")

    def test_empty_input(self) -> None:
        self.assert_unreadable("", "unexpected end of input")

    def test_whitespace_only(self) -> None:
        self.assert_unreadable(" \n\t ", "unexpected end of input")

    def test_byte_order_mark(self) -> None:
        self.assert_unreadable(BYTE_ORDER_MARK + "1", "byte order mark")

    def test_other_whitespace(self) -> None:
        for space in ("\x0b", "\x0c", "\xa0", chr(0x2028), chr(0x3000)):
            with self.subTest(space=ascii(space)):
                self.assert_unreadable(space + "1", "unexpected character")

    def test_comment(self) -> None:
        self.assert_unreadable("// note\n1", "unexpected character")
        self.assert_unreadable("1 /* note */", "trailing data")

    def test_bytes_that_are_not_utf8(self) -> None:
        for data in (b'"\xff"', b'"\xc3"', b"\xc0\xaf", unhex("22 f4 90 80 80 22")):
            with self.subTest(data=data.hex()):
                with self.assertRaises(CanonError) as caught:
                    canon.parse(data)
                self.assertIn("not UTF-8", caught.exception.reason)

    def test_utf16_bytes(self) -> None:
        with self.assertRaises(CanonError):
            canon.parse("1".encode("utf-16"))

    def test_argument_of_another_type(self) -> None:
        for data in (None, 1, bytearray(b"1"), ["1"]):
            with self.subTest(type=type(data).__name__):
                with self.assertRaises(TypeError):
                    canon.parse(data)

    def test_the_message_gives_the_character_offset(self) -> None:
        with self.assertRaises(CanonError) as caught:
            canon.parse('{"a": [1, null]}')
        self.assertEqual(
            str(caught.exception), '$["a"][1]: null is not allowed (at character 10)'
        )


class _Numbers:
    """A fixed sequence of integers for building test values (no random module)."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.count = 0

    def below(self, n: int) -> int:
        self.count += 1
        digest = hashlib.sha256(f"{self.label}:{self.count}".encode("ascii")).digest()
        return int.from_bytes(digest[:8], "big") % n


# Pieces that stay NFC however they are joined: none is a combining mark or a
# character that composes with a neighbour.
_PIECES = (
    "a", "Z", "0", " ", '"', "\\", "/", "\b", "\f", "\n", "\r", "\t", "\x00", "\x1f",
    "\x7f", "\x80", E_ACUTE, chr(0x03A9), chr(0x65E5), chr(0x2028), chr(0xFFFF),
    chr(0x1F600), chr(0x10FFFF), "null", "1.5", "</script>",
)  # fmt: skip
_KEYS = ("a", "b", "aa", "a.b", "a-b", "a_b", "a:b", "0", "10", "9", "z", "id", "kind")
_INTEGERS = (0, 1, -1, 7, -42, 2**31, -(2**31), 2**53 - 1, -(2**53 - 1), 10**15)


def _build(numbers: _Numbers, depth: int) -> object:
    kind = numbers.below(3 if depth >= 4 else 6)
    if kind == 0:
        return "".join(
            _PIECES[numbers.below(len(_PIECES))] for _ in range(numbers.below(6))
        )
    if kind == 1:
        return _INTEGERS[numbers.below(len(_INTEGERS))]
    if kind == 2:
        return numbers.below(2) == 1
    if kind == 3:
        return [_build(numbers, depth + 1) for _ in range(numbers.below(5))]
    members: dict = {}
    for _ in range(numbers.below(5)):
        members[_KEYS[numbers.below(len(_KEYS))]] = _build(numbers, depth + 1)
    return members


class GeneratedValueTests(unittest.TestCase):
    """Five hundred built values, compared with Python's own JSON module."""

    @classmethod
    def setUpClass(cls) -> None:
        numbers = _Numbers("canon-generated-values")
        cls.values = [_build(numbers, 0) for _ in range(500)]

    def test_the_values_cover_every_type(self) -> None:
        kinds = {type(value) for value in self.values}
        self.assertEqual(kinds, {str, int, bool, list, dict})

    def test_canon_matches_the_independent_serialiser(self) -> None:
        for index, value in enumerate(self.values):
            with self.subTest(index=index):
                self.assertEqual(canon.canon(value), reference_bytes(value))

    def test_hash_of_is_the_sha256_of_canon(self) -> None:
        for index, value in enumerate(self.values):
            with self.subTest(index=index):
                self.assertEqual(
                    canon.hash_of(value),
                    hashlib.sha256(reference_bytes(value)).hexdigest(),
                )

    def test_parse_of_canon_is_the_value(self) -> None:
        for index, value in enumerate(self.values):
            with self.subTest(index=index):
                parsed = canon.parse(canon.canon(value))
                self.assertEqual(parsed, value)
                # equal values of different types (1 and True) must not pass
                self.assertEqual(reference_bytes(parsed), reference_bytes(value))

    def test_parse_reads_escaped_and_indented_text(self) -> None:
        for index, value in enumerate(self.values):
            with self.subTest(index=index):
                text = json.dumps(value, ensure_ascii=True, indent=2)
                self.assertEqual(canon.parse(text), value)
                self.assertEqual(canon.parse(text.encode("ascii")), value)

    def test_parse_agrees_with_the_standard_reader(self) -> None:
        for index, value in enumerate(self.values):
            with self.subTest(index=index):
                data = canon.canon(value)
                self.assertEqual(canon.parse(data), json.loads(data))


if __name__ == "__main__":
    unittest.main()
