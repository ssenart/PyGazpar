import os
import time
import glob
import logging
from abc import ABC, abstractmethod
from pygazpar.enum import Frequency
from pygazpar.datafileparser import DataFileParser
from pygazpar.webdriverwrapper import WebDriverWrapper


HOME_URL = 'https://monespace.grdf.fr'
LOGIN_URL = HOME_URL + '/monespace/connexion'
WELCOME_URL = HOME_URL + '/monespace/particulier/accueil'
DATA_URL = HOME_URL + '/monespace/particulier/consommation/consommations'
DATA_FILENAME = 'Consommations gaz_*.xlsx'

DEFAULT_TMP_DIRECTORY = '/tmp'
DEFAULT_FIREFOX_WEBDRIVER = os.getcwd() + '/geckodriver'
DEFAULT_WAIT_TIME = 30
DEFAULT_LAST_N_ROWS = 0
DEFAULT_HEADLESS_MODE = True
DEFAULT_METER_READING_FREQUENCY = Frequency.DAILY


# ------------------------------------------------------------------------------------------------------------
class LoginError(Exception):
    """ Client has failed to login in GrDF Web site (check username/password)"""
    pass


# ------------------------------------------------------------------------------------------------------------
class IClient(ABC):

    @abstractmethod
    def data(self) -> dict:
        pass

    @abstractmethod
    def update(self):
        pass


