# TODO

## Published consumption: daily split

Published readings cover a period (`dateDebutReleve` to `dateFinReleve`). The first version spreads each period's volume evenly across its days, and its energy in proportion to the volume.

- [ ] Shape the daily split with the seasonal profile, so winter and summer days get different shares. Rows keep the type `Calculé`.
- [ ] Weight the daily split by temperature (degree-days) from the meteo data.
- [x] Keep the sums of volume and energy equal to the published totals in every case. The split already does this, and the tests check it: keep it true when the split is shaped by a seasonal profile or by degree-days.

## Published consumption: gaps

- [x] Some published periods do not chain. The parser rebuilds each gap from the meter indexes: its volume is the index difference, and its energy is that volume times the average coefficient of the neighbouring periods. It logs a warning for each gap. In the sample, the gap of October 2019 is 107 m³ and 1,194 kWh.

## Sibling projects

- [x] `home-assistant-gazpar` (`util.py`, `sensor.py`) imports `Frequency` and `PropertyName` from `pygazpar.enum`. `pygazpar/enum.py` is kept as a compatibility re-export of `pygazpar.model`: do not delete it before the integration imports from `pygazpar` directly.
- [x] `gazpar2haws`, `gazpar2mqtt` and `home-assistant-gazpar` pin `pygazpar>=1.4.0a4`.
- [ ] Run the test suites of `gazpar2haws`, `home-assistant-gazpar` and `gazpar2mqtt` against this version (editable install). Their code was checked by reading only: the `Calculé` type, the published readings split by day, the CLI options and datasources, and the removed `loadSince()` and `loadDateRange()` (no sibling calls them).
- [ ] `gazpar2haws` (`gazpar.py`) passes `tmpDirectory=` to `ExcelWebDataSource`. Change it to `tmp_directory=` once 1.4.0 is published, and raise the pins to `>=1.4.0` in the same commit.

## Naming

- [x] Rename the legacy camelCase identifiers to snake_case (the `N` ruff rules enforce it). `ExcelWebDataSource(tmpDirectory=...)` still works with a `DeprecationWarning`: remove it in the next major version (2.0).

## Release

- [x] Version of the breaking changes: **1.4.0**. The last tag is 1.4.0a4, and the changes break 1.3.1 users: the removed `Client.loadSince()` and `Client.loadDateRange()`, the snake_case parameters and `compute_*` methods, and the GrDF model attributes. They are listed in the changelog.
- [ ] Release 1.4.0 with the `create-release` workflow (it bumps `pyproject.toml`, finalizes the changelog, tags and publishes to PyPI: do not bump by hand). A final version is accepted on `master` only, so merge `develop` into `master` first, or go through a `1.4.0rc1` on a `release/1.4.0` branch. Run it as a dry run first. Then move the sibling pins to `>=1.4.0` (see the Sibling projects section).
- [ ] Remove the deprecated `tmpDirectory` keyword of `ExcelWebDataSource` in the next major version (2.0).
