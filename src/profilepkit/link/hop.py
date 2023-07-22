import re
import tldextract
from dataclasses import dataclass

from common.constants import ConstantsNamespace


constants = ConstantsNamespace



@dataclass
class PageLink:
    url: str
    depth: int



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


def is_valid_link(url, base_url):
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
    if (url.startswith('http://')
        or url.startswith('https://')) \
            and base_domain != link_domain:  # check if it is different domain only when there is absolute/whole address
        return False

    return True


def filter_extracted_links(page_links, base_url, visited_links, links_to_visit, err_file):
    def filter_out_invalid(page_link):
        return is_valid_link(page_link.url, base_url)

    def filter_out_visited(page_link):
        return page_link.url not in visited_links

    def filter_out_present_links(page_link):
        return page_link.url not in [to_visit.url for to_visit in links_to_visit]
    
    valid = filter(filter_out_invalid, page_links)
    valid_not_visited = filter(filter_out_visited, valid)
    new_links = filter(filter_out_present_links, valid_not_visited)

    # exclude links that are overly long
    not_too_long = []
    for page_link in new_links:
        if len(page_link.url) > 310:
            print(f'WARN: {link=} is too long and may not be relevant. Ignored', file=err_file)
        else:
            not_too_long.append(page_link)

    return remove_duplicates(not_too_long)


def prioritize_relevant(page_links):
    '''move relevant word at the beginning of the queue'''
    front = []
    rest = []
    for page_link in page_links:
        has_relevant = False
        for word in constants.RELEVANT_WORDS:
            if word in page_link.url:
                front.append(page_link)
                has_relevant = True
                break
        if not has_relevant:
            rest.append(page_link)

    return front + rest