# ------------------------------------------------------------------------------------------------------------
class Client(IClient):

    logger = logging.getLogger(__name__)

    # ------------------------------------------------------
    def __init__(self, username: str, password: str, firefox_webdriver_executable: str = DEFAULT_FIREFOX_WEBDRIVER, wait_time: int = DEFAULT_WAIT_TIME, tmp_directory: str = DEFAULT_TMP_DIRECTORY, lastNRows: int = DEFAULT_LAST_N_ROWS, headLessMode: bool = DEFAULT_HEADLESS_MODE, meterReadingFrequency: Frequency = DEFAULT_METER_READING_FREQUENCY):
        self.__username = username
        self.__password = password
        self.__firefox_webdriver_executable = firefox_webdriver_executable
        self.__wait_time = wait_time
        self.__tmp_directory = tmp_directory
        self.__data = []
        self.__lastNRows = lastNRows
        self.__headlessMode = headLessMode
        self.__meterReadingFrequency = meterReadingFrequency

    # ------------------------------------------------------
    def data(self) -> dict:
        return self.__data

    # ------------------------------------------------------
    def __acceptCookies(self, driver: WebDriverWrapper):

        try:
            cookies_accept_button = driver.find_element_by_xpath("//a[@id='_EPcommonPage_WAR_EPportlet_:formBandeauCnil:j_idt12']", "Cookies accept button", False)
            cookies_accept_button.click()
        except Exception:
            # Do nothing, because the Pop up may not appear.
            pass

    # ------------------------------------------------------
    def __acceptPrivacyConditions(self, driver: WebDriverWrapper):

        try:
            # id=btn_accept_banner
            accept_button = driver.find_element_by_id("btn_accept_banner", "Privacy Conditions accept button", False)
            accept_button.click()
        except Exception:
            # Do nothing, because the Pop up may not appear.
            pass

    # ------------------------------------------------------
    def __closeEventualPopup(self, driver: WebDriverWrapper):

        # Accept an eventual Privacy Conditions popup.
        self.__acceptPrivacyConditions(driver)

        # Eventually, click Accept in the lower banner to accept cookies from the site.
        self.__acceptCookies(driver)

        # Eventually, close Advertisement Popup Windows.
        try:
            advertisement_popup_element = driver.find_element_by_xpath("/html/body/abtasty-modal/div/div[1]", "Advertisement close button", False)
            advertisement_popup_element.click()
        except Exception:
            # Do nothing, because the Pop up may not appear.
            pass

        # Eventually, close Survey Popup Windows : /html/body/div[12]/div[2] or //*[@id="mfbIframeClose"]
        try:
            survey_popup_element = driver.find_element_by_xpath("//*[@id='mfbIframeClose']", "Survey close button", False)
            survey_popup_element.click()
        except Exception:
            # Do nothing, because the Pop up may not appear.
            pass

    # ------------------------------------------------------
    def update(self):

        Client.logger.debug("Start updating the data...")

        # XLSX is in the TMP directory
        data_file_path_pattern = self.__tmp_directory + '/' + DATA_FILENAME

        # We remove an eventual existing data file (from a previous run that has not deleted it)
        file_list = glob.glob(data_file_path_pattern)
        for filename in file_list:
            if os.path.isfile(filename):
                os.remove(filename)

        # Create the WebDriver with the ability to log and take screenshot for debugging.
        driver = WebDriverWrapper(self.__firefox_webdriver_executable, self.__wait_time, self.__tmp_directory, self.__headlessMode)

        try:

            # Login URL
            driver.get(LOGIN_URL, "Go to login page")

            # Accept an eventual Privacy Conditions popup.
            self.__acceptPrivacyConditions(driver)

            # Fill login form
            email_element = driver.find_element_by_id("_EspacePerso_WAR_EPportlet_:seConnecterForm:email", "Login page: Email text field")
            password_element = driver.find_element_by_id("_EspacePerso_WAR_EPportlet_:seConnecterForm:passwordSecretSeConnecter", "Login page: Password text field")

            email_element.send_keys(self.__username)
            password_element.send_keys(self.__password)

            # Submit the login form.
            submit_button_element = driver.find_element_by_id("_EspacePerso_WAR_EPportlet_:seConnecterForm:meConnecter", "Login page: 'Me connecter' button")
            submit_button_element.click()

            # Close eventual popup Windows or Assistant appearing.
            self.__closeEventualPopup(driver)

            # Once we find the 'Acceder' button from the main page, we are logged on successfully.
            try:
                driver.find_element_by_xpath("//div[2]/div[2]/div/a/div", "Welcome page: 'Acceder' button of 'Suivi de consommation'")
            except Exception:
                # Perhaps, login has failed.
                if driver.current_url() == WELCOME_URL:
                    # We're good.
                    pass
                elif driver.current_url() == LOGIN_URL:
                    raise LoginError("GrDF sign in has failed, please check your username/password")
                else:
                    raise

            # Page 'votre consommation'
            driver.get(DATA_URL, "Go to 'Consommations' page")

            # Wait for the data page to load completely.
            time.sleep(self.__wait_time)

            # Eventually, close TokyWoky assistant which may hide the Download button.
            try:
                tokyWoky_close_button = driver.find_element_by_xpath("//div[@id='toky_container']/div/div", "TokyWoky assistant close button")
                tokyWoky_close_button.click()
            except Exception:
                # Do nothing, because the Pop up may not appear.
                pass

            buttonDescriptionByFrequency = {
                Frequency.HOURLY: "Hourly consumption button",
                Frequency.DAILY: "Daily consumption button",
                Frequency.WEEKLY: "Weekly consumption button",
                Frequency.MONTHLY: "Monthly consumption button"
            }

            xpathByFrequency = {
                Frequency.HOURLY: "//table[@id='_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite1']/tbody/tr/td[4]/label",
                Frequency.DAILY: "//table[@id='_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite1']/tbody/tr/td[3]/label",
                Frequency.WEEKLY: "//table[@id='_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite1']/tbody/tr/td[2]/label",
                Frequency.MONTHLY: "//table[@id='_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite1']/tbody/tr/td[1]/label"
            }

            # Select daily consumption
            daily_consumption_element = driver.find_element_by_xpath(xpathByFrequency[self.__meterReadingFrequency], buttonDescriptionByFrequency[self.__meterReadingFrequency])
            daily_consumption_element.click()

            # Download file
            download_button_element = driver.find_element_by_xpath("//button[@title=\"Télécharger\"]/span", "Download button")
            download_button_element.click()

            # Wait a few for the download to complete
            time.sleep(self.__wait_time)

            # Load the XLSX file into the data structure
            file_list = glob.glob(data_file_path_pattern)

            if len(file_list) == 0:
                WebDriverWrapper.logger.warning(f"Not any data file has been found in '{self.__tmp_directory}' directory")

            for filename in file_list:

                self.__data = DataFileParser.parse(filename, self.__meterReadingFrequency, self.__lastNRows)

                os.remove(filename)

            Client.logger.debug("The data update terminates normally")
        except Exception:
            WebDriverWrapper.logger.error("An unexpected error occured while updating the data", exc_info=True)
            raise
        finally:
            # Quit the driver
            driver.quit()


