import os
import time

from enum import Enum

from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, StaleElementReferenceException

from common.constants import ConstantsNamespace
from common.exceptions import LongFilenameException
from link.utils import PageLink, to_filename, is_valid
from link.hop import is_valid_link, PageLink


constants = ConstantsNamespace


WebpageActionType = Enum(
     'WebpageActionType', ['UNKNOWN', 'SCREENSHOT_AND_STORE']
)


class ActionResult:
    def __init__(self, successful, val=None):
        self.successful = successful
        self.val = val


class WebpageAction:
    def __init__(self, action_type, *action_args):
        self.action_type = action_type
        self.args = action_args
        self.func = self.__type_to_func()

    def __type_to_func(self):
        if self.action_type == WebpageActionType.SCREENSHOT_AND_STORE:
            return Webpage.take_screenshot_and_store

        return lambda args: f'Unknown function[{args=}]'


class Webpage:
    def __init__(self, web_driver, page_link, err_file):
        self.__web_driver = web_driver
        self.link = page_link
        self.__err_file = err_file

    def visit(self):
        # navigate to the web page you want to capture
        try:
            self.__web_driver.get(self.link.url)
        except WebDriverException:
            # if not successful, retry after RETRY_TIME seconds
            time.sleep(constants.RETRY_TIME)

            try:
                self.__web_driver.get(self.link.url)
            except WebDriverException as e:
                raise e  # TODO

        # pause videos that have autoplay set to true
        pause_ap_script = 'videos = document.querySelectorAll("video"); for(video of videos) {video.pause()}'
        self.__web_driver.execute_script(pause_ap_script)

        content_type = self.__web_driver.execute_script("return document.contentType")

        if content_type.startswith('text'):
            return True

        return False

    def __get_valid_img_path(self, export_path, width=2880, height=1620):
        self.__web_driver.set_window_size(width, height)

        filename = ''

        try:
            filename = to_filename(self.link.url, export_path)
        except LongFilenameException as lfe:
            filename = filename[:(lfe.limit - len(constants.IMG_EXT) - 1)] + '.' + constants.IMG_EXT
            print('WARN: Link was too long.',
                  f'The filename of the screenshot has changed to: {filename}',
                  file=self.__err_file)

        path = os.path.join(export_path, filename)
        if os.path.exists(path):
            print(f'WARN: Screenshot already exists at: {path}', file=self.__err_file)
            return None

        return path

    def take_screenshot_and_store(self, export_path, width=2880, height=1620):
        path = self.__get_valid_img_path(export_path, width, height)

        if path is None:
            return ActionResult(False)

        # take a screenshot of the entire web page and save it as an image file
        successful = self.__web_driver.save_screenshot(path)

        return ActionResult(successful, path)

    def extract_links(self, base_url, include_fragment=False):
        page_links = []
        urls = []
        a_tags = self.__web_driver.find_elements(By.XPATH, '//a[@href]')
        for a_tag in a_tags:
            href = ''
            try:
                href = a_tag.get_attribute('href').strip()
            except StaleElementReferenceException:
                print(f'ERROR: One of the links to visit next, "{self.link.url}",',
                      'is skipped (reason: stale element)',
                      file=self.__err_file)
            except WebDriverException as e:
                print(f'ERROR: One of the links to visit next, "{self.link.url}",',
                      f'is skipped (reason: {str(e)})',
                      file=self.__err_file)
            else:
                idx = href.find('?nocache')
                if idx != -1:
                    href = href[:idx]

                if not include_fragment:
                    # remove fragmet
                    frag_idx = href.find('#')
                    if frag_idx != -1:
                        href = href[:frag_idx]

                if href not in urls and is_valid(href, base_url):
                    urls.append(href)
                    page_links += [PageLink(href, self.link.depth+1)]

        return page_links

    def perform_action(self, action):
        return action.func(self, *action.args)
