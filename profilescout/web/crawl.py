import os
import sys
import time
import random
import traceback
import copy

from io import StringIO
from dataclasses import dataclass
from http.client import RemoteDisconnected

from profilescout.common.constants import ConstantsNamespace
from profilescout.common.structures import OriginPageDetectionStrategy
from profilescout.link.utils import is_valid_sublink
from profilescout.web.manager import CrawlManager, CrawlStatus
from profilescout.web.webdriver import setup_web_driver
from profilescout.web.webpage import ScrapeOption, WebpageActionType


constants = ConstantsNamespace


def _close_everything(web_driver, out_file, err_file, export_path, use_buffer):
    if web_driver is not None:
        web_driver.quit()
    # make sure that everything is flushed before stream is closed
    out_file.flush()
    err_file.flush()
    if use_buffer:
        out_content = out_file.getvalue()
        err_content = err_file.getvalue()
        # close buffers
        out_file.close()
        err_file.close()
        # create log files
        out_file, err_file = _create_out_and_err_files(export_path)
        # write buffered contents to log files
        out_file.write(out_content)
        err_file.write(err_content)
        out_file.close()
        err_file.close()
    else:
        if out_file != sys.stdout:
            out_file.close()
        if err_file != sys.stderr:
            err_file.close()


def _create_out_and_err_files(export_path):
    suffix = ''
    out_log_path = os.path.join(export_path, 'out.log')
    err_log_path = os.path.join(export_path, 'err.log')
    if os.path.exists(out_log_path) or os.path.exists(err_log_path):
        suffix += str(random.randint(constants.PRINT_SUFFIX_MIN, constants.PRINT_SUFFIX_MAX))
        out_log_path = os.path.join(export_path, f'out{suffix}.log')
        err_log_path = os.path.join(export_path, f'err{suffix}.log')
    out_file = open(out_log_path, 'w')
    err_file = open(err_log_path, 'w')

    return out_file, err_file


def crawl_website(
    export_path,
    base_url,
    options,
    action_type,
    scrape_option,
    image_classifier
):
    detection_strategy = OriginPageDetectionStrategy()
    if action_type == WebpageActionType.SCRAPE_PAGES:
        crawler = Crawler(options, export_path)
        for step in crawler.crawl(base_url):
            crawler.save(scrape_option)
    elif action_type == WebpageActionType.FIND_ORIGIN:
        crawler = Crawler(options, export_path, detection_strategy, image_classifier)
        for step in crawler.crawl(base_url):
            if detection_strategy.successful():
                break
    elif action_type == WebpageActionType.SCRAPE_PROFILES:
        crawler = Crawler(options, export_path, detection_strategy, image_classifier)
        for step in crawler.crawl(base_url):
            if detection_strategy.successful():
                result = detection_strategy.get_result()
                origin = result['origin']
                og_crawler = crawler.create_subcrawler()
                og_crawler.options.max_depth = result['depth'] + 1
                og_crawler.links_from_structure = True
                og_crawler.skip_sublinks = True
                og_crawler.skip_first_page = True
                og_crawler.sublink_filters = [lambda page_link: is_valid_sublink(page_link.url, result['most_common_format'], '####')]
                for og_step in og_crawler.crawl(origin, result['depth']):
                    og_crawler.save(scrape_option)
                    og_crawler.skip_sublinks = True
                crawler.mark_as_visited(og_crawler.get_visited_links(), og_crawler.get_scraped_count())


@dataclass
class CrawlOptions:
    max_depth: int = 3
    max_pages: int = None
    crawl_sleep: int = 2
    include_fragment: bool = False
    bump_relevant: bool = True
    use_buffer: bool = False
    scraping: bool = True
    resolution: tuple = (constants.WIDTH, constants.HEIGHT)

    def increase(self, to_incr):
        for option, val in to_incr.items():
            assert val > 0, 'value must be greater then 0'
            if option == 'max_depth':
                self.max_depth += val
            elif option == 'max_pages':
                self.max_pages += val
            elif option == 'crawl_sleep':
                self.crawl_sleep += val
            else:
                raise KeyError(f'provided value {option!r} is not recognised as a crawl option')


