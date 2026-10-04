# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Python 3.14 is tested in CI and listed as a supported version.
- Development dependencies: black `^26.3.1`, pytest `^9.0.3` and pytest-asyncio `^1.4.0`.

### Security

- Locked `urllib3` to 2.8.0, `requests` to 2.34.2, `idna` to 3.20 and `python-dotenv` to 1.2.4 to fix open Dependabot alerts.

## [1.4.0a3] - 2026-10-04

### Changed

- Release process: the create-release workflow takes an explicit version, and checks it against the branch, the existing tags and the changelog before anything is changed.
- Release process: the changelog is finalized automatically: `[Unreleased]` becomes the released version, a new empty `[Unreleased]` is added above it, and the compare links are updated.
- Release process: GitHub releases are created as drafts by default, with the changelog section as their notes. A dry run option builds and validates a release without publishing it.
- Release process: the version bump commit and the tag are pushed together, and only after the package is published.
- Release process: final versions are released from `master`, alphas from `develop`, and betas and release candidates from `release/*`. Feature branches publish to TestPyPI.

### Removed

- GitVersion, its configuration and the version step in CI.

## [1.4.0a2] - 2026-10-03

### Added

- CLI reads `GRDF_USERNAME`, `GRDF_PASSWORD` and `PCE_IDENTIFIER` from the environment or a `.env` file when the credentials are not given on the command line. `python-dotenv` is now a runtime dependency.
- CLI `--consumption-type` option (`INFORMATIVE` or `PUBLISHED`) for the `json` and `raw-consumption` datasources.
- CLI `raw-consumption` and `raw-temperature` datasources printing the GrDF API responses without post processing.
- `RawConsumptionWebDataSource` and `RawTemperatureWebDataSource` in the library, returning the GrDF API responses as received.
- Log a warning when published periods do not chain, and rebuild the gap from the meter indexes.
- Gaps between published periods are rebuilt from the meter indexes: the volume is the index difference, and the energy uses the average coefficient of the neighbouring periods. The rows have the type `Calculé`.
- Informative days without data are rebuilt from the meter indexes when the indexes on both sides are known.
- Every reading shows its `frequency`, `start_date` and `end_date`.
- Data model in `pygazpar.model` (`PeriodReading`, `DailyReading`, `Frequency`, `PropertyName`) and GrDF records and responses in `pygazpar.grdf`, validated as they are read.
- `Client.load_readings_since` and `Client.load_readings_date_range` return the readings as models. `load_since` and `load_date_range` keep the dict form.

### Changed

- Published readings are split into one row per day instead of one row on the last day of their period. Volume is spread evenly across the days and energy follows it in proportion, keeping the published totals exact. Indexes are interpolated, and the rows have the type `Calculé`.
- Informative records and published periods share one parsing path: each record is a period.
- Weekly, monthly and yearly rows, and the Excel and test datasources, are built from the same models as the daily rows.
- Excel rows are read into the models: a period without data gets empty values, and the dates come from the labels.
- The API client validates each response as it arrives, and returns models: the PCE list, the consumption of each PCE, the temperatures and the Excel sheet. The raw sources use the `*_raw` methods, which return the response as received.
- `--datasource` only accepts the listed datasources. Any other value is a usage error.
- `pygazpar.enum` re-exports `Frequency` and `PropertyName`, which are now defined in `pygazpar.model`.

### Fixed

- Weekly rows follow the calendar: the week of 30 December 2019 to 5 January 2020 is its own week. Before, its first days were merged into the following week's label and totals.
- Empty buckets give `null` values instead of `NaN`, which is not valid JSON.
- A password with a double quote, a backslash, a tab or a non-ASCII character no longer breaks the login. The login requests are now built with `json.dumps`, so the password is sent as typed.

### Breaking changes

Compared with 1.3.1:

- Rows carry the full set of keys, with `null` for the values a source does not give. The Excel and test datasource rows now have `temperature_degC`, `converter_factor_kwh/m3` and `type` keys, and the period rows have the index keys. Code that tests whether a key is present must change.
- Output rows gain `frequency`, `start_date` and `end_date`. Code that checks the exact set of keys must accept them. The order of the keys changed.
- Weekly values change around the new year, because of the fix above. The sample has 156 weekly rows instead of 155.
- Published readings are returned one row per day, with the type `Calculé`, instead of one row per period. Row counts for published data change.
- `APIClient` methods return models instead of dicts and lists: `get_pce_list` returns `GrdfPce` objects, `get_pce_consumption` returns `GrdfPceConsumption` objects keyed by PCE identifier, `get_pce_meteo` returns a dict keyed by date, and `get_pce_consumption_excelsheet` returns a `GrdfExcelSheet`.
- A malformed API response raises a pydantic `ValidationError`, where it used to raise `TypeError`.
- `FrequencyConverter` functions and `ExcelParser.parse` take and return models instead of dicts.
- An invalid GrDF record is skipped with a warning.
- `pydantic` is a new runtime dependency, and `typing-extensions` is bumped to 4.16.0.
- A custom `IDataSource` implements `readings()`, which returns models, instead of `load()`. `load()` is now the dict form, provided by the base class.
- The CLI refuses an unknown `--datasource` with a usage error (exit code 2), where it used to raise a `ValueError`.
- Loading readings for a PCE that is not in the account raises `UnknownPceError`, a `ServerError`, where it used to return no data. The identifier is checked against the PCE list of the account, so a PCE of the account with no data still returns no readings. The raw sources and `APIClient` are unchanged.

