"""
string_utils v1 — correct implementation.
Simulates a high-quality LLM output that passes all tests.
"""


def reverse_string(s: str) -> str:
    """Return the reverse of string s."""
    return s[::-1]


def is_palindrome(s: str) -> bool:
    """Return True if s reads the same forwards and backwards (case-insensitive)."""
    normalised = s.lower()
    return normalised == normalised[::-1]


def count_vowels(s: str) -> int:
    """Count the number of vowels (a, e, i, o, u) in s, case-insensitively."""
    return sum(1 for c in s.lower() if c in "aeiou")


def title_case(s: str) -> str:
    """Convert s to title case: first letter of each word uppercase, rest lowercase."""
    return " ".join(word.capitalize() for word in s.split())