class Crawler:
    def __init__(
        self,
        options,
        export_path,
        detection_strategy=None,
        image_classifier=None,
        parent_out_file=None,
        parent_err_file=None,
        is_subcrawler=False
    ):
        self.skip_sublinks = False
        self.skip_first_page = False
        self.links_from_structure = False
        self.status = CrawlStatus.NOT_STARTED
        self.img_width = constants.WIDTH
        self.img_height = constants.HEIGHT
        self.sublink_filters = []
        self.detection_strategy = detection_strategy
        self.options = options
        self.image_classifier = image_classifier
        self.is_subcrawler = is_subcrawler
        # prepare output files and directories
        self.export_path = export_path
        self._out_file = sys.stdout
        self._err_file = sys.stderr
        if is_subcrawler:
            self._out_file = parent_out_file
            self._err_file = parent_err_file
        else:
            export_path_exists = True
            try:
                os.mkdir(self.export_path)
            except FileExistsError:
                print(f'INFO: Directory exists at: {self.export_path}')
            except OSError:
                print(f'ERROR: Cannot create directory at {self.export_path!r}, stderr and stdout will be used')
                export_path_exists = False
            if export_path_exists:
                # open log files for writing if the directory is created
                if self.options.use_buffer:
                    self._out_file = StringIO()
                    self._err_file = StringIO()
                else:
                    self._out_file, self._err_file = _create_out_and_err_files(self.export_path)
            else:
                self.export_path = '.'
            if self.options.scraping:
                try:
                    os.mkdir(os.path.join(self.export_path, 'html'))
                    os.mkdir(os.path.join(self.export_path, 'screenshots'))
                except Exception:
                    pass

    def _visit_page(self):
        if not self.crawl_manager.has_next():
            print(f'INFO: All links at a depth of {self.options.max_depth} have been visited.',
                  'Stopping the crawling...',
                  file=self._out_file)
            self.status = CrawlStatus.FINISHED
            return None
        self.curr_page = self.crawl_manager.visit_next()
        if self.curr_page is None:
            return None
        print(f'{self.curr_page.link.depth} {self.curr_page.link.url}', file=self._out_file, flush=True)
        return self.curr_page

    def _visit_cleanup(self):
        self._out_file.flush()
        self._err_file.flush()
        time.sleep(self.options.crawl_sleep)

    def _perform_detection_strategy(self):
        self.detection_strategy.analyse(self.curr_page, self.image_classifier, self.options.resolution)
        result = self.detection_strategy.get_result()
        if result is not None:
            print(f"INFO: {result['message']}", file=self._out_file)
        return result

    def _perform_action(self, action, args):
        action_result = action(**args)
        if action_result.successful:
            self.crawl_manager.increase_count()
            if self.crawl_manager.is_page_max_reached():
                self.status = CrawlStatus.FINISHED
        else:
            action_name = action.__name__
            print(f'ERROR: Failed to perform action {action_name!r} for: {self.curr_page.link.url}', file=self._err_file)
        return action_result

    def _queue_sublinks(self):
        return self.crawl_manager.queue_sublinks(
            self.options.include_fragment,
            self.sublink_filters,
            self.links_from_structure)

    def crawl(self, base_url, base_depth=0):
        if not self.is_subcrawler:
            print(f'INFO: Logs for {base_url!r} are located at {self.export_path!r}')
        self._web_driver = setup_web_driver()
        self.status = CrawlStatus.RUNNING
        self.crawl_manager = CrawlManager(self._web_driver, base_url, self._out_file, self._err_file, base_depth=base_depth)
        self.crawl_manager.set_options(
            self.options.max_depth,
            self.options.max_pages,
            self.options.bump_relevant)
        try:
            while True:
                self.skip_sublinks = False
                current_page = self._visit_page()
                if current_page is None or self.status == CrawlStatus.FINISHED:
                    break

                if self.detection_strategy is not None:
                    if self.detection_strategy.successful():
                        self.detection_strategy.reset()  # prep for new origin page
                    self._perform_detection_strategy()

                if self.skip_first_page:
                    self.skip_first_page = False
                    print(f'INFO: Skipped page: {self.curr_page.link.url}', file=self._out_file)
                else:
                    yield current_page.link

                # execution will resume here so check status to find out if crawling should be finished or not
                # note: caller might do something like performing action, which can lead to change of the
                #       crawl status
                if self.status == CrawlStatus.FINISHED:
                    break

                if not self.skip_sublinks:
                    self._queue_sublinks()
                self._visit_cleanup()
        except RemoteDisconnected as rde:
            print(f'INFO: Interrupted. Exiting... ({rde!r})', file=self._err_file)
        except Exception as e:
            print(f'ERROR: {e!s}')
            print(f'{traceback.format_exc()}')
        finally:
            if not self.is_subcrawler:
                _close_everything(self._web_driver, self._out_file, self._err_file, self.export_path, self.options.use_buffer)
                print(f'INFO: Crawling of {base_url!r} is complete')
            else:
                print(f'INFO: Subcrawling of {base_url!r} is complete')

    def create_subcrawler(self):
        options = copy.copy(self.options)
        return Crawler(
            options,
            self.export_path,
            parent_out_file=self._out_file,
            parent_err_file=self._err_file,
            is_subcrawler=True)

    def save(self, scrape_option):
        action = self.curr_page.scrape_page
        if scrape_option == ScrapeOption.ALL:
            args = {'export_path': self.export_path, 'scrape_option': ScrapeOption.ALL,
                    'width': self.img_width, 'height': self.img_height}
        elif scrape_option == ScrapeOption.HTML:
            action = self.curr_page.get_html
            args = {}
        elif scrape_option == ScrapeOption.SCREENSHOT:
            args = {'export_path': self.export_path, 'scrape_option': ScrapeOption.SCREENSHOT,
                    'width': self.img_width, 'height': self.img_height}
        else:
            return None
        return self._perform_action(action, args)

    def get_visited_links(self):
        return self.crawl_manager.get_visited_links()

    def get_links_to_visit(self):
        return self.crawl_manager.get_links_to_visit()

    def get_scraped_count(self):
        return self.crawl_manager.get_scraped_count()

    def mark_as_visited(self, visited_links, scraped_count):
        return self.crawl_manager.mark_as_visited(visited_links, scraped_count)
