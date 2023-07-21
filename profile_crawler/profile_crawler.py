import os
import sys
import traceback
import time
import re
import random
import textwrap
import platform
import tldextract
import io

from concurrent.futures import ThreadPoolExecutor, wait

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (StaleElementReferenceException,
                                        WebDriverException,
                                        UnexpectedAlertPresentException)

from http.client import RemoteDisconnected

FUTURES = []
IMPL_WAIT_FOR_FULL_LOAD = 18
RETRY_TIME = 60
BUFF_THRESHOLD = 30
INVALID_EXTENSIONS = [
    'mp4', 'jpg', 'png', 'jpeg',
    'zip', 'rar', 'xls', 'rtf',
    'docx', 'doc', 'pptx', 'ppt',
    'pdf', 'txt']

RELEVANT_WORDS = [
    # en
    'profile', 'user', 'users',
    'about-us', 'team',
    'employees', 'staff', 'professor',

    # rs
    'profil',
    'o-nama',
    'zaposlen', 'nastavnik', 'nastavnici', 'saradnici', 'profesor', 'osoblje'
    'запослен', 'наставник', 'наставници', 'сарадници', 'професор', 'особље']


def setup_web_driver():
    # create a new Chrome browser instance Options
    options = webdriver.ChromeOptions()

    # disable file downloads
    null_path = '/dev/null'  # assume that program is run on Unix-like OS

    if platform.system() == 'Windows':
        null_path = 'NUL'

    profile = {
            "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
            "download.default_directory": null_path,
            "profile.default_content_settings.popups": 0,
            "download.prompt_for_download": False,
            "download_restrictions": 3,  # https://chromeenterprise.google/policies/#DownloadRestrictions
            "safebrowsing.enabled": True
        }

    options.add_experimental_option("prefs", profile)

    options.add_argument("--no-sandbox")                 # bypass OS security model
    options.add_argument("--start-maximized")            # open Browser in maximized mode
    options.add_argument("--disable-extensions")         # disabling extensions
    options.add_argument("--disable-gpu")                # applicable to Windows only
    options.add_argument("--disable-dev-shm-usage")      # overcome limited resource problems
    options.add_argument("--disable-application-cache")
    options.add_argument("--mute-audio")

    # disable GUI
    options.add_argument('--headless')
    options.add_argument('--disable-infobars')

    web_driver = webdriver.Chrome(
        service=Service(),
        options=options)

    # wait for the page to fully load
    web_driver.implicitly_wait(IMPL_WAIT_FOR_FULL_LOAD)

    return web_driver


def visit_page(web_driver, url):
    # navigate to the web page you want to capture
    try:
        web_driver.get(url)
    except WebDriverException:
        # if not successful, retry after RETRY_TIME seconds
        time.sleep(RETRY_TIME)

        try:
            web_driver.get(url)
        except WebDriverException as e:
            raise e  # TODO

    # pause videos that have autoplay set to true
    web_driver.execute_script('videos = document.querySelectorAll("video"); for(video of videos) {video.pause()}')

    content_type = web_driver.execute_script("return document.contentType")

    if content_type.startswith('text'):
        return True

    return False


def screenshot_current_webpage(web_driver, err_file, export_path, width=2880, height=1620):
    web_driver.set_window_size(width, height)

    filename = ''
    ext = '.png'
    try:
        filename = web_driver.current_url
    except WebDriverException:
        # try one more time after RETRY_TIME seconds
        time.sleep(RETRY_TIME)
        try:
            filename = web_driver.current_url
        except UnexpectedAlertPresentException:
            print('ERROR: extraction of the current URL has failed because an alert was present', file=err_file)
            return False
        except WebDriverException as e:
            print(f'ERROR: extraction of the current URL has failed (reason: {str(e)})', file=err_file)
            return False

    # remove '/' at the end
    if filename[-1] == '/':
        filename = filename[:-1]

    filename = filename.replace('https://', '').replace('http://', '')
    filename = filename.replace('/', '__').replace('?', 'QMARK').replace('#', 'ANCHOR').replace('&', 'AMPERSAND')

    # check if filename exceeds upper limit for number of characters
    FNAME_MAX_LEN = os.pathconf(export_path, 'PC_NAME_MAX')
    if len(filename) + len(ext) > FNAME_MAX_LEN:
        filename = filename[:(FNAME_MAX_LEN - len(ext))] + ext
        print(f'WARN: Link was too long. The filename of the screenshot has changed to: {filename}', file=err_file)
    else:
        filename += ext

    path = os.path.join(export_path, filename)
    if os.path.exists(path):
        print(f'WARN: Screenshot already exists at: {path}', file=err_file)
        return False

    # take a screenshot of the entire web page and save it as an image file
    return web_driver.save_screenshot(path)


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
        if ext.lower() in INVALID_EXTENSIONS:
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


def parse_web_driver_exception(e, url):
    reason = 'error'
    err_msg = ''

    if 'ERR_NAME_NOT_RESOLVED' in str(e):
        reason = 'unresolved'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: name cannot be resolved)'
    elif 'ERR_ADDRESS_UNREACHABLE' in str(e):
        reason = 'unreachable'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: address cannot be reached)'
    elif 'ERR_CONNECTION_TIMED_OUT' in str(e):
        reason = 'timed out'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: connection timed out)'
    elif 'stale element reference' in str(e):
        reason = 'stale'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: stale element)'
    elif 'ERR_SSL_VERSION_OR_CIPHER_MISMATCH' in str(e):
        reason = 'https not supported'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: site does not support https)'
    else:
        err_msg = f'ERROR: {str(e)}'

    return err_msg, reason


def extract_links(web_driver, base_url, url, depth, err_file, include_fragmet=False):
    hops = []
    a_tags = web_driver.find_elements(By.XPATH, '//a[@href]')
    for a_tag in a_tags:
        href = ''
        try:
            href = a_tag.get_attribute('href').strip()
        except StaleElementReferenceException:
            print(f'ERROR: One of the next hop from "{url}" is skipped (reason: stale element)', file=err_file)
        except WebDriverException as e:
            print(f'ERROR: One of the next hop from "{url}" is skipped (reason: {str(e)})', file=err_file)
        else:
            idx = href.find('?nocache')
            if idx != -1:
                href = href[:idx]

            if not include_fragmet:
                # remove fragmet
                frag_idx = href.find('#')
                if frag_idx != -1:
                    href = href[:frag_idx]

            if href not in hops and is_valid_link(href, base_url):
                hops += [(href, depth+1)]

    return hops


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


def convert_links_to_absolute_path(hops, base_url, current_link):
    # fix relative links or links that start with '/'
    hops_fixed = []
    for (link, depth) in hops:
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
        hops_fixed += [(fixed_link, depth)]

    return hops_fixed


def convert_to_fqdn(url):
    return tldextract.extract(url).fqdn


def convert_to_base_url(url):
    # extract base url from given url
    base_url = convert_to_fqdn(url)

    if 'https://' in url:
        base_url = 'https://' + base_url
    else:
        base_url = 'http://' + base_url

    return base_url + '/'


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


def prioritize_relevant(hops):
    '''move relevant word at the beginning of the queue'''
    front = []
    rest = []
    for link, depth in hops:
        has_relevant = False
        for word in RELEVANT_WORDS:
            if word in link:
                front += [(link, depth)]
                has_relevant = True
                break
        if not has_relevant:
            rest += [(link, depth)]

    return front + rest


def create_out_and_err_files(export_path):
    suffix = ''
    out_log_path = os.path.join(export_path, 'out.log')
    err_log_path = os.path.join(export_path, 'err.log')
    if os.path.exists(out_log_path) or os.path.exists(err_log_path):
        suffix += str(random.randint(100_000, 999_999))
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


