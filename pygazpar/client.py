import os
from selenium import webdriver
import time
import glob
from openpyxl import load_workbook

HOME_URL = 'https://monespace.grdf.fr'
LOGIN_URL = HOME_URL + '/monespace'
DATA_URL = HOME_URL + '/monespace/particulier/consommation/consommations'
DATA_FILENAME = 'Consommations gaz_*.xlsx'

DEFAULT_TMP_DIRECTORY = '/tmp'
DEFAULT_FIREFOX_WEBDRIVER = os.getcwd() + '/geckodriver'

class Client(object):
    def __init__(self, username, password, firefox_webdriver_executable = DEFAULT_FIREFOX_WEBDRIVER, tmp_directory = DEFAULT_TMP_DIRECTORY):
        self.__username = username
        self.__password = password
        self.__firefox_webdriver_executable = firefox_webdriver_executable
        self.__tmp_directory = tmp_directory
        self.data = []

    def update(self):

        # XLSX is in the TMP directory
        data_file_path_pattern = self.__tmp_directory + '/' + DATA_FILENAME

        # We remove an eventual existing file (from a previous run that has not deleted it)
        file_list = glob.glob(data_file_path_pattern)
        for filename in file_list:
            if os.path.isfile(filename):
                os.remove(filename)

        # Initialize the Firefox WebDriver
        profile = webdriver.FirefoxProfile()
        options = webdriver.FirefoxOptions()
        options.headless = True
        profile.set_preference('browser.download.folderList', 2)  # custom location
        profile.set_preference('browser.download.manager.showWhenStarting', False)
        profile.set_preference('browser.helperApps.alwaysAsk.force', False)
        profile.set_preference('browser.download.dir', self.__tmp_directory)
        profile.set_preference('browser.helperApps.neverAsk.saveToDisk', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        try:
            driver = webdriver.Firefox(executable_path=self.__firefox_webdriver_executable, firefox_profile=profile, options=options, service_log_path=self.__tmp_directory + '/geckodriver.log')
            driver.set_window_position(0, 0)
            driver.set_window_size(1200, 1200)
            
            driver.implicitly_wait(10)
            
            driver.get(HOME_URL)
            
            # Fill login form
            email_element = driver.find_element_by_id("_EspacePerso_WAR_EPportlet_:seConnecterForm:email")
            password_element = driver.find_element_by_id("_EspacePerso_WAR_EPportlet_:seConnecterForm:passwordSecretSeConnecter")
            
            email_element.send_keys(self.__username)
            password_element.send_keys(self.__password)
            
            submit_button_element = driver.find_element_by_id('_EspacePerso_WAR_EPportlet_:seConnecterForm:meConnecter')
            submit_button_element.click()
            
            # Wait a few for the login to complete
            time.sleep(10)
            
            # Page 'votre consomation'
            driver.get(DATA_URL)

            # Wait a few for the data page load to complete
            time.sleep(10)
            
            # Close Popup Windows
            close_popup_element = driver.find_elements_by_css_selector('.abtasty-modal__close > svg')
            close_popup_element[0].click()
            time.sleep(5)

            # Select daily consumption
            daily_consumption_element = driver.find_element_by_xpath("//table[@id='_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite1']/tbody/tr/td[3]/label")
            daily_consumption_element.click()
            time.sleep(5)

            # Download file
            download_button_element = driver.find_element_by_xpath("//button[@id='_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:telechargerDonnees']/span")
            download_button_element.click()
            
            # Wait a few for the download to complete
            time.sleep(10)
            
            # Load the XLSX file into the data structure
            file_list = glob.glob(data_file_path_pattern)

            for filename in file_list:
                wb = load_workbook(filename = filename)
                ws = wb['Historique par jour']
                for rownum in range(8, 365):
                    row = {}
                    if ws.cell(column=2, row=rownum).value != None:
                        row['time'] = ws.cell(column=2, row=rownum).value
                        row['total_m3'] = ws.cell(column=4, row=rownum).value
                        row['total_kWh'] = float(ws.cell(column=4, row=rownum).value) * 11.244
                        row['daily_m3'] = ws.cell(column=5, row=rownum).value
                        row['daily_kWh'] = ws.cell(column=6, row=rownum).value
                        self.data.append(row)
                wb.close()
            
                os.remove(filename)

        finally:
            # Close the driver
            driver.close()
