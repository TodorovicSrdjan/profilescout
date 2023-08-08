import os
import time

from enum import Enum
from PIL import Image
from io import BytesIO

from profilescout.common.exceptions import WebDriverException, StaleElementReferenceException
from profilescout.common.constants import ConstantsNamespace
from profilescout.link.utils import PageLink, is_valid, url2file_path
from profilescout.classification.classifier import ImageClassifier


constants = ConstantsNamespace

WebpageActionType = Enum(
     'WebpageActionType', [
         'UNKNOWN',
         'SCRAPE_PAGES',
         'SCRAPE_PROFILES',
         'FIND_ORIGIN']
)

ScrapeOption = Enum('ScrapeOption', ['ALL', 'HTML', 'SCREENSHOT'])


class ActionResult:
    def __init__(self, successful, val=None, msg=''):
        self.successful = successful
        self.val = val
        self.msg = msg


class Webpage:
    def __init__(self, web_driver, page_link, out_file, err_file):
        self.__web_driver = web_driver
        self.link = page_link
        self.__out_file = out_file
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

    def get_html(self):
        return self.__web_driver.get_page_source()

    def take_screenshot(self, width=constants.WIDTH, height=constants.HEIGHT):
        '''takes screenshot of current page and returns image as byte array'''
        self.__web_driver.set_window_size(width, height)

        # take a screenshot of the entire web page and store it in buffer
        screenshot_bytes = BytesIO(self.__web_driver.get_screenshot_as_png())  # TODO close
        image = Image.open(screenshot_bytes).convert("RGB")

        return ActionResult(True, image, 'Image is stored in a buffer')

    def scrape_page(self, export_path, scrape_option, width=constants.WIDTH, height=constants.HEIGHT):
        successful = True
        result = {'html': None, 'screenshot': None}
        self.__web_driver.set_window_size(width, height)

        if scrape_option in [ScrapeOption.ALL, ScrapeOption.SCREENSHOT]:
            # take a screenshot of the entire web page and save it as an image file
            path = url2file_path(
                self.link.url,
                os.path.join(export_path, 'screenshots'),
                constants.IMG_EXT,
                self.__err_file)
            if path is None:
                return ActionResult(False, 'Failed to craft valid storing path for the screenshot')
            result['screenshot'] = path
            successful = self.__web_driver.save_screenshot(path)

        if scrape_option in [ScrapeOption.ALL, ScrapeOption.HTML]:
            # save html as a file
            path = url2file_path(
                self.link.url,
                os.path.join(export_path, 'html'),
                'html',
                self.__err_file)
            if path is None:
                return ActionResult(False, 'Failed to craft valid storing path for the html')
            result['html'] = path
            html = self.get_html()
            with open(path, 'w') as f:
                f.write(html)

        return ActionResult(successful, result)

    def is_profile(self, classifier_name, width, height):
        result = self.take_screenshot(width, height)

        if not result.successful:
            return ActionResult(False, 'Inference was not successfully performed')

        img_bytes = result.val
        img_classifier = ImageClassifier(classifier_name)
        profile_detected = img_classifier.predict(img_bytes, height, width)

        if profile_detected:
            print(f'INFO: Detected as profile page: {self.link.url}', file=self.__out_file)

        return ActionResult(True, profile_detected, 'Inference was successfully performed')

    def extract_links(self, base_url, include_fragment=False, from_structure=False, previous_links=[]):
        page_links = []
        urls = []
        xpath = '//a[@href]'
        if from_structure:
            xpath = '''//*[self::table or self::ol or self::ul or self::section]//a[@href
                            and not(ancestor::header or ancestor::footer or ancestor::nav)
                            and not(ancestor::div[contains(@id, 'footer')])
                            and not(ancestor::div[contains(@id, 'nav')])
                            and not(ancestor::div[contains(@id, 'navigation')])
                            and not(ancestor::div[contains(@class, 'footer')])
                            and not(ancestor::div[contains(@class, 'nav')])
                            and not(ancestor::div[contains(@class, 'navigation')])
                            and not(ancestor::div[contains(@role, 'footer')])
                            and not(ancestor::div[contains(@role, 'nav')])
                            and not(ancestor::div[contains(@role, 'navigation')])
                        ]'''
        a_tags = self.__web_driver.find_elements_with_xpath(xpath)
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
                    # remove fragment
                    frag_idx = href.find('#')
                    if frag_idx != -1:
                        href = href[:frag_idx]

                if href not in urls and is_valid(href, base_url):
                    urls.append(href)
                    page_link = PageLink(href, self.link.depth+1, self.link.url)
                    if from_structure and page_link.url in previous_links:
                        continue
                    page_links += [page_link]

        return page_links
