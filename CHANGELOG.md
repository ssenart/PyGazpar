# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0](https://github.com/ssenart/PyGazpar/compare/0.1.27...0.2.0) - 2021-04-21
### Added
- [#12](https://github.com/ssenart/PyGazpar/issues/10): Be able to retrieve consumption not only on a daily basis, but weekly and monthly:
    - API : Add a new parameter 'meterReadingFrequency' to Client that accepts enumeration: Frequency.DAILY, Frequency.WEEKLY or Frequency.MONTHLY.
    - Command line : Add a new argument '--frequency' that accepts values : DAILY, WEEKLY or MONTHLY.
- Be able to test using offline data :
    - API : Add a new parameter 'testMode' to Clients used to specify whether we want to get some live data (testMode=False) and static testing data (testMode=True).
    - Command line : Add a new argument '--testMode' (True if specified and False by default).

## [0.1.27](https://github.com/ssenart/PyGazpar/compare/0.1.26...0.1.27) - 2021-04-20
### Fixed
- [#10](https://github.com/ssenart/PyGazpar/issues/10) : Does not download data file in tmpdir as expected (instead it is downloaded in the default user Download directory). The previous attempt in version 0.1.26 is a failure. The origin of the bug is that we send relative tmp directory path to Webdriver. Additionally, it has to be normalized to the runtime OS.

## [0.1.26](https://github.com/ssenart/PyGazpar/compare/0.1.25...0.1.26) - 2021-04-18
### Fixed
- [#10](https://github.com/ssenart/PyGazpar/issues/10) : Does not download data file in tmpdir as expected (instead it is downloaded in the default user Download directory).

### Added
- A new parameter to drive whether we want Selenium in headless mode or not (mainly for troubleshooting purpose).

## [0.1.25] - 2021-04-15
### Fixed
- Remove useless warning log messages (log message level has been decreased to debug).

## [0.1.24] - 2021-04-14
### Added
- README.md amendment (thanks to pbranly).

## [0.1.23] - 2021-04-09
### Changed
- Final release with CI/CD workflow improvement.

## [0.1.22] - 2021-04-09
### Changed
- Improve CI/CD workflow.

## [0.1.21] - 2021-04-07
### Changed
- Cleanup some codes managing Privacy Conditions popup.

## [0.1.20] - 2021-04-07
### Changed
- Close an eventual Privacy Conditions popup just before clicking the daily button (instead of Cookie banner).

## [0.1.19] - 2021-04-06
### Added
- Close an eventual Cookie popup just before clicking the daily button.
- Add log messages and screenshot capture around click() and send_keys() methods.

## [0.1.18] - 2021-04-05
### Fixed
- Typo in logger usage.

## [0.1.17] - 2021-04-05
### Fixed
- Logger name must be different in each instance. Using __name__ is a good practice, we can get the module hierarchy.

## [0.1.16] - 2021-04-05
### Fixed
- Logger 'pygazpar' initialization must be done inside the main program and not inside the library.

## [0.1.15] - 2021-04-05
### Added
- Many log message to help debugging if GrDF site changes something : pygazpar.log
- Take a screenshot of the corresponding page where a selenium command fails : error_screenshot.png.

## [0.1.14] - 2020-09-23
### Fixed
- GrDF survey popup has to be closed at the home page.
- GrDF Assistant popup may hide the Download button. We have to close it.
- GrDF bottom banner that invite to accept cookies may also hide the Download button. We have to accept it.

### Added
- A new parameter 'lastNRows' to get only the last N most recent records.

## [0.1.13] - 2020-06-30
### Fixed
- GrDF data retrieval from Excel file is not limited to the 1000 first rows any more.

## [0.1.12] - 2020-06-30
### Fixed
- The previous 0.1.11 is not sufficient. Hence, 2 new changes : First, make configurable the waiting time so the user can adapt to its context usage.
Second, the condition on clicking on Download button is now based on the corresponding event and not anymore on its identifier. 

## [0.1.11] - 2020-06-29
### Fixed
- When GrDF Web site is slower than usual, the client may not wait enough time for pages to load and miss to reach the data file.
It occurs with the page containing 'Jour' button which is very long to load (I increase the wait to load time from 5s to 30s).

## [0.1.10] - 2020-06-03
### Fixed
- Extract rows from Excel until line 1000 (instead of 365 as before).

## [0.1.9] - 2019-08-31
### Fixed
- WebDriver window size must be large enough to display all clickable components.

## [0.1.8] - 2019-08-31
### Changed
- Use PropertyNameEnum type to store all property names.

## [0.1.7] - 2019-08-29
### Added
- Add wait_time option to control how much time the library has to wait for Web page element to load (see https://selenium-python.readthedocs.io/waits.html for details).
- Add LoginError exception raised when PyGazpar is unable to sign in the GrDF Web site with the given username/password.
- Refactor all data property names.

## [0.1.6] - 2019-08-26
### Added
- Add README.md and CHANGELOG.md.
- Add Client.data() method to get the updated data.

### Removed
- Remove Client.data property to get the updated data. Replaced with Client.__data private property.

[0.1.25]: https://github.com/ssenart/PyGazpar/compare/0.1.24...0.1.25
[0.1.24]: https://github.com/ssenart/PyGazpar/compare/0.1.23...0.1.24
[0.1.23]: https://github.com/ssenart/PyGazpar/compare/0.1.22...0.1.23
[0.1.22]: https://github.com/ssenart/PyGazpar/compare/0.1.21...0.1.22
[0.1.21]: https://github.com/ssenart/PyGazpar/compare/0.1.20...0.1.21
[0.1.20]: https://github.com/ssenart/PyGazpar/compare/0.1.19...0.1.20
[0.1.19]: https://github.com/ssenart/PyGazpar/compare/0.1.17...0.1.19
[0.1.18]: https://github.com/ssenart/PyGazpar/compare/0.1.17...0.1.18
[0.1.17]: https://github.com/ssenart/PyGazpar/compare/0.1.16...0.1.17
[0.1.16]: https://github.com/ssenart/PyGazpar/compare/0.1.15...0.1.16
[0.1.15]: https://github.com/ssenart/PyGazpar/compare/0.1.14...0.1.15
[0.1.14]: https://github.com/ssenart/PyGazpar/compare/0.1.13...0.1.14
[0.1.13]: https://github.com/ssenart/PyGazpar/compare/0.1.12...0.1.13
[0.1.12]: https://github.com/ssenart/PyGazpar/compare/0.1.11...0.1.12
[0.1.11]: https://github.com/ssenart/PyGazpar/compare/0.1.10...0.1.11
[0.1.10]: https://github.com/ssenart/PyGazpar/compare/0.1.9...0.1.10
[0.1.9]: https://github.com/ssenart/PyGazpar/compare/0.1.7...0.1.9
[0.1.8]: https://github.com/ssenart/PyGazpar/compare/0.1.7...0.1.8
[0.1.7]: https://github.com/ssenart/PyGazpar/compare/0.1.6...0.1.7
[0.1.6]: https://github.com/ssenart/PyGazpar/compare/0.1.5...0.1.6
