import os
import sys
import time
import random
import traceback

from io import StringIO
from dataclasses import dataclass
from http.client import RemoteDisconnected

from web.webdriver import setup_web_driver
from web.manager import CrawlManager, ActionManager, CrawlStatus
from common.constants import ConstantsNamespace


constants = ConstantsNamespace()


@dataclass
class CrawlOptions:
    max_depth: int
    max_pages: int
    crawl_sleep: int
    include_fragment: bool
    bump_relevant: bool
    use_buffer: bool
    scraping: bool


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


def crawl_website(export_path, base_url, plan):
    '''A function to crawl links up to a maximum depth'''
    result = None
    web_driver = None
    out_file = sys.stdout
    err_file = sys.stderr

    try:
        web_driver = setup_web_driver()
        export_path_exists = True
        try:
            os.mkdir(export_path)
        except FileExistsError:
            print(f'INFO: Directory exists at: {export_path}')
        except OSError:
            print(f'ERROR: Cannot create directory at {export_path!r}, stderr and stdout will be used')
            export_path_exists = False

        if export_path_exists:
            # open log files for writing if the directory is created
            if plan.options.use_buffer:
                out_file = StringIO()
                err_file = StringIO()
            else:
                out_file, err_file = _create_out_and_err_files(export_path)
            print(f'INFO: Logs for {base_url!r} are located at {export_path!r}')
        else:
            export_path = '.'

        if plan.options.scraping:
            try:
                os.mkdir(os.path.join(export_path, 'html'))
                os.mkdir(os.path.join(export_path, 'screenshots'))
            except Exception:
                pass

        crawl_manager = CrawlManager(web_driver, base_url, out_file, err_file)
        crawl_manager.set_options(
            plan.options.max_depth,
            plan.options.max_pages,
            plan.options.bump_relevant)

        action_manager = ActionManager(out_file, err_file)

        # iterates until there aren't any links to be visited
        # if max depth is reached link extraction is ignored and all links up to that depth are visited and saved
        while True:
            # visit page
            if not crawl_manager.has_next():
                print(f'INFO: All links at a depth of {plan.options.max_depth} have been visited.',
                      'Stopping the crawling...',
                      file=out_file)
                break
            curr_page_link = crawl_manager.visit_next()
            if curr_page_link is None:
                continue
            print(f'{curr_page_link.depth} {curr_page_link.url}', file=out_file, flush=True)

            # perform action on visited page
            crawl_status = CrawlStatus.CONTINUE
            if plan.action_allowed():
                action = plan.get_curr_action()
                action_result = action_manager.perform_action(crawl_manager.curr_page, action)
                crawl_status = crawl_manager.process_action_result(action_result, action.action_type)
                if action_result.successful:  # TODO refactor with new crawl option
                    crawl_manager.increase_count()
                    if crawl_manager.is_page_max_reached():
                        break

            # check if current stage is over
            if crawl_status == CrawlStatus.NEXT_STAGE:
                result = action_result.val
                print(f'INFO: {action_result.msg}', file=out_file)
                has_next = plan.next_stage(crawl_manager, result)
                if not has_next:
                    break

            if crawl_status != CrawlStatus.SKIP_SUBLINKS or plan.skip_sublinks():
                plan.queued_sublinks()
                filters = plan.filters
                crawl_manager.queue_sublinks(plan.options.include_fragment, filters)

            out_file.flush()
            err_file.flush()
            time.sleep(plan.options.crawl_sleep)
    except RemoteDisconnected as rde:
        print(f'INFO: Interrupted. Exiting... ({rde!r})', file=err_file)
    except Exception as e:
        print(f'ERROR: {e!s}', file=err_file)
        print(f'{traceback.format_exc()}', file=err_file)
    finally:
        _close_everything(web_driver, out_file, err_file, export_path, plan.options.use_buffer)
        print(f'INFO: Crawling of {base_url!r} is complete')
    return result


class CrawlPlan:
    def __init__(self, options, stages, actions):
        self.__stages = stages
        self.__actions = actions

        self.__current_stage_index = 0
        self.__current_action_index = 0

        self.__init_page = None
        self.__clear_history = False
        self.__skip_next_page_action = False
        self.__skip_sublinks_after = None
        self.__current_action = actions[0]

        self.options = options
        self.filters = []

    def get_curr_action(self):
        return self.__current_action

    def next_stage(self, crawl_manager, prev_stage_result):
        if len(self.__stages) == self.__current_action_index:
            return False

        update = self.__stages[self.__current_stage_index]
        update(self, crawl_manager.get_options(), crawl_manager.curr_page, prev_stage_result)

        if self.__clear_history:
            crawl_manager.clear_history(self.__init_page)

        # update crawl options
        max_depth = self.options.max_depth
        max_pages = self.options.max_pages
        bump_relevant = self.options.bump_relevant
        crawl_manager.set_options(max_depth, max_pages, bump_relevant)

        self.__current_stage_index += 1

        return self.next_action()

    def next_action(self):
        if len(self.__actions) == self.__current_action_index:
            return False
        self.__current_action_index += 1
        self.__current_action = self.__actions[self.__current_action_index]
        return True

    def action_allowed(self):
        if self.__skip_next_page_action:
            self.__skip_next_page_action = False
            return False
        return True

    def queued_sublinks(self):
        if self.__skip_sublinks_after is not None:
            self.__skip_sublinks_after -= 1
            if self.__skip_sublinks_after < 0:  # just in case
                self.__skip_sublinks_after = None

        return self.__skip_sublinks_after

    def skip_sublinks(self):
        if self.__skip_sublinks_after is not None or self.__skip_sublinks_after == 0:
            return True
        return False
