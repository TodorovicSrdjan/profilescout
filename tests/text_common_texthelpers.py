import pytest

from context import profilescout
from profilescout.common.texthelpers import longest_common_substring


class TestLongestCommonSubstring:
    def test_longest_common_substring_when_strings_have_common_string(self):
        result = longest_common_substring("Hello World", "World, Hello!")
        assert result == "Hello"
        result = longest_common_substring("ABCDEFGH", "0123ABCDGH")
        assert result == "ABCD"

    def test_longest_common_substring_when_strings_have_no_common_string(self):
        result = longest_common_substring("ABCDEF", "123456")
        assert result == ""

    def test_longest_common_substring_when_strings_are_empty(self):
        result = longest_common_substring("", "")
        assert result == ""

    def test_longest_common_substring_when_strings_are_same(self):
        result = longest_common_substring("Python", "Python")
        assert result == "Python"

    def test_longest_common_substring_when_one_string_is_empty(self):
        result = longest_common_substring("Hello", "")
        assert result == ""

    def test_longest_common_substring_when_case_is_lower(self):
        result = longest_common_substring("Petar Petrovic", "dr petar Petrovic", case_sensitive=False)
        assert result == "petar petrovic"