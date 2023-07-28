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


def crawl_website(export_path, base_url, action, options):
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
            if options.use_buffer:
                out_file = StringIO()
                err_file = StringIO()
            else:
                out_file, err_file = _create_out_and_err_files(export_path)
            print(f'INFO: Logs for {base_url!r} are located at {export_path!r}')
        else:
            export_path = '.'

        if options.scraping:
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

        action_manager = ActionManager(web_driver, base_url, out_file, err_file)

        # iterates until there aren't any links to be visited
        # if max depth is reached link extraction is ignored and all links up to that depth are visited and saved
        while True:
            if not crawl_manager.has_next():
                print(f'INFO: All links at a depth of {options.max_depth} have been visited.',
                      'Stopping the crawling...',
                      file=out_file)
                break

            curr_page_link = crawl_manager.visit_next()
            if curr_page_link is None:
                continue

            print(f'{curr_page_link.depth} {curr_page_link.url}', file=out_file, flush=True)

            # perform action on visited page
            action_result = action_manager.perform_action(crawl_manager.curr_page, action)

            if action_result.crawl_status == CrawlStatus.EXIT:
                result = action_result.val
                print(f'INFO: {action_result.msg}', file=out_file)
                break

            if action_result.successful:
                crawl_manager.increase_count()
                if crawl_manager.is_page_max_reached():
                    break

            if action_result.crawl_status != CrawlStatus.SKIP_SUBLINKS:
                crawl_manager.queue_sublinks(options.include_fragment)

            out_file.flush()
            err_file.flush()

            time.sleep(options.crawl_sleep)
    except RemoteDisconnected as rde:
        print(f'INFO: Interrupted. Exiting... ({rde!r})', file=err_file)
    except Exception as e:
        print(f'ERROR: {e!s}', file=err_file)
        print(f'{traceback.format_exc()}', file=err_file)
    finally:
        _close_everything(web_driver, out_file, err_file, export_path, options.use_buffer)
        print(f'INFO: Crawling of {base_url!r} is complete')

    return result
