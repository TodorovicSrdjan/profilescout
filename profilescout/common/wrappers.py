from abc import ABC, abstractmethod


class WebElementWrapper(ABC):
    """Interface/Base class to abstract WebElement usage."""

    @abstractmethod
    def get_attribute(self, name):
        pass

    @abstractmethod
    def find_elements_with_xpath(self, xpath):
        pass


class WebDriverWrapper(ABC):
    '''
    Interface/Base class to abstract WebDriver usage.
    '''

    @abstractmethod
    def get(self, url):
        pass

    @abstractmethod
    def get_screenshot_as_png(self):
        pass

    @abstractmethod
    def save_screenshot(self, path):
        pass

    @abstractmethod
    def get_page_source(self):
        pass

    @abstractmethod
    def find_elements_with_xpath(self, xpath):
        pass

    @abstractmethod
    def execute_script(self, script):
        pass

    @abstractmethod
    def set_window_size(self, width, height):
        pass

    @abstractmethod
    def quit(self):
        pass
