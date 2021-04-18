import os
import logging
from selenium import webdriver
from .webelementwrapper import WebElementWrapper


# ------------------------------------------------------------------------------------------------------------
class WebDriverWrapper:

    logger = logging.getLogger(__name__)

    # ------------------------------------------------------
    def __init__(self, firefox_webdriver_executable: str, wait_time: int, tmp_directory: str, headLessMode: bool):

        self.__firefox_webdriver_executable = firefox_webdriver_executable
        self.__wait_time = wait_time
        self.__tmp_directory = tmp_directory

        # We remove the geckodriver log file
        geckodriverLogFile = f"{self.__tmp_directory}/pygazpar_geckodriver.log"
        if os.path.isfile(geckodriverLogFile):
            os.remove(geckodriverLogFile)

        # Initialize the Firefox WebDriver
        options = webdriver.FirefoxOptions()
        # options.log.level = 'trace'
        options.headless = headLessMode
        profile = webdriver.FirefoxProfile()
        profile.set_preference('browser.download.folderList', 2)  # 2 indicates a custom (see: browser.download.dir) folder.
        profile.set_preference('browser.download.dir', self.__tmp_directory)
        profile.set_preference('browser.download.manager.showWhenStarting', False)  # Whether or not to show the Downloads window when a download begins.
        profile.set_preference('browser.helperApps.alwaysAsk.force', False)
        profile.set_preference('browser.helperApps.neverAsk.saveToDisk', 'application/excel, application/vnd.ms-excel, application/x-excel, application/x-msexcel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        self.__driver = webdriver.Firefox(executable_path=self.__firefox_webdriver_executable, firefox_profile=profile, options=options, service_log_path=geckodriverLogFile)

        self.__driver.set_window_position(0, 0)
        self.__driver.set_window_size(1920, 1200)
        # self.__driver.fullscreen_window()

        self.__driver.implicitly_wait(self.__wait_time)

    # ------------------------------------------------------
    def quit(self):

        WebDriverWrapper.logger.debug("quit()...")
        try:
            self.__driver.quit()
            WebDriverWrapper.logger.debug("quit() -> Ok")
        except Exception:
            WebDriverWrapper.logger.warning("quit() -> Error", exc_info=True)
            self.__driver.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")
            raise

    # ------------------------------------------------------
    def get(self, url: str, description: str):

        WebDriverWrapper.logger.debug(f"get('{url}'): {description}...")
        try:
            res = self.__driver.get(url)
            WebDriverWrapper.logger.debug(f"get('{url}'): {description} -> Ok")
            return res
        except Exception:
            WebDriverWrapper.logger.warning(f"get('{url}'): {description} -> Error", exc_info=True)
            self.__driver.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")
            raise

    # ------------------------------------------------------
    def current_url(self):

        WebDriverWrapper.logger.debug("current_url()...")
        try:
            self.__driver.current_url()
            WebDriverWrapper.logger.debug("current_url() -> Ok")
        except Exception:
            WebDriverWrapper.logger.warning("current_url() -> Error", exc_info=True)
            self.__driver.save_screenshot("{self.__tmp_directory}/error_screenshot.png")
            raise

    # ------------------------------------------------------
    def find_element_by_id(self, id: str, description: str, screenshotOnNotFound: bool = True) -> WebElementWrapper:

        WebDriverWrapper.logger.debug(f"find_element_by_id('{id}'): {description}...")
        try:
            element = self.__driver.find_element_by_id(id)
            res = WebElementWrapper(element, description, self.__tmp_directory)
            WebDriverWrapper.logger.debug(f"find_element_by_id('{id}'): {description} -> Ok")
            return res
        except Exception:
            message = f"find_element_by_id('{id}'): {description} -> Not found"
            if screenshotOnNotFound:
                WebDriverWrapper.logger.warning(message, exc_info=True)
                self.__driver.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")
            else:
                WebDriverWrapper.logger.debug(message, exc_info=False)
            raise

    # ------------------------------------------------------
    def find_element_by_xpath(self, xpath: str, description: str, screenshotOnNotFound: bool = True) -> WebElementWrapper:

        WebDriverWrapper.logger.debug(f"find_element_by_xpath('{xpath}'): {description}...")
        try:
            element = self.__driver.find_element_by_xpath(xpath)
            res = WebElementWrapper(element, description, self.__tmp_directory)
            WebDriverWrapper.logger.debug(f"find_element_by_xpath('{xpath}'): {description} -> Ok")
            return res
        except Exception:
            message = f"find_element_by_xpath('{xpath}'): {description} -> Not found"
            if screenshotOnNotFound:
                WebDriverWrapper.logger.warning(message, exc_info=True)
                self.__driver.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")
            else:
                WebDriverWrapper.logger.debug(message, exc_info=False)
            raise

    # ------------------------------------------------------
    def save_screenshot(self, filename: str):

        WebDriverWrapper.logger.debug(f"save_screenshot('{filename}')...")
        try:
            res = self.__driver.save_screenshot(filename)
            WebDriverWrapper.logger.debug(f"save_screenshot('{filename}') -> Ok")
            return res
        except Exception:
            WebDriverWrapper.logger.warning(f"save_screenshot('{filename}') -> Error", exc_info=True)
