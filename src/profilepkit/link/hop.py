import re
import tldextract

from common.constants import ConstantsNamespace


constants = ConstantsNamespace


def remove_duplicates(hops):
    unique_links = hops

    i = 0
    n = len(unique_links)
    while i < n-1:
        j = i+1
        while j < n:
            if unique_links[i][0] == unique_links[j][0]:
                # update depth if there is better path
                if unique_links[i][1] > unique_links[j][1]:
                    unique_links[i][1] = unique_links[j][1]

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


def filter_extracted_links(hops, base_url, visited_links, links_to_visit, err_file):
    # create filter functions
    def filter_out_invalid(tuple):
        return is_valid_link(tuple[0], base_url)

    def filter_out_visited(tuple):
        return tuple[0] not in visited_links

    def filter_out_present_links(tuple):
        return tuple[0] not in [to_visit_tuple[0] for to_visit_tuple in links_to_visit]

    valid_hops = filter(filter_out_invalid, hops)
    valid_not_visited_hops = filter(filter_out_visited, valid_hops)
    new_links = filter(filter_out_present_links, valid_not_visited_hops)

    # exclude links that are overly long
    not_too_long = []
    for link, depth in new_links:
        if len(link) > 310:
            print(f'WARN: {link=} is too long and may not be relevant. Ignored', file=err_file)
        else:
            not_too_long += [(link, depth)]

    return remove_duplicates(not_too_long)


def prioritize_relevant(hops):
    '''move relevant word at the beginning of the queue'''
    front = []
    rest = []
    for link, depth in hops:
        has_relevant = False
        for word in constants.RELEVANT_WORDS:
            if word in link:
                front += [(link, depth)]
                has_relevant = True
                break
        if not has_relevant:
            rest += [(link, depth)]

    return front + rest
