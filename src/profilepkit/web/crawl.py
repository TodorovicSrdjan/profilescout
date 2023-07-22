import io
import os
import sys
import time
import random
import traceback

from http.client import RemoteDisconnected
from selenium.common.exceptions import WebDriverException

from web.webdriver import setup_web_driver
from web.webpage import visit_page, extract_links
from link.utils import convert_links_to_absolute_path
from link.hop import filter_extracted_links, prioritize_relevant
from common.exceptions import parse_web_driver_exception
from common.constants import ConstantsNamespace


constants = ConstantsNamespace()


def close_everything(web_driver, out_file, err_file, export_path, use_buffer):
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
        out_file, err_file = create_out_and_err_files(export_path)

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


def create_out_and_err_files(export_path):
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


def crawl_website(export_path, base_url,
                  max_depth, max_pages, crawl_sleep,
                  include_fragmet, bump_relevant, use_buffer,
                  action, *action_args):
    '''A function to crawl links up to a maximum depth'''

    visited_links = set()
    links_to_visit = [(base_url, 0)]  # add base url as link that needs to be visited
    scraped_count = 0

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
            if use_buffer:
                out_file = io.StringIO()
                err_file = io.StringIO()
            else:
                out_file, err_file = create_out_and_err_files(export_path)

            print(f'INFO: Logs for {base_url!r} are located at {export_path!r}')

        # iterates until there aren't any links to be visited
        # if max depth is reached link extraction is ignored and all links up to that depth are visited and saved
        while True:
            if len(links_to_visit) == 0:
                print(f'INFO: All links at a depth of {max_depth} have been visited. Stopping the crawling...',
                      file=out_file)
                break

            # take next link from the queue and visit it
            current_link = links_to_visit.pop(0)

            # visit page
            try:
                is_text_file = visit_page(web_driver, current_link[0])
            except WebDriverException as e:
                err_msg, reason = parse_web_driver_exception(e, current_link[0])
                print(f'ERROR: {err_msg} (reason: {reason})', file=err_file)
                print(f'WARN: {reason} {current_link[0]}', file=out_file)

                # skip this url
                continue

            # mark link as visited
            visited_links.add(current_link[0])

            # if content-type is not 'text/*' then ignore it
            if not is_text_file:
                continue

            print(f'{current_link[1]} {current_link[0]}', file=out_file, flush=True)

            # perform action on visited page
            successful = action(web_driver, err_file, *action_args)

            if successful:
                scraped_count += 1
            else:
                print(f'ERROR: Failed to perform action {action.__name__!r} for: {current_link[0]}', file=err_file)

            if max_pages is not None and scraped_count == max_pages:
                print(f'INFO: Maximum number of pages to scrape ({max_pages}) reached. Stopping the crawling...',
                      file=out_file)
                print(f'INFO: There were  {len(links_to_visit)} unvisited links in the queue', file=out_file)
                print(f'INFO: Current depth: {current_link[1]}', file=out_file)

                break

            # check if the maximum depth (number of hops) has been reached
            if current_link[1] == max_depth:
                # ignore links on the current page and continue with visiting links that left to be visited
                continue

            hops = extract_links(web_driver, base_url,
                                 url=current_link[0],
                                 depth=current_link[1],
                                 err_file=err_file,
                                 include_fragmet=include_fragmet)

            # transform extracted URLs, as some of them may be invalid or irrelevant
            hops_with_abs_path = convert_links_to_absolute_path(hops, base_url, current_link[0])
            hops_to_add = filter_extracted_links(hops_with_abs_path, base_url, visited_links, links_to_visit, err_file)

            if bump_relevant:
                hops_to_add = prioritize_relevant(hops_to_add)

            links_to_visit.extend(hops_to_add)

            out_file.flush()
            err_file.flush()

            time.sleep(crawl_sleep)
    except RemoteDisconnected as rde:
        print(f'INFO: Interrupted. Exiting... ({rde!r})', file=err_file)
    except Exception as e:
        print(f'ERROR: {e!s}', file=err_file)
        print(f'{traceback.format_exc()}', file=err_file)
    else:
        print(f'INFO: Crawling of {base_url!r} is complete')
    finally:
        close_everything(web_driver, out_file, err_file, export_path, use_buffer)
