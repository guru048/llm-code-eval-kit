"""
string_utils v2 — partially correct with logic bugs.
Simulates a medium-quality LLM output: some functions work, others have subtle errors.

Bugs introduced:
  - is_palindrome does NOT normalise case (fails T7: 'Racecar')
  - count_vowels counts 'y' as a vowel (fails T12: 'rhythm' should be 0)
  - title_case uses str.title() which doesn't fully re-capitalise (passes basic cases)
"""


def reverse_string(s: str) -> str:
    return s[::-1]


def is_palindrome(s: str) -> bool:
    # Bug: missing .lower() — case-sensitive comparison
    return s == s[::-1]


def count_vowels(s: str) -> int:
    # Bug: includes 'y' as a vowel
    return sum(1 for c in s.lower() if c in "aeiouy")


def title_case(s: str) -> str:
    return s.title()
