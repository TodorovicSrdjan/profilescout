import re
import os
import sys
import random
import tldextract
from urllib.parse import urlparse

from dataclasses import dataclass

from profilescout.common.constants import ConstantsNamespace
from profilescout.common.exceptions import LongFilenameException


constants = ConstantsNamespace


@dataclass
class PageLink:
    url: str
    depth: int
    parent_url: str = None


def is_url(s):
    extracted = tldextract.extract(s)
    return bool(extracted.domain and extracted.suffix)


def is_valid(url, base_url):
    if not isinstance(url, str):
        return False

    if url == '.' or url == '' or url[-1] == '#':
        return False

    if url.startswith('mailto:') or url.startswith('tel:') or url.startswith('javascript:'):
        return False

    if '?nocache' in url:
        return False

    # search for url with filename and extension and check if exntension is invalid
    matched = re.search(r"^(https?://)?(www\.)?[a-zA-Z0-9_-]+(\.[a-zA-Z]{2,6})+(/\S*)*/\S+\.(\w{1,5})$", url)
    if matched:
        ext = matched.groups()[-1]
        if ext.lower() in constants.INVALID_EXTENSIONS:
            return False

    base_domain = tldextract.extract(base_url).domain
    link_domain = tldextract.extract(url).domain

    # TODO rethink; could cause problem with some sites that have profiles
    # on another url or as PDF/DOCX/...
    has_protocol = url.startswith('http://') or url.startswith('https://')
    if has_protocol and base_domain != link_domain:
        return False

    return True


def to_abs_path(page_links, base_url, current_link):
    # fix relative links or links that start with '/'
    abs_links = []
    for pl in page_links:
        link, depth, parent_url = pl.url, pl.depth, pl.parent_url
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
        abs_links += [PageLink(fixed_link, depth, parent_url)]

    return abs_links


def to_key(url):
    result = tldextract.extract(url)
    if result.subdomain in ['', 'www']:
        return result.domain
    if 'www' in result.subdomain:
        subdomain = result.subdomain.replace('www.', '')
    return f'{result.domain}-{subdomain}'


def to_fqdn(url):
    return tldextract.extract(url).fqdn


def to_base_url(url):
    # extract base url from given url
    base_url = to_fqdn(url)

    if 'https://' in url:
        base_url = 'https://' + base_url
    else:
        base_url = 'http://' + base_url

    return base_url + '/'


def remove_duplicates(page_links):
    unique_links = page_links

    i = 0
    n = len(unique_links)
    while i < n-1:
        j = i+1
        while j < n:
            if unique_links[i].url == unique_links[j].url:
                # update depth if there is better path
                if unique_links[i].depth > unique_links[j].depth:
                    unique_links[i].depth = unique_links[j].depth

                # delete duplicate
                del unique_links[j]
                j -= 1
                n -= 1
            j += 1
        i += 1

    return unique_links


def prioritize_relevant(link_queue):
    '''move relevant word at the beginning of the queue'''
    front = []
    rest = []
    for page_link in link_queue:
        has_relevant = False
        for word in constants.RELEVANT_WORDS:
            if word in page_link.url.lower():
                front.append(page_link)
                has_relevant = True
                break
        if not has_relevant:
            rest.append(page_link)

    return front + rest


def filter_out_invalid(page_links, base_url):
    result = filter(lambda pl: is_valid(pl.url, base_url),
                    page_links)
    return list(result)


def filter_out_visited(page_links, visited_links):
    result = filter(lambda pl: pl.url not in visited_links,
                    page_links)
    return list(result)


def filter_out_present_links(page_links, links_to_visit):
    result = filter(lambda pl: pl.url not in [to_visit.url for to_visit in links_to_visit],
                    page_links)
    return list(result)


def filter_out_long(page_links, err_file=sys.stderr):
    # exclude links that are overly long
    not_too_long = []
    for page_link in page_links:
        if len(page_link.url) > 310:
            print(f'WARN: url={page_link.url!r} is too long and may not be relevant. Ignored',
                  file=err_file)
        else:
            not_too_long.append(page_link)

    return not_too_long


def to_filename(url, export_path, extension):
    filename = url

    # remove '/' at the end
    if filename[-1] == '/':
        filename = filename[:-1]

    filename = filename.replace(f'__.{extension}', f'.{extension}')
    filename = filename.replace('http://', '').replace('https://', '')

    for unsafe_part in constants.CHAR_REPLACEMENTS.keys():
        if unsafe_part in filename:
            filename = filename.replace(unsafe_part, constants.CHAR_REPLACEMENTS[unsafe_part])

    # check if filename exceeds upper limit for number of characters
    limit = os.pathconf(export_path, 'PC_NAME_MAX')
    limit = min(limit, constants.FILENAME_MAX_LENGHT)
    if len(filename) + len(extension) + 1 > limit:
        raise LongFilenameException(filename, limit)
    else:
        filename += '.' + extension

    return filename


def url2file_path(link, export_path, extension, err_file=sys.stderr):
    filename = ''
    try:
        filename = to_filename(link, export_path, extension)
    except LongFilenameException as lfe:
        filename = lfe.args[0]

        # cut off chars that exceed limit
        filename = filename[:lfe.limit]

        # replace the remaining string with suffix and extension
        ext = '.' + extension
        suffix = constants.FILENAME_CUT_SUFFIX
        suffix += str(random.randint(1000, 9999))
        overwrite_len = len(suffix) + len(ext)
        filename = filename[:-overwrite_len] + suffix + ext
        print('WARN: Link was too long.',
              f'The filename of has changed to: {filename}',
              file=err_file)
    path = os.path.join(export_path, filename)
    if os.path.exists(path):
        print(f'WARN: File already exists at: {path}', file=err_file)
        return None

    return path


def replace_param_vals(url, replacement='####'):
    return re.sub(r'(?<=[?&])(.*?)=(.*?)(?=&|$)', r'\1='+replacement, url)


def most_common_format(urls, placeholder='####'):
    parsed_url = urlparse(urls[0])
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    url_paths = [urlparse(replace_param_vals(url, placeholder)).path[1:] for url in urls]
    fmts = dict()
    for url1 in url_paths:
        url1 = url1.split('/')
        for url2 in url_paths:
            url2 = url2.split('/')
            fmt_parts = []
            lmin = min(len(url1), len(url2))
            for i in range(lmin):
                fmt_parts += [url1[i]] if url1[i] == url2[i] else [placeholder]
            lmax = max(len(url1), len(url2))
            fmt_parts += [placeholder] * (lmax - lmin)
            if placeholder in fmt_parts:
                fmt = '/'.join(fmt_parts)
                fmts[fmt] = fmts.get(fmt, 0) + 1
    if len(fmts) == 0:
        return None
    # sort formats by count of '#' in format and negative value of frequency
    # note: negative value is used in order to achive desc ordering by frequency
    fmt_freqs = sorted(fmts.items(), key=lambda x: (x[0].count(placeholder), -x[1]))
    common_fmt = fmt_freqs[0][0]
    return base_url + common_fmt


def match_profile_fmt(url, fmt, placeholder):
    assert placeholder in fmt, f'expected a format containing the placeholder {placeholder!r}, but recieved: {fmt!r}'
    fmt_pattern = re.sub(placeholder, r'.+?', fmt)
    return re.search(fmt_pattern, url)