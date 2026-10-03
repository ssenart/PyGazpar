# TODO

## Published consumption: daily split

Published readings cover a period (`dateDebutReleve` to `dateFinReleve`). The first version spreads each period's volume evenly across its days, and its energy in proportion to the volume.

- [ ] Shape the daily split with the seasonal profile, so winter and summer days get different shares. Rows keep the type `Calculé`.
- [ ] Weight the daily split by temperature (degree-days) from the meteo data.
- [ ] Keep the sums of volume and energy equal to the published totals in every case. The split already does this, and the tests check it.

## Published consumption: gaps

- [x] Some published periods do not chain. The parser rebuilds each gap from the meter indexes: its volume is the index difference, and its energy is that volume times the average coefficient of the neighbouring periods. It logs a warning for each gap. In the sample, the gap of October 2019 is 107 m³ and 1,194 kWh.

## Sibling projects

- [ ] Check `gazpar2haws`, `home-assistant-gazpar`, `gazpar2mqtt` and `lovelace-gazpar-card` against the changes: the `Calculé` type, the published readings split by day, the CLI options and datasources, and the new `python-dotenv` runtime dependency.
- [ ] `gazpar2haws` pins pygazpar 1.3.1 from PyPI. Decide when it moves to this version.

## Naming

- [ ] Rename the legacy camelCase identifiers to snake_case. Public parameter names such as `pceIdentifier` need a deprecation path, because callers may pass them by keyword.
