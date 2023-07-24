from selenium.common.exceptions import WebDriverException

from web.webpage import Webpage
from common.constants import ConstantsNamespace
from common.exceptions import parse_web_driver_exception
from link.utils import PageLink, remove_duplicates, prioritize_relevant, to_abs_path
from link.utils import filter_out_invalid, filter_out_visited, filter_out_present_links, filter_out_long

constants = ConstantsNamespace


class CrawlManager:
    def __init__(self, web_driver, base_url, out_file, err_file, max_depth=3, max_pages=None):
        self.web_driver = web_driver
        self.base_url = base_url
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.bump_relevant = False

        page_link = PageLink(base_url, 0)
        self.curr_page = Webpage(web_driver, page_link, err_file)

        self.__scraped_count = 0
        self.__visited_links = set()
        self.__links_to_visit = [page_link]  # add base url as link that needs to be visited

        self.out_file = out_file
        self.err_file = err_file

    def __set_curr_page(self, page_link):
        self.curr_page = Webpage(self.web_driver, page_link, self.err_file)
        return self.curr_page

    def has_next(self):
        return len(self.__links_to_visit) > 0

    def is_page_max_reached(self):
        if self.max_pages is not None and self.__scraped_count == self.max_pages:
            print(f'INFO: Maximum number of pages to scrape ({self.max_pages}) reached.',
                  'Stopping the crawling...',
                  file=self.out_file)
            print(f'INFO: There were {len(self.__links_to_visit)} unvisited links in the queue',
                  file=self.out_file)
            print(f'INFO: Current depth: {self.curr_page.link.depth}', file=self.out_file)
            return True
        return False

    def visit_next(self):
        # take next link from the queue and visit it
        self.__set_curr_page(self.__links_to_visit.pop(0))

        # visit page
        try:
            is_text_file = self.curr_page.visit()
        except WebDriverException as e:
            err_msg, reason = parse_web_driver_exception(e, self.curr_page.link.url)
            print(f'ERROR: {err_msg} (reason: {reason})', file=self.err_file)
            print(f'WARN: {reason} {self.curr_page.link.url}', file=self.out_file)

            # skip this url
            return None

        # mark link as visited
        self.__visited_links.add(self.curr_page.link.url)

        # if content-type is not 'text/*' then ignore it
        if not is_text_file:
            return None

        return self.curr_page.link

    def increase_count(self):
        self.__scraped_count += 1
        return self.__scraped_count

    def queue_sublinks(self, include_fragment=False):

        # check if the maximum depth (number of hops) has been reached
        if self.curr_page.link.depth == self.max_depth:
            # ignore links on the current page and continue with visiting links that left to be visited
            return None

        hops = self.curr_page.extract_links(self.base_url, include_fragment)

        # transform extracted URLs, as some of them may be invalid or irrelevant
        hops_with_abs_path = to_abs_path(hops, self.base_url, self.curr_page.link.url)
        valid = filter_out_invalid(hops_with_abs_path, self.base_url)
        valid_not_visited = filter_out_visited(valid, self.__visited_links)
        new_links = filter_out_present_links(valid_not_visited, self.__links_to_visit)
        new_links = filter_out_long(new_links, self.err_file)
        new_links = remove_duplicates(new_links)

        self.__links_to_visit.extend(new_links)

        if self.bump_relevant:
            self.__links_to_visit = prioritize_relevant(self.__links_to_visit)

        return self.__links_to_visit
