import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from pygazpar.enum import PropertyName

INPUT_DATE_FORMAT = "%Y-%m-%d"

OUTPUT_DATE_FORMAT = "%d/%m/%Y"

# Type of the daily rows derived from a published period: volume, energy and indexes are calculated, not measured.
CALCULATED_TYPE = "Calculé"

Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class JsonParser:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    @staticmethod
    def parse(jsonStr: str, temperaturesStr: str, pceIdentifier: str) -> list[dict[str, Any]]:

        res = []

        data = json.loads(jsonStr)

        temperatures = json.loads(temperaturesStr)

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        for releve in data[pceIdentifier]["releves"]:
            if releve["journeeGaziere"] is None:
                # Published reading: a period that is spread over its days.
                res.extend(JsonParser.__spread_period(releve, temperatures, data_timestamp))
                continue

            reading_date = releve["journeeGaziere"]

            temperature = releve["temperature"]
            if temperature is None and temperatures is not None and len(temperatures) > 0:
                temperature = temperatures.get(reading_date)

            item: dict[str, Any] = {}
            item[PropertyName.TIME_PERIOD.value] = datetime.strftime(
                datetime.strptime(reading_date, INPUT_DATE_FORMAT), OUTPUT_DATE_FORMAT
            )
            item[PropertyName.START_INDEX.value] = releve["indexDebut"]
            item[PropertyName.END_INDEX.value] = releve["indexFin"]
            item[PropertyName.VOLUME.value] = releve["volumeBrutConsomme"]
            item[PropertyName.ENERGY.value] = releve["energieConsomme"]
            item[PropertyName.CONVERTER_FACTOR.value] = releve["coeffConversion"]
            item[PropertyName.TEMPERATURE.value] = temperature
            item[PropertyName.TYPE.value] = releve["qualificationReleve"]
            item[PropertyName.TIMESTAMP.value] = data_timestamp

            res.append(item)

        Logger.debug("Daily data read successfully from Json")

        return res

    # ------------------------------------------------------
    @staticmethod
    def __spread_period(releve: dict[str, Any], temperatures: Any, data_timestamp: str) -> list[dict[str, Any]]:
        """Spreads a published reading over the days of its period.

        The period starts at dateDebutReleve and ends (excluded) at dateFinReleve. Volume is split evenly, and energy
        follows it in proportion. Each total is split in units of its own published precision, so the parts sum exactly
        to the published totals. Indexes are interpolated between the published start and end indexes. The temperature
        of each day comes from the meteo data.
        """

        start_date = releve.get("dateDebutReleve")
        end_date = releve.get("dateFinReleve")
        if start_date is None or end_date is None:
            Logger.warning("Published reading ignored because it has no start or end date")
            return []

        first_day = datetime.fromisoformat(start_date).date()
        days = (datetime.fromisoformat(end_date).date() - first_day).days
        if days <= 0:
            Logger.warning("Published reading ignored because its period is empty")
            return []

        (index_start, index_end), index_scale = JsonParser.__to_units(releve["indexDebut"], releve["indexFin"])
        (volume,), volume_scale = JsonParser.__to_units(releve["volumeBrutConsomme"])
        (energy,), energy_scale = JsonParser.__to_units(releve["energieConsomme"])

        volume_bounds = JsonParser.__bounds(0, volume, days)
        index_bounds = JsonParser.__bounds(index_start, index_end, days)

        # Volume is the reference: energy follows it, so each day gets the share of the published energy that
        # matches its share of the published volume. Without volume, energy is spread evenly over the days.
        if volume != 0:
            energy_bounds = [energy * bound // volume for bound in volume_bounds]
        else:
            energy_bounds = JsonParser.__bounds(0, energy, days)

        res = []
        for i in range(days):
            day = (first_day + timedelta(days=i)).strftime(INPUT_DATE_FORMAT)

            item: dict[str, Any] = {}
            item[PropertyName.TIME_PERIOD.value] = datetime.strftime(
                datetime.strptime(day, INPUT_DATE_FORMAT), OUTPUT_DATE_FORMAT
            )
            item[PropertyName.START_INDEX.value] = JsonParser.__to_output(Decimal(index_bounds[i]) / index_scale)
            item[PropertyName.END_INDEX.value] = JsonParser.__to_output(Decimal(index_bounds[i + 1]) / index_scale)
            item[PropertyName.VOLUME.value] = JsonParser.__to_output(
                Decimal(volume_bounds[i + 1] - volume_bounds[i]) / volume_scale
            )
            item[PropertyName.ENERGY.value] = JsonParser.__to_output(
                Decimal(energy_bounds[i + 1] - energy_bounds[i]) / energy_scale
            )
            item[PropertyName.CONVERTER_FACTOR.value] = releve["coeffConversion"]
            item[PropertyName.TEMPERATURE.value] = temperatures.get(day) if temperatures else None
            item[PropertyName.TYPE.value] = CALCULATED_TYPE
            item[PropertyName.TIMESTAMP.value] = data_timestamp

            res.append(item)

        return res

    # ------------------------------------------------------
    @staticmethod
    def __bounds(start: int, end: int, days: int) -> list[int]:
        """Returns days + 1 bounds from start to end, so that consecutive differences sum exactly to end - start."""

        return [start + (end - start) * i // days for i in range(days + 1)]

    # ------------------------------------------------------
    @staticmethod
    def __to_units(*values: Any) -> tuple[list[int], int]:
        """Returns the values as whole units of their most precise decimal place, and the number of units per unit."""

        decimals = [Decimal(str(value)) for value in values]
        digits = max(max(0, -int(decimal.as_tuple().exponent)) for decimal in decimals)

        return [int(decimal.scaleb(digits)) for decimal in decimals], 10**digits

    # ------------------------------------------------------
    @staticmethod
    def __to_output(value: Decimal) -> int | float:
        """Keeps whole numbers as int, and returns other values as float, at their published precision."""

        return int(value) if value == value.to_integral_value() else float(value)