## [1.4.0a1] - 2026-07-27

### Added

- Support explicitly requesting published GRDF consumption readings.

### Fixed

- Parse published readings whose `journeeGaziere` field is empty by using the last day of their reporting period.

## [1.3.1] - 2025-07-22

### Fixed

[#88](https://github.com/ssenart/PyGazpar/issues/88) : 500 - NGINX / OpenID Connect login failure.

## [1.3.0] - 2025-02-15

### Added

[#84](https://github.com/ssenart/PyGazpar/issues/84) : Add a function to retrieve list of PCE ids.

### Changed

[#85](https://github.com/ssenart/PyGazpar/issues/85) : Move to Poetry dependency/package management tool.

## [1.2.8](https://github.com/ssenart/PyGazpar/compare/1.2.8...1.2.7) - 2025-01-11

### Added
- [#81](https://github.com/ssenart/PyGazpar/issues/81): Add meter/temperature debug log messages to help investigation in case of errors.

## [1.2.7](https://github.com/ssenart/PyGazpar/compare/1.2.7...1.2.6) - 2025-01-06

### Fixed
- [#79](https://github.com/ssenart/PyGazpar/issues/79): Fix some unittests that wrongly failed because of the new year.

## [1.2.6](https://github.com/ssenart/PyGazpar/compare/1.2.6...1.2.5) - 2025-01-03

### Fixed
- [#77](https://github.com/ssenart/PyGazpar/issues/77): Some error may occur while requesting data from GrDF API.

## [1.2.5](https://github.com/ssenart/PyGazpar/compare/1.2.5...1.2.4) - 2024-12-21

### Fixed
- [#75](https://github.com/ssenart/PyGazpar/issues/75): Fix an error when no temperature data is available.

## [1.2.4](https://github.com/ssenart/PyGazpar/compare/1.2.4...1.2.3) - 2024-10-09

### Fixed
- [#72](https://github.com/ssenart/PyGazpar/issues/72): Remove the warning message "UserWarning: Boolean Series key will be reindexed to match DataFrame index. df = pd.concat([df[(df["count"] >= 7)], df.tail(1)[df["count"] < 7]])".

## [1.2.3](https://github.com/ssenart/PyGazpar/compare/1.2.3...1.2.1) - 2024-10-05

### Added
- [#70](https://github.com/ssenart/PyGazpar/issues/70): Add Python 3.12 support.

## [1.2.2](https://github.com/ssenart/PyGazpar/compare/1.2.1...1.2.2) - 2024-05-08

### Fixed
- [#65](https://github.com/ssenart/PyGazpar/issues/65): [Bug] PermissionError happens when loading data from Excel file.

## [1.2.1](https://github.com/ssenart/PyGazpar/compare/1.2.0...1.2.1) - 2024-05-04

### Fixed
- [#64](https://github.com/ssenart/PyGazpar/issues/64): [Issue] Captcha failed issue.

- [#63](https://github.com/ssenart/PyGazpar/issues/63): [Bug] If the latest received consumption is Sunday, then the last weekly period is duplicated.

## [1.2.0](https://github.com/ssenart/PyGazpar/compare/1.1.6...1.2.0) - 2022-12-16

### Changed
- [#59](https://github.com/ssenart/PyGazpar/issues/59): [Feature] Support both Excel and Json data source format from GrDF site.

- [#60](https://github.com/ssenart/PyGazpar/issues/60): [Feature] Permit to load data at multiple frequencies with one method call.

### Fixed
- [#47](https://github.com/ssenart/PyGazpar/issues/47): [Bug] No temperature field available.

- [#58](https://github.com/ssenart/PyGazpar/issues/58): [Issue] No data update - GrDF web site is half broken - Download button does not work anymore.

## [1.1.6](https://github.com/ssenart/PyGazpar/compare/1.1.5...1.1.6) - 2022-11-16
### Fixed
- [#55](https://github.com/ssenart/PyGazpar/issues/55): Problème de connexion.

## [1.1.5](https://github.com/ssenart/PyGazpar/compare/1.1.4...1.1.5) - 2022-07-11
### Fixed
- [#49](https://github.com/ssenart/PyGazpar/issues/49): Authentication failure.

## [1.1.4](https://github.com/ssenart/PyGazpar/compare/1.1.2...1.1.4) - 2022-01-18
### Changed
- [#43](https://github.com/ssenart/PyGazpar/issues/43): Downloaded Excel file name has changed from Donnees_informatives_PCE_$dateDebut_$dateFin.xlsx to Donnees_informatives_$numeroPCE_$dateDebut_$dateFin.xlsx.

## [1.1.2](https://github.com/ssenart/PyGazpar/compare/1.1.1...1.1.2) - 2022-01-08
### Fixed
- [#39](https://github.com/ssenart/PyGazpar/issues/39): NameError: name 'Frequency' is not defined (thanks [nicolas-r](https://github.com/nicolas-r)).
- Numéro PCE pas forcément un nombre: Le numéro PCE de mon compteur commence par un 0 et lorsque j'essaie de récupérer mes relevés avec PyGazpar, une erreur de l'API est renvoyée. Le numéro PCE ne doit donc pas être converti en int lorsque il est passé en paramètre mais doit être une string (thanks  [maelgangloff](https://github.com/maelgangloff)).

## [1.1.1](https://github.com/ssenart/PyGazpar/compare/1.1.0...1.1.1) - 2021-12-02
### Changed
- Exact same version as 1.1.0 except that 1.1.0 has not been published on Pypi repository.

## [1.1.0](https://github.com/ssenart/PyGazpar/compare/1.0.2...1.1.0) - 2021-12-02
### Changed
- Remove Selenium usage and use simple Web request for login and data retrieval.

## [1.0.2](https://github.com/ssenart/PyGazpar/compare/1.0.1...1.0.2) - 2021-11-25
### Fixed
- Fix broken command line pygazpar caused by adding the new lastNDays parameter.
- Fix the error : ValueError: could not convert string to float: 'Index de début de période (m3)'. It occurs because the records in the Excel file now starts at line 10 instead of line 8 before (thanks to [DEFAYArnaud](https://github.com/DEFAYArnaud) for having spotted the issue and bringing the fix).

### Changed
- In the Excel file, if a cell is empty, then no corresponding key will be inserted in the result dictionary (before we inserted a key with an empty string).

## [1.0.1](https://github.com/ssenart/PyGazpar/compare/1.0.0...1.0.1) - 2021-11-24
### Fixed
- Fix typo warning from Pylance preventing 1.0.0 to be published.

## [1.0.0](https://github.com/ssenart/PyGazpar/compare/0.2.0...1.0.0) - 2021-11-24
### Added
- New lastNDays parameter to query data only over the last N days period.

### Fixed
- [#18](https://github.com/ssenart/PyGazpar/issues/18): PyGazpar broken since GRDF Monespace has been upgraded to a new version.

## [0.2.0](https://github.com/ssenart/PyGazpar/compare/0.1.27...0.2.0) - 2021-04-21
### Added
- [#12](https://github.com/ssenart/PyGazpar/issues/10): Be able to retrieve consumption not only on a daily basis, but weekly and monthly:
    - API : Add a new parameter 'meterReadingFrequency' to Client that accepts enumeration: Frequency.DAILY, Frequency.WEEKLY or Frequency.MONTHLY.
    - Command line : Add a new argument '--frequency' that accepts values : DAILY, WEEKLY or MONTHLY.
- Be able to test using offline data :
    - API : Add a new parameter 'testMode' to Clients used to specify whether we want to get some live data (testMode=False) and static testing data (testMode=True).
    - Command line : Add a new argument '--testMode' (True if specified and False by default).

### Changed
- Some ouput energy property names have changed:
    - 'date' => 'time_period'.
    - 'converter_factor' => 'converter_factor_kwh/m3'.
    - 'local_temperature' => 'temperature_degC'.

## [0.1.27](https://github.com/ssenart/PyGazpar/compare/0.1.26...0.1.27) - 2021-04-20
### Fixed
- [#10](https://github.com/ssenart/PyGazpar/issues/10) : Does not download data file in tmpdir as expected (instead it is downloaded in the default user Download directory). The previous attempt in version 0.1.26 is a failure. The origin of the bug is that we send a relative tmp directory path to Webdriver. Additionally, this path has to be normalized to the runtime OS (using slash or backslash).

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

[Unreleased]: https://github.com/ssenart/PyGazpar/compare/1.4.0a3...HEAD
[1.4.0a3]: https://github.com/ssenart/PyGazpar/compare/1.4.0a2...1.4.0a3
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