# ------------------------------------------------------------------------------------------------------------
class DummyClient(IClient):

    logger = logging.getLogger(__name__)

    # ------------------------------------------------------
    def __init__(self, lastNRows: int = DEFAULT_LAST_N_ROWS, meterReadingFrequency: Frequency = DEFAULT_METER_READING_FREQUENCY):
        self.__lastNRows = lastNRows
        self.__meterReadingFrequency = meterReadingFrequency
        self.__data = []

    # ------------------------------------------------------
    def data(self) -> dict:
        return self.__data

    # ------------------------------------------------------
    def update(self):

        dataByFrequency = {
            Frequency.HOURLY: [],
            Frequency.DAILY: [
                {
                    "date": "01/07/2019",
                    "start_index_m3": 9802.0,
                    "end_index_m3": 9805.0,
                    "volume_m3": 3.6,
                    "energy_kwh": 40.0,
                    "converter_factor": "11,244",
                    "local_temperature": "",
                    "type": "MES",
                    "timestamp": "2019-08-29T16:56:07.380422"
                },
                {
                    "date": "02/07/2019",
                    "start_index_m3": 9805.0,
                    "end_index_m3": 9808.0,
                    "volume_m3": 2.8,
                    "energy_kwh": 31.0,
                    "converter_factor": "11,244",
                    "local_temperature": "21",
                    "type": "MES",
                    "timestamp": "2019-08-29T16:56:07.380422"
                },
                {
                    "date": "03/07/2019",
                    "start_index_m3": 9808.0,
                    "end_index_m3": 9811.0,
                    "volume_m3": 2.9,
                    "energy_kwh": 33.0,
                    "converter_factor": "11,244",
                    "local_temperature": "",
                    "type": "MES",
                    "timestamp": "2019-08-29T16:56:07.380422"
                }
            ],
            Frequency.WEEKLY: [
                {
                    "date": "Semaine 13 - 2021",
                    "volume_m3": 317.6,
                    "energy_kwh": 3547,
                    "timestamp": "2019-08-29T16:56:07.380422"
                },
                {
                    "date": "Semaine 14 - 2021",
                    "volume_m3": 261.1,
                    "energy_kwh": 2937,
                    "timestamp": "2019-08-29T16:56:07.380422"
                },
                {
                    "date": "Semaine 15 - 2021",
                    "volume_m3": 124.5,
                    "energy_kwh": 1402,
                    "timestamp": "2019-08-29T16:56:07.380422"
                }                
            ],
            Frequency.MONTHLY: [
                {
                    "date": "Février 2021",
                    "volume_m3": 317.6,
                    "energy_kwh": 3547,
                    "timestamp": "2019-08-29T16:56:07.380422"
                },
                {
                    "date": "Mars 2021",
                    "volume_m3": 261.1,
                    "energy_kwh": 2937,
                    "timestamp": "2019-08-29T16:56:07.380422"
                },
                {
                    "date": "Avril 2021",
                    "volume_m3": 124.5,
                    "energy_kwh": 1402,
                    "timestamp": "2019-08-29T16:56:07.380422"
                }
            ]
        }

        self.__data = dataByFrequency[self.__meterReadingFrequency]
