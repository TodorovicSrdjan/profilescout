import tldextract

from common.constants import ConstantsNamespace
from link.hop import PageLink


constants = ConstantsNamespace


def convert_links_to_absolute_path(page_links, base_url, current_link):
    # fix relative links or links that start with '/'
    abs_links = []
    for pl in page_links:
        link, depth = pl.url, pl.depth
        fixed_link = ''
        if link.startswith('http'):
            fixed_link = link
        elif link.startswith('www'):
            fixed_link = 'http://' + link
        else:
            # relative path or absoulte path from '/'
            if link[0] == '/':
                # absolute path
                if base_url[-1] == '/':
                    link = link[1:]  # remove '/' since base_url ends with one
                fixed_link = base_url + link
            else:
                # relative path
                if current_link[-1] != '/':
                    link = '/' + link
                fixed_link = current_link + link
        abs_links += [PageLink(fixed_link, depth)]

    return abs_links


def convert_to_fqdn(url):
    return tldextract.extract(url).fqdn


def convert_to_base_url(url):
    # extract base url from given url
    base_url = convert_to_fqdn(url)

    if 'https://' in url:
        base_url = 'https://' + base_url
    else:
        base_url = 'http://' + base_url

    return base_url + '/'
