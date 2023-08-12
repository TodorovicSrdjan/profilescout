import re
import os
import sys
import random
import tldextract
from urllib.parse import urlparse, quote_plus

from dataclasses import dataclass

from profilescout.common.constants import ConstantsNamespace


constants = ConstantsNamespace


@dataclass
class PageLink:
    url: str
    depth: int
    parent_url: str = None
    txt: str = ''


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

    base_extract = tldextract.extract(base_url)
    link_extract = tldextract.extract(url)
    base_subdo_reversed = base_extract.subdomain.replace('www', '').split('.')[::-1]
    link_subdo_reversed = link_extract.subdomain.replace('www', '').split('.')[::-1]
    common_len = min(len(base_subdo_reversed), len(link_subdo_reversed))
    # TODO rethink; could cause problem with some sites that have profiles
    # on another url or as PDF/DOCX/...
    has_protocol = url.startswith('http://') or url.startswith('https://')
    if (
        has_protocol
        and (  # check if they have common subdomain (base subdomain must be contained in url's subdomain)
            base_extract.domain != link_extract.domain
            or any(base_subdo_reversed[i] != link_subdo_reversed[i] for i in range(common_len))
        )
    ):
        return False

    return True


def to_abs_path(url, current_url):
    base_url = to_base_url(current_url)
    # fix relative links or links that start with '/'
    abs_url = url
    if url.startswith('http'):
        abs_url = url
    elif url.startswith('www'):
        abs_url = 'http://' + url
    else:
        # relative path or absoulte path from '/'
        if url[0] == '/':
            # absolute path
            if base_url[-1] == '/':
                url = url[1:]  # remove '/' since base_url ends with one
            abs_url = base_url + url
        else:
            # relative path
            if current_url[-1] != '/':
                url = '/' + url
            abs_url = current_url + url
    return abs_url


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
            word = quote_plus(word)
            if word in page_link.url.lower():
                front.append(page_link)
                has_relevant = True
                break
        if not has_relevant:
            rest.append(page_link)

    return front + rest


def with_and_without_www(url):
    parsed_url = urlparse(url)
    if parsed_url.scheme == '' or parsed_url.hostname is None:
        if url.startswith('www.'):
            return url, url.replace('www.', '')
        return f'www.{url}', url
    if parsed_url.hostname.startswith('www'):
        return url, url.replace('www.', '')
    return url.replace(f'{parsed_url.scheme}://', f'{parsed_url.scheme}://www.'), url


def filter_out_invalid(page_links, base_url):
    result = filter(lambda pl: is_valid(pl.url, base_url),
                    page_links)
    return list(result)


def filter_out_visited(page_links, visited_links):
    result = []
    for page_link in page_links:
        www, wo_www = with_and_without_www(page_link.url)
        if www not in visited_links and wo_www not in visited_links:
            result += [page_link]
    return result


def filter_out_present_links(page_links, links_to_visit):
    result = []
    urls_to_visit = [to_visit.url for to_visit in links_to_visit]
    for page_link in page_links:
        www, wo_www = with_and_without_www(page_link.url)
        if www not in urls_to_visit and wo_www not in urls_to_visit:
            result += [page_link]
    return result


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


def to_filename(url, export_path, extension, err_file=sys.stderr):
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
        # cut off chars that exceed limit
        filename = filename[:limit]
        # replace the remaining string with suffix and extension
        ext = '.' + extension
        suffix = constants.FILENAME_CUT_SUFFIX
        suffix += str(random.randint(1000, 9999))
        overwrite_len = len(suffix) + len(ext)
        filename = filename[:-overwrite_len] + suffix + ext
        print('WARN: Link was too long.',
              f'The filename of has changed to: {filename}',
              file=err_file)
    else:
        filename += '.' + extension

    return filename


def to_file_path(link, export_path, extension, ignore_existing=False, err_file=sys.stderr):
    filename = ''
    filename = to_filename(link, export_path, extension)
    path = os.path.join(export_path, filename)
    if not ignore_existing and os.path.exists(path):
        print(f'WARN: File already exists at: {path}', file=err_file)
        return None
    return path


def replace_param_vals(url, replacement='####'):
    return re.sub(r'(?<=[?&])(.*?)=(.*?)(?=&|$)', r'\1='+replacement, url)


def _create_format_freq_tuple(fmt_freq, placeholder='####'):
    fmt_path_part = fmt_freq[0]
    qmark_idx = fmt_path_part.find('?')
    if qmark_idx != -1:
        fmt_path_part = fmt_path_part[:qmark_idx]
    query_part = fmt_freq[0][qmark_idx:]
    query_var_count = query_part.count(placeholder)
    # penalize those formats which don't have any variable part in url query
    query_var_count_asc = query_var_count if query_var_count > 0 else sys.maxsize
    fmt_freq_desc = -fmt_freq[1]
    var_count_asc = fmt_freq[0].count(placeholder) if fmt_freq[0].count(placeholder) > 0 else sys.maxsize
    has_slash_desc = '/' not in fmt_freq[0]
    has_query_desc = '?' not in fmt_freq[0]
    has_var_in_path_desc = placeholder not in fmt_path_part
    return has_slash_desc, has_query_desc, has_var_in_path_desc, var_count_asc, query_var_count_asc, fmt_freq_desc


def most_common_format(urls, placeholder='####'):
    parsed_urls = [urlparse(url) for url in urls]
    urls_without_domain = [f'{url.path}?{url.query}'
                           if url.query != '' else url.path
                           for url in parsed_urls]
    encoded_urls = [replace_param_vals(url, placeholder) for url in urls_without_domain]
    fmts = dict()
    for url1 in encoded_urls:
        url1_parts = url1.split('/')
        url1_parts = [part for part in url1_parts if part != '']
        for url2 in encoded_urls:
            url2_parts = url2.split('/')
            url2_parts = [part for part in url2_parts if part != '']
            fmt_parts = []
            lmin = min(len(url1_parts), len(url2_parts))
            for i in range(lmin):
                fmt_parts += [url1_parts[i]] if url1_parts[i] == url2_parts[i] else [placeholder]
            lmax = max(len(url1_parts), len(url2_parts))
            fmt_parts += [placeholder] * (lmax - lmin)
            # if placeholder in fmt_parts or len(fmt_parts) == 1:
            fmt = '/'.join(fmt_parts)
            fmts[fmt] = fmts.get(fmt, 0) + 1
    if len(fmts) == 0:
        return None
    # sort formats by count of '#' in format, negative value of '?' freqency
    # and negative value of placeholder frequency
    # note: negative value is used in order to achive desc ordering by frequency
    fmt_freqs = sorted(fmts.items(), key=lambda x: _create_format_freq_tuple(x, placeholder))
    common_fmt = fmt_freqs[0][0]
    parsed_url = urlparse(urls[0])
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    return base_url + common_fmt


def match_profile_fmt(url, fmt, placeholder):
    assert placeholder in fmt, f'expected a format containing the placeholder {placeholder!r}, but recieved: {fmt!r}'
    fmt_escaped = re.escape(fmt)
    fmt_pattern = fmt_escaped.replace(re.escape(placeholder), r'.+?')
    return re.search(fmt_pattern, url)


def is_valid_sublink(url, fmt, placeholder):
    return fmt is None or match_profile_fmt(url, fmt, placeholder)
