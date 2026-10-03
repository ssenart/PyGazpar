# TODO

## Published consumption: daily split

Published readings cover a period (`dateDebutReleve` to `dateFinReleve`). The first version spreads each period's volume evenly across its days, and its energy in proportion to the volume.

- [ ] Shape the daily split with the seasonal profile, so winter and summer days get different shares. Rows keep the type `Calculé`.
- [ ] Weight the daily split by temperature (degree-days) from the meteo data.
- [ ] Keep the sums of volume and energy equal to the published totals in every case. The split already does this, and the tests check it.

## Published consumption: gaps

- [ ] Some published periods do not chain: the index at the end of one period differs from the start of the next. In the sample, 3 October 2019 ends at index 9,996 and 3 November 2019 starts at 10,103, with no readings in between. Log a warning for such gaps. Monthly output drops any month with fewer than 28 days, so this month disappears.

## Sibling projects

- [ ] Check `gazpar2haws`, `home-assistant-gazpar`, `gazpar2mqtt` and `lovelace-gazpar-card` against the changes: the `Calculé` type, the published readings split by day, the CLI options and datasources, and the new `python-dotenv` runtime dependency.
- [ ] `gazpar2haws` pins pygazpar 1.3.1 from PyPI. Decide when it moves to this version.

## Naming

- [ ] Rename the legacy camelCase identifiers to snake_case. Public parameter names such as `pceIdentifier` need a deprecation path, because callers may pass them by keyword.
