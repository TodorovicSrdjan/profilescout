from enum import Enum

from profilescout.web.webpage import Webpage, WebpageActionType
from profilescout.common.constants import ConstantsNamespace
from profilescout.common.exceptions import WebDriverException, parse_web_driver_exception
from profilescout.link.utils import PageLink, remove_duplicates, prioritize_relevant, to_abs_path, most_common_format
from profilescout.link.utils import filter_out_invalid, filter_out_visited, filter_out_present_links, filter_out_long


constants = ConstantsNamespace

CrawlStatus = Enum('CrawlStatus', ['CONTINUE', 'NEXT_ACTION', 'NEXT_STAGE', 'SKIP_SUBLINKS'])


class ActionManager:
    def __init__(self, out_file, err_file):
        self.__out_file = out_file
        self.__err_file = err_file

    def __perform(self, page, action):
        result = None
        if action.action_type != WebpageActionType.UNKNOWN and hasattr(action.func, "__name__"):
            func = getattr(page, action.func.__name__)
            result = func(*action.args)

        return result

    def perform_action(self, page, action):
        result = self.__perform(page, action)
        if result is None or not result.successful:
            action_name = None
            if action.func is None:
                action_name = action.action_type.name.lower()
            else:
                action_name = action.func.__name__
            print(f'ERROR: Failed to perform action {action_name!r} for: {page.link.url}', file=self.__err_file)

        return result


class CrawlManager:
    def __init__(self, web_driver, base_url, out_file, err_file, max_depth=3, max_pages=None):
        self.__web_driver = web_driver
        self.__base_url = base_url
        self.__max_depth = max_depth
        self.__max_pages = max_pages
        self.__bump_relevant = False

        page_link = PageLink(base_url, 0)
        self.curr_page = Webpage(web_driver, page_link, out_file, err_file)

        self.__scraped_count = 0
        self.__visited_links = set()
        self.__links_to_visit = [page_link]  # add base url as link that needs to be visited

        self.out_file = out_file
        self.err_file = err_file

    def __set_curr_page(self, page_link):
        self.curr_page = Webpage(self.__web_driver, page_link, self.out_file, self.err_file)
        return self.curr_page

    def has_next(self):
        return len(self.__links_to_visit) > 0

    def clear_history(self, init_page=None):
        self.__scraped_count = 0
        self.__visited_links = set()

        link = init_page if init_page is not None else self.curr_page
        self.__links_to_visit = [link]

    def set_options(self, max_depth=None, max_pages=None, bump_relevant=None):
        self.__max_depth = max_depth if max_depth is not None else self.__max_depth
        self.__max_pages = max_pages if max_pages is not None else self.__max_pages
        self.__bump_relevant = bump_relevant if bump_relevant is not None else self.__bump_relevant

    def is_page_max_reached(self):
        if self.__max_pages is not None and self.__scraped_count == self.__max_pages:
            print(f'INFO: Maximum number of pages to scrape ({self.__max_pages}) reached.',
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

    def get_options(self):
        return {
            'max_depth': self.__max_depth,
            'max_pages': self.__max_pages,
            'bump_relevant': self.__bump_relevant}

    def queue_sublinks(self, include_fragment=False, plan_filters=[], links_from_structure=False):
        # check if the maximum depth (number of hops) has been reached
        if self.curr_page.link.depth == self.__max_depth:
            # ignore links on the current page and continue with visiting links that left to be visited
            return None
        # extract URLs
        if not links_from_structure:
            self.__previous_links = []
        hops = self.curr_page.extract_links(self.__base_url, include_fragment, links_from_structure,  self.__previous_links)
        self.__previous_links = [hop.url for hop in hops]

        # transform extracted URLs, as some of them may be invalid or irrelevant
        hops_with_abs_path = to_abs_path(hops, self.__base_url, self.curr_page.link.url)
        valid = filter_out_invalid(hops_with_abs_path, self.__base_url)
        valid_not_visited = filter_out_visited(valid, self.__visited_links)
        new_links = filter_out_present_links(valid_not_visited, self.__links_to_visit)
        new_links = filter_out_long(new_links, self.err_file)
        new_links = remove_duplicates(new_links)
        if plan_filters != []:
            for plan_filter in plan_filters:
                new_links = filter(plan_filter, new_links)
        self.__links_to_visit.extend(new_links)

        if self.__bump_relevant:
            self.__links_to_visit = prioritize_relevant(self.__links_to_visit)

        return self.__links_to_visit

    def process_action_result(self, result, action_type):
        if action_type == WebpageActionType.FIND_ORIGIN:
            profile_detected = result.val
            if result.successful and profile_detected:
                if not hasattr(self, '_CrawlManager__origin_candidates'):
                    self.__origin_candidates = {}
                # assume that this is initial page
                origin = self.curr_page.link.url
                parent_url = self.curr_page.link.parent_url
                if parent_url is not None:
                    origin = parent_url
                if origin not in self.__origin_candidates:
                    self.__origin_candidates[origin] = []
                else:
                    self.__origin_candidates[origin] += [self.curr_page.link.url]

                # check if the profile page origin is found
                children = self.__origin_candidates[origin]
                children_count = len(children)
                if children_count == constants.ORIGIN_PAGE_THRESHOLD:
                    result.val = {'origin': origin, 'most_common_format': most_common_format(children)}  # TODO add placeholder
                    result.msg = f'Found profile page origin at {origin!r}'
                    return CrawlStatus.NEXT_STAGE
        return CrawlStatus.CONTINUE
