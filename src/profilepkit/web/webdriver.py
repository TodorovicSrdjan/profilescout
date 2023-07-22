import platform

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from common.constants import ConstantsNamespace


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

    return web_driver
