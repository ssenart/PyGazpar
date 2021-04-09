import logging
from selenium.webdriver.remote.webelement import WebElement


# ------------------------------------------------------------------------------------------------------------
class WebElementWrapper:

    logger = logging.getLogger(__name__)

    # ------------------------------------------------------
    def __init__(self, element: WebElement, description: str, tmp_directory: str):

        self.__element = element
        self.__description = description
        self.__tmp_directory = tmp_directory

    # ------------------------------------------------------
    def click(self):

        WebElementWrapper.logger.debug(f"click(): {self.__description}...")
        try:
            self.__element.click()
            WebElementWrapper.logger.debug("click() -> Ok")
        except Exception:
            WebElementWrapper.logger.warning("click(): {self.__description} -> Error", exc_info=True)
            self.__element.parent.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")
            raise

    # ------------------------------------------------------
    def send_keys(self, value: str):

        WebElementWrapper.logger.debug(f"send_keys({value}): {self.__description}...")
        try:
            self.__element.send_keys(value)
            WebElementWrapper.logger.debug(f"send_keys({value}) -> Ok")
        except Exception:
            WebElementWrapper.logger.warning(f"send_keys({value}): {self.__description} -> Error", exc_info=True)
            self.__element.parent.save_screenshot(f"{self.__tmp_directory}/error_screenshot.png")
            raise
