import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    StaleElementReferenceException as SeleniumStaleElementReferenceException,
    WebDriverException as SeleniumWebDriverException)

from profilescout.common.constants import ConstantsNamespace
from profilescout.common.wrappers import WebElementWrapper, WebDriverWrapper
from profilescout.common.exceptions import StaleElementReferenceException, WebDriverException


constants = ConstantsNamespace


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
    web_driver.implicitly_wait(constants.IMPL_WAIT_FOR_FULL_LOAD)

    return WebDriver(web_driver)


class WebElement(WebElementWrapper):
    """Implementation of WebElementWrapper that wraps WebElement."""

    def __init__(self, element):
        self.element = element

    def get_attribute(self, name):
        try:
            return self.element.get_attribute(name)
        except SeleniumStaleElementReferenceException as e:
            raise StaleElementReferenceException.from_stale_element_exception(e)

    def find_elements_with_xpath(self, xpath):
        return [WebElement(el) for el in self.element.find_elements(By.XPATH, xpath)]

    @property
    def text(self):
        return self.element.text


class WebDriver(WebDriverWrapper):
    """Implementation of WebDriverWrapper that wraps WebDriver."""

    def __init__(self, driver):
        self._driver = driver

    def get(self, url):
        try:
            return self._driver.get(url)
        except SeleniumWebDriverException as e:
            raise WebDriverException.from_webdriver_exception(e)

    def get_screenshot_as_png(self):
        return self._driver.get_screenshot_as_png()

    def save_screenshot(self, path):
        return self._driver.save_screenshot(path)

    def get_page_source(self):
        return self._driver.page_source

    def find_elements_with_xpath(self, xpath):
        return [WebElement(el) for el in self._driver.find_elements(By.XPATH, xpath)]

    def execute_script(self, script):
        return self._driver.execute_script(script)

    def set_window_size(self, width, height):
        return self._driver.set_window_size(width, height)

    def quit(self):
        self._driver.quit()
