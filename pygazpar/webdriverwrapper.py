import os
import logging
import traceback
from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement

# ------------------------------------------------------------------------------------------------------------
class WebDriverWrapper:

    logger = logging.getLogger(__name__)

    # ------------------------------------------------------
    def __init__(self, firefox_webdriver_executable: str, wait_time: int, tmp_directory: str):

        self.__firefox_webdriver_executable = firefox_webdriver_executable
        self.__wait_time = wait_time
        self.__tmp_directory = tmp_directory

        # We remove the geckodriver log file
        geckodriverLogFile = self.__tmp_directory + '/pygazpar_geckodriver.log'
        if os.path.isfile(geckodriverLogFile):
            os.remove(geckodriverLogFile)

        # Initialize the Firefox WebDriver
        options = webdriver.FirefoxOptions()
        #options.log.level = 'trace'
        options.headless = True
        profile = webdriver.FirefoxProfile()
        profile.set_preference('browser.download.folderList', 2)  # custom location
        profile.set_preference('browser.download.manager.showWhenStarting', False)
        profile.set_preference('browser.helperApps.alwaysAsk.force', False)
        profile.set_preference('browser.download.dir', self.__tmp_directory)
        profile.set_preference('browser.helperApps.neverAsk.saveToDisk', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        self.__driver = webdriver.Firefox(executable_path=self.__firefox_webdriver_executable, firefox_profile=profile, options=options, service_log_path=geckodriverLogFile)

        self.__driver.set_window_position(0, 0)
        self.__driver.set_window_size(1920, 1200)
        #self.__driver.fullscreen_window()

        self.__driver.implicitly_wait(self.__wait_time)


    # ------------------------------------------------------
    def quit(self): 

        WebDriverWrapper.logger.debug(f"quit()...")
        try:
            self.__driver.quit()
            WebDriverWrapper.logger.debug(f"quit() -> Ok")
        except Exception:
            WebDriverWrapper.logger.warning(f"quit() -> Error",  exc_info=True)
            self.__driver.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")


    # ------------------------------------------------------
    def get(self, url: str, description: str): 

        WebDriverWrapper.logger.debug(f"get('{url}') : {description}...")
        try:
            res = self.__driver.get(url)
            WebDriverWrapper.logger.debug(f"get('{url}') -> Ok")
            return res
        except Exception:
            WebDriverWrapper.logger.warning(f"get('{url}') -> Error",  exc_info=True)
            self.__driver.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")


    # ------------------------------------------------------
    def current_url(self): 

        WebDriverWrapper.logger.debug(f"current_url()...")
        try:
            self.__driver.current_url()
            WebDriverWrapper.logger.debug(f"current_url() -> Ok")
        except Exception:
            WebDriverWrapper.logger.warning(f"current_url() -> Error",  exc_info=True)
            self.__driver.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")


    # ------------------------------------------------------
    def find_element_by_id(self, id: str, description: str) -> WebElement:

        WebDriverWrapper.logger.debug(f"find_element_by_id('{id}') : {description}...")
        try:
            res = self.__driver.find_element_by_id(id)
            WebDriverWrapper.logger.debug(f"find_element_by_id('{id}') -> Ok")
            return res
        except Exception:
            WebDriverWrapper.logger.warning(f"find_element_by_id('{id}') -> Error",  exc_info=True)
            self.__driver.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")


    # ------------------------------------------------------
    def find_element_by_xpath(self, xpath: str, description: str) -> WebElement:

        WebDriverWrapper.logger.debug(f"find_element_by_xpath('{xpath}') : {description}...")
        try:
            res = self.__driver.find_element_by_xpath(xpath)
            WebDriverWrapper.logger.debug(f"find_element_by_xpath('{xpath}') -> Ok")
            return res
        except Exception:
            WebDriverWrapper.logger.warning(f"find_element_by_xpath('{xpath}') -> Error",  exc_info=True)
            self.__driver.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")

    # ------------------------------------------------------
    def save_screenshot(self, filename: str):

        WebDriverWrapper.logger.debug(f"save_screenshot('{filename}')...")
        try:
            res = self.__driver.save_screenshot(filename)
            WebDriverWrapper.logger.debug(f"save_screenshot('{filename}') -> Ok")
            return res
        except Exception:
            WebDriverWrapper.logger.warning(f"save_screenshot('{filename}') -> Error",  exc_info=True)
           
