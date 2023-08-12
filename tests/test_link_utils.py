import pytest
from unittest import mock

from context import profilescout
from profilescout.link.utils import (
    replace_param_vals,
    most_common_format,
    match_profile_fmt,
    is_valid_sublink)
from profilescout.link.utils import (
    filter_out_invalid,
    filter_out_long,
    filter_out_present_links,
    filter_out_visited,
    with_and_without_www)

@pytest.fixture
def page_links():
    class Link:
        def __init__(self, url):
            self.url = url

        def __repr__(self):
            return self.url

    return [
        Link('https://example.com/link1'),
        Link('http://www.example.com/link2'),
        Link('https://www.example.com/link3'),
        Link('http://example.com/link4'),
        Link('https://www.anotherexample.com/link5'),
        Link('https://www.example.com/index.php?id=123#fragment'),
        Link('#'),
        Link('mailto:user@example.com'),
    ]

@pytest.fixture
def visited_links():
    return [
        'https://example.com/link1',
        'https://www.example.com/link3'
    ]

@pytest.fixture
def links_to_visit():
    class Link:
        def __init__(self, url):
            self.url = url

    return [
        Link('http://example.com/link2'),
        Link('http://example.com/link4')
    ]


@pytest.fixture
def mocker():
    return mock.Mock()


class TestMostCommonFormat:
    '''Examples:
    'https://example.com/user/123',
    'https://example.com/user/456',
    'https://example.com/product/789',
    'https://example.com/product/123',
    'https://example.com/user/789',
    => 'https://example.com/user/####'


    'https://example.com/user?id=123',
    'https://example.com/user?id=456',
    'https://example.com/user?id=789',
    'https://example.com/user?id=123&page=cv',
    'https://example.com/user?id=789&page=cv',
    => 'https://example.com/user?id=####'


    'https://example.com/user?id=123',
    'https://example.com/user?id=456',
    'https://example.com/product?id=789',
    'https://example.com/product?id=123',
    'https://example.com/user?id=789',
    => 'https://example.com/user?id=####'


    'https://example.com/user/123/profile?page=cv',
    'https://example.com/user/456/profile?page=cv',
    'https://example.com/user/789/profile?page=cv',
    'https://example.com/user/123/profile?page=cv',
    'https://example.com/user/789/profile?page=cv',
    => 'https://example.com/user/####/profile?page=cv'


    'https://example.com/user/123/profile?page=cv',
    'https://example.com/user/456/profile?page=publications',
    'https://example.com/user/789/profile?page=publications',
    'https://example.com/user/123/profile?page=contact',
    'https://example.com/user/789/profile?page=cv',
    => 'https://example.com/user/####/profile?page=####'
    '''


    def test_most_common_format_with_different_paths(self):
        urls = [
            'https://example.com/user/123',
            'https://example.com/user/456',
            'https://example.com/product/789',
            'https://example.com/product/123',
            'https://example.com/user/789',
        ]
        expected_result = 'https://example.com/user/####'

        assert most_common_format(urls) == expected_result

    def test_most_common_format_with_different_paths_and_queries(self):
        urls = [
            'https://example.com/user?id=123',
            'https://example.com/user?id=456',
            'https://example.com/product?id=789',
            'https://example.com/product?id=123',
            'https://example.com/user?id=789',
        ]
        expected_result = 'https://example.com/user?id=####'

        assert most_common_format(urls) == expected_result

    def test_most_common_format_with_same_paths_and_different_queries(self):
        urls = [
            'https://example.com/user?id=123',
            'https://example.com/user?id=456',
            'https://example.com/user?id=789',
            'https://example.com/user?id=123&page=cv',
            'https://example.com/user?id=789&page=cv',
        ]
        expected_result = 'https://example.com/user?id=####'

        assert most_common_format(urls) == expected_result

    def test_most_common_format_with_different_paths_and_same_queries(self):
        urls = [
            'https://example.com/user/123/profile?page=cv',
            'https://example.com/user/456/profile?page=cv',
            'https://example.com/user/789/profile?page=cv',
            'https://example.com/user/123/profile?page=cv',
            'https://example.com/user/789/profile?page=cv',
        ]
        expected_result = 'https://example.com/user/####/profile?page=####'

        assert most_common_format(urls) == expected_result

    def test_most_common_format_with_custom_placeholder(self):
        urls = [
            'https://example.com/user/123',
            'https://example.com/user/456',
            'https://example.com/product/789',
            'https://example.com/product/123',
            'https://example.com/user/789',
        ]
        placeholder = '****'
        expected_result = 'https://example.com/user/****'

        assert most_common_format(urls, placeholder) == expected_result

    def test_most_common_format_for_same_url(self):
        urls = [
            'https://example.com/user/123',
            'https://example.com/user/123',
            'https://example.com/user/123',
        ]
        expected_result = 'https://example.com/user/123'

        assert most_common_format(urls) == expected_result

    def test_most_common_format_with_placeholder_on_all_parts(self):
        urls = [
            'https://example.com/user/123',
            'https://example.com/profile/456',
            'https://example.com/product/789',
        ]

        assert most_common_format(urls) == 'https://example.com/####/####'

    def test_most_common_format_with_single_url(self):
        urls = [
            'https://example.com/user/123',
        ]
        expected_result = 'https://example.com/user/123'

        assert most_common_format(urls) == expected_result

    def test_most_common_format_with_empty_urls(self):
        urls = []

        assert most_common_format(urls) is None


class TestWithAndWithoutWWW:
    def test_with_and_without_www(self):
        assert with_and_without_www('http://www.example.com') == ('http://www.example.com', 'http://example.com')
        assert with_and_without_www('https://example.com') == ('https://www.example.com', 'https://example.com')

    def test_with_and_without_www_without_scheme(self):
        assert with_and_without_www('www.example.com') == ('www.example.com', 'example.com')
        assert with_and_without_www('example.com') == ('www.example.com', 'example.com')


class TestFilterOutVisited:
    def test_filter_out_visited(self, page_links, visited_links):
        expected_result = [
            page_links[1],  # http://www.example.com/link2
            page_links[3],  # http://example.com/link4
            page_links[4],  # https://www.anotherexample.com/link5
            page_links[5],  # https://www.example.com/index.php?id=123#fragment
            page_links[6],  # #
            page_links[7],  # mailto:user@example.com
        ]
        result = filter_out_visited(page_links, visited_links)
        assert result == expected_result


class TestFilterOutInvalid:
    def test_filter_out_invalid(self, page_links, mocker):
        def mock_is_valid(url, base_url):
            return url in [page_links[0].url, page_links[1].url, page_links[2].url, page_links[3].url]

        mocker.patch('profilescout.link.utils.is_valid', mock_is_valid)
        base_url = 'https://example.com'
        expected_result = [
            page_links[0],  # https://example.com/link1
            page_links[1],  # http://www.example.com/link2
            page_links[2],  # https://www.example.com/link3
            page_links[3],  # http://example.com/link4
            page_links[5]   # https://www.example.com/index.php?id=123#fragment
        ]
        result = filter_out_invalid(page_links, base_url)
        assert result == expected_result


class TestFilterOutPresentLinks:
    def test_filter_out_present_links(self, page_links, links_to_visit):
        expected_result = [
            page_links[0],  # https://example.com/link1
            page_links[2],  # https://www.example.com/link3
            page_links[4],  # https://www.anotherexample.com/link5
            page_links[5],  # https://www.example.com/index.php?id=123#fragment
            page_links[6],  # #
            page_links[7],  # mailto:user@example.com
        ]
        result = filter_out_present_links(page_links, links_to_visit)
        assert result == expected_result