def main(url, urls_file_path, export_path,
         crawl_sleep,
         depth, max_pages, max_threads,
         include_fragmet, bump_relevant, peserve_uri, use_buffer,
         action):
    user_inputs = []
    crawl_inputs = []

    if urls_file_path is None:
        user_inputs += [(url, depth, crawl_sleep)]
    else:
        # read urls and other data from file
        lines = []
        with open(urls_file_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            # set default or passed values from command line in case
            # they are not present in the file for given line
            read_depth, read_crawl_sleep = depth, crawl_sleep

            line = line.replace('\n', '').strip()
            parts = line.split(' ')
            if len(parts) == 1 and parts[0] != '':
                read_url = parts[0]
            elif len(parts) == 2:
                read_depth, read_url = parts[0], parts[1]
            elif len(parts) == 3:
                read_depth, read_crawl_sleep, read_url = parts[0], parts[1], parts[2]
            else:
                print(f'WARN: {line=} is not in valid format. Ignored')
                continue

            if not read_url.startswith('http://') and not read_url.startswith('https://'):
                print(f"WARN: {read_url=} should start with 'http://' or 'https://'. Ignored")
                continue  # TODO add option to choose action in this situation

            user_inputs += [(read_url, read_depth, read_crawl_sleep)]

    # if there are too many links buffer output to avoid load on storage device
    if len(user_inputs) > BUFF_THRESHOLD:
        use_buffer = True

    # prepare crawl inputs
    for read_url, read_depth, read_crawl_sleep in user_inputs:
        output_fname = convert_to_fqdn(read_url)
        export_path_for_url = os.path.join(export_path, output_fname)

        if not peserve_uri:
            read_url = convert_to_base_url(read_url)

        crawl_inputs += [(
            export_path_for_url,
            read_url,
            read_depth,
            max_pages,
            read_crawl_sleep,
            include_fragmet,
            bump_relevant,
            use_buffer,
            action,
            export_path_for_url  # TODO
            )]

    print(f'INFO: PID: {os.getpid()!r}')
    print('INFO: Start submitting URls for crawling...')

    # crawl each website in seperate threead
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        # Submit each URL for crawling
        FUTURES = [executor.submit(crawl_website, *crawl_input) for crawl_input in crawl_inputs]

        print('INFO: Waiting threads to complete...')

        # Wait for all tasks to complete
        wait(FUTURES)
        print('INFO: Threads have completed the crawling')


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Crawl website and do something with for each page',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(f'''\
            Additional details
            ------------------
            Full input line format is: '[DEPTH [CRAWL_SLEEP]] URL"

            DEPTH and CRAWL_SLEEP are optional and if a number is present it will be consider as DEPTH.
            For example, "3 https://example.com" means that the URL should be crawled to a depth of 3.

            If some of the fields (DEPTH or CRAWL_SLEEP) are present in the line then corresponding argument is ignored.

            Writing too much on the storage drive can reduce its lifespan. To mitigate this issue, if there are more than
            {BUFF_THRESHOLD} links, informational and error messages will be buffered and written at the end of the crawling process.

            RELEVANT_WORDS={RELEVANT_WORDS}
            '''))

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--url',
        help='URL of the website to crawl',
        required=False,
        dest='url')
    input_group.add_argument(
        '-f', '--file',
        help='Path to the file with URLs of the websites to crawl',
        required=False,
        dest='urls_file_path',
        default=None,
        type=str)

    parser.add_argument(
        '-a', '--action',
        help="Action to perform at a time of visiting the page",
        required=False,
        dest='action',
        choices=['screenshot'],
        default='screenshot',
        type=str)
    parser.add_argument(
        '-b', '--buffer',
        help="Buffer errors and outputs until crawling of website is finished and then create logs",
        required=False,
        dest='use_buffer',
        action='store_const',
        const=True,
        default=False)
    parser.add_argument(
        '-br', '--bump-relevant',
        help="Bump relevant links to the top of the visiting queue (based on RELEVANT_WORDS list)",
        required=False,
        dest='bump_relevant',
        action='store_const',
        const=True,
        default=False)
    parser.add_argument(
        '-ep', '--export-path',
        help='Path to destination directory for exporting',
        required=False,
        dest='export_path',
        default='./results')
    parser.add_argument(
        '-cs', '--crawl-sleep',
        help='Time to sleep between each page visit (default: %(default)s)',
        required=False,
        dest='crawl_sleep',
        default=2,
        type=int)
    parser.add_argument(
        '-d', '--depth',
        help='Maximum crawl depth (default: %(default)s)',
        required=False,
        dest='depth',
        default=2,
        type=int)
    parser.add_argument(
        '-if', '--include-fragment',
        help="Consider links with URI Fragmet (e.g. http://example.com/some#fragmet) as seperate page",
        required=False,
        dest='include_fragmet',
        action='store_const',
        const=True,
        default=False)
    parser.add_argument(
        '-ol', '--output-log-path',
        help="Path to output log file. Ignored if '-f'/'--file' is used",
        required=False,
        dest='out_log_path',
        default=None,
        type=str)
    parser.add_argument(
        '-el', '--error-log-path',
        help="Path to error log file. Ignored if '-f'/'--file' is used",
        required=False,
        dest='err_log_path',
        default=None,
        type=str)
    parser.add_argument(
        '-t', '--threads',
        help="Maximum number of threads to use if '-f'/'--file' is provided (default: %(default)s)",
        required=False,
        dest='max_threads',
        default=4,
        type=int)
    parser.add_argument(
        '-mp', '--max-pages',
        help='''
                Maximum number of pages to scrape
                and page is considered scraped if the action is performed successfuly (default: unlimited)
                ''',
        required=False,
        dest='max_pages',
        default=None,
        type=int)
    parser.add_argument(
        '-p', '--preserve',
        help="Preserve whole URI (e.g. \'http://example.com/something/\' instead of  \'http://example.com/\')",
        required=False,
        dest='peserve_uri',
        action='store_const',
        const=True,
        default=False)

    args = parser.parse_args()

    if args.url is not None:
        if not (args.url.startswith('http://')
                or args.url.startswith('https://')):
            parser.error("url should start with 'http://' or 'https://'")
            sys.exit()

    # create export dir if not present
    try:
        os.mkdir(args.export_path)
    except FileExistsError:
        print(f'INFO: Directory {args.export_path!r} already exists')
    except OSError as e:
        args.export_path = os.getcwd()
        print(f'''
              ERROR: Unable create directory at {args.export_path!r}
              (reason: {e.strerror if hasattr(e, "strerror") else "unknown"}).
              The current directory has been set as the export directory
              ''')

    # map choice to corresponding function
    action = lambda x, y, z: print('no action given: ', x, y, z)
    if args.action == 'screenshot':  # TODO replace with match at some point
        action = screenshot_current_webpage

    try:
        main(
            url=args.url,
            urls_file_path=args.urls_file_path,
            export_path=args.export_path,
            crawl_sleep=args.crawl_sleep,
            depth=args.depth,
            max_pages=args.max_pages,
            max_threads=args.max_threads,
            include_fragmet=args.include_fragmet,
            bump_relevant=args.bump_relevant,
            peserve_uri=args.peserve_uri,
            use_buffer=args.use_buffer,
            action=action
            )
    except KeyboardInterrupt:
        print('\nINFO: Exited')
    else:
        print('INFO: Finished')
