import os
import sys
import textwrap

from concurrent.futures import ThreadPoolExecutor, wait

from common.constants import ConstantsNamespace
from link.utils import to_fqdn, to_base_url
from web.webpage import WebpageActionType, WebpageAction
from web.crawl import CrawlOptions, crawl_website
from classification.classifier import CLASSIFIERS_DIR

constants = ConstantsNamespace


def main(url, urls_file_path, export_path,
         crawl_sleep,
         depth, max_pages, max_threads,
         include_fragment, bump_relevant, peserve_uri, use_buffer,
         action_type,
         resolution, image_classifier):
    user_inputs = []
    crawl_inputs = []
    constants = ConstantsNamespace()

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
    if len(user_inputs) > constants.BUFF_THRESHOLD:
        use_buffer = True

    # prepare crawl inputs
    for read_url, read_depth, read_crawl_sleep in user_inputs:
        output_fname = to_fqdn(read_url)
        export_path_for_url = os.path.join(export_path, output_fname)

        args = [action_type]
        if action_type == WebpageActionType.SCREENSHOT_AND_STORE:
            args.extend([export_path_for_url, *resolution])
        elif action_type == WebpageActionType.FIND_ORIGIN:
            args.extend([image_classifier, *resolution])

        action = WebpageAction(*args)

        if not peserve_uri:
            read_url = to_base_url(read_url)

        crawl_options = CrawlOptions(
            read_depth,
            max_pages,
            read_crawl_sleep,
            include_fragment,
            bump_relevant,
            use_buffer)

        crawl_inputs += [(
            export_path_for_url,
            read_url,
            action,
            crawl_options)]

    print(f'INFO: PID: {os.getpid()!r}')
    print('INFO: Start submitting URls for crawling...')

    # crawl each website in seperate threead
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        # Submit each URL for crawling
        futures = [executor.submit(crawl_website, *crawl_input) for crawl_input in crawl_inputs]

        print('INFO: Waiting threads to complete...')

        # Wait for all tasks to complete
        wait(futures)
        print('INFO: Threads have completed the crawling')


if __name__ == "__main__":
    import argparse

    action_choices = [at.name.lower() for at in list(WebpageActionType)]
    action_choices.remove(WebpageActionType.UNKNOWN.name.lower())
    default_action_choice = next(filter(lambda c: 'store' in c, action_choices))

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
            {constants.BUFF_THRESHOLD} links, informational and error messages will be buffered and written at the end of
            the crawling process.

            RELEVANT_WORDS={constants.RELEVANT_WORDS}
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
        help="Action to perform at a time of visiting the page  (default: %(default)s)",
        required=False,
        dest='action',
        choices=action_choices,
        default=default_action_choice,
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
        '-ic', '--image-classifier',
        help="Image classifier to be used for identifying profile pages (default: %(default)s)",
        required=False,
        dest='image_classifier',
        choices=constants.IMAGE_CLASSIFIERS,
        default=constants.IMAGE_CLASSIFIERS[0],
        type=str)
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
        help="Consider links with URI Fragment (e.g. http://example.com/some#fragment) as seperate page",
        required=False,
        dest='include_fragment',
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
    parser.add_argument(
        '-r', '--resolution',
        help="Resolution of headless browser and output images. Format: WIDTHxHIGHT (default: %(default)s)",
        required=False,
        dest='resolution',
        default=f'{constants.WIDTH}x{constants.HEIGHT}',
        type=str)

    args = parser.parse_args()

    if args.url is not None:
        if not (args.url.startswith('http://')
                or args.url.startswith('https://')):
            parser.error("url should start with 'http://' or 'https://'")
            sys.exit()

    args.resolution = args.resolution.split('x')
    if (len(args.resolution) < 2 
    or not args.resolution[0].isdigit()
    or args.resolution[0][0] == '0'
    or not args.resolution[1].isdigit()
    or args.resolution[1][0] == '0'
    ):
        parser.error("valid format for resolution: WIDTHxHEIGHT. Example: 2880x1620")
        sys.exit()

    # create export dir if not present
    try:
        os.mkdir(args.export_path)
    except FileExistsError:
        print(f'INFO: Directory {args.export_path!r} already exists')
    except OSError as e:
        args.export_path = os.getcwd()
        parser.error(f'''
              ERROR: Unable create directory at {args.export_path!r}
              (reason: {e.strerror if hasattr(e, "strerror") else "unknown"}).
              The current directory has been set as the export directory
              ''')
        sys.exit()

    # map action str to enum
    action_type = getattr(WebpageActionType, args.action.upper(), None)
    
    try:
        if not os.listdir(CLASSIFIERS_DIR):
            h5_files = [file for file in os.listdir(CLASSIFIERS_DIR) if file.endswith('.h5')]

            if len(h5_files) == 0:
                parser.error(f'Directory {CLASSIFIERS_DIR!r} does not contain any .h5 files');
                sys.exit()
                
            if args.image_classifier not in h5_files:
                parser.error(f'Model \'{args.image_classifier}.h5\' is not found at {CLASSIFIERS_DIR!r}');
                sys.exit()
    except FileNotFoundError:
        parser.error(f'Directory {CLASSIFIERS_DIR!r} is not present');
        sys.exit()

    try:
        main(
            url=args.url,
            urls_file_path=args.urls_file_path,
            export_path=args.export_path,
            crawl_sleep=args.crawl_sleep,
            depth=args.depth,
            max_pages=args.max_pages,
            max_threads=args.max_threads,
            include_fragment=args.include_fragment,
            bump_relevant=args.bump_relevant,
            peserve_uri=args.peserve_uri,
            use_buffer=args.use_buffer,
            action_type=action_type,
            resolution=args.resolution,
            image_classifier=args.image_classifier)
    except KeyboardInterrupt:
        print('\nINFO: Exited')
    else:
        print('INFO: Finished')
