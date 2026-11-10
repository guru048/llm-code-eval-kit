"""
string_utils v3 — poor quality, mostly stub / hallucinated implementations.
Simulates a low-quality LLM output: functions exist but are mostly wrong.

Bugs introduced:
  - reverse_string returns the original string (no-op)
  - is_palindrome always returns False (stub)
  - count_vowels returns length of string instead of vowel count
  - title_case returns uppercased string instead of title case
"""


def reverse_string(s: str) -> str:
    # Bug: returns original string unchanged
    return s


def is_palindrome(s: str) -> bool:
    # Bug: always returns False (hallucination / stub)
    return False


def count_vowels(s: str) -> int:
    # Bug: returns total length instead of vowel count
    return len(s)


def title_case(s: str) -> str:
    # Bug: uppercases entire string instead of title-casing
    return s.upper()
