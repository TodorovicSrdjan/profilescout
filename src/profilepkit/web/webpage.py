import os
import time

from selenium.webdriver.common.by import By
from selenium.common.exceptions import (WebDriverException,
                                        StaleElementReferenceException,
                                        UnexpectedAlertPresentException)

from common.constants import ConstantsNamespace
from link.hop import is_valid_link


constants = ConstantsNamespace


def visit_page(web_driver, url):
    # navigate to the web page you want to capture
    try:
        web_driver.get(url)
    except WebDriverException:
        # if not successful, retry after RETRY_TIME seconds
        time.sleep(constants.RETRY_TIME)

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
    try:
        filename = web_driver.current_url
    except WebDriverException:
        # try one more time after RETRY_TIME seconds
        time.sleep(constants.RETRY_TIME)
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

    filename = filename.replace(f'__.{constants.IMG_EXT}', f'.{constants.IMG_EXT}')

    for unsafe_part in constants.CHAR_REPLACEMENTS.keys():
        if unsafe_part in filename:
            filename = filename.replace(unsafe_part, constants.CHAR_REPLACEMENTS[unsafe_part])

    # check if filename exceeds upper limit for number of characters
    FNAME_MAX_LEN = os.pathconf(export_path, 'PC_NAME_MAX')
    if len(filename) + len(constants.IMG_EXT) + 1 > FNAME_MAX_LEN:
        filename = filename[:(FNAME_MAX_LEN - len(constants.IMG_EXT) - 1)] + '.' + constants.IMG_EXT
        print(f'WARN: Link was too long. The filename of the screenshot has changed to: {filename}', file=err_file)
    else:
        filename += '.' + constants.IMG_EXT

    path = os.path.join(export_path, filename)
    if os.path.exists(path):
        print(f'WARN: Screenshot already exists at: {path}', file=err_file)
        return False

    # take a screenshot of the entire web page and save it as an image file
    return web_driver.save_screenshot(path)


def extract_links(web_driver, base_url, url, depth, err_file, include_fragmet=False):
    hops = []
    urls = []
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
                    
            if href not in urls and is_valid_link(href, base_url):
                urls.append(href)
                hops += [(href, depth+1)]

    return hops
