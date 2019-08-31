# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/ssenart/PyGazpar/compare/0.1.9...HEAD
[0.1.9]: https://github.com/ssenart/PyGazpar/compare/0.1.7...0.1.9
[0.1.8]: https://github.com/ssenart/PyGazpar/compare/0.1.7...0.1.8
[0.1.7]: https://github.com/ssenart/PyGazpar/compare/0.1.6...0.1.7
[0.1.6]: https://github.com/ssenart/PyGazpar/compare/0.1.5...0.1.6
