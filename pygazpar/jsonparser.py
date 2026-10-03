import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from pygazpar.enum import PropertyName

INPUT_DATE_FORMAT = "%Y-%m-%d"

OUTPUT_DATE_FORMAT = "%d/%m/%Y"

# Type of the rows derived from a published period or from a gap: volume, energy and indexes are calculated, not measured.
CALCULATED_TYPE = "Calculé"

Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class JsonParser:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    @staticmethod
    def parse(jsonStr: str, temperaturesStr: str, pceIdentifier: str) -> list[dict[str, Any]]:
        """Returns one row per day.

        Every GrDF record is a period: an informative record is one gas day, and a published record covers several days.
        A gap between two periods is rebuilt from the meter indexes.
        """

        res: list[dict[str, Any]] = []

        data = json.loads(jsonStr)

        temperatures = json.loads(temperaturesStr)

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        last_end = None
        last_index = None
        last_coefficient = None
        # Days without consumption wait for the next period: a gap rebuilt from the indexes covers them when it can.
        pending: list[tuple[date, date, dict[str, Any]]] = []
        for start, end, releve in JsonParser.__periods(data[pceIdentifier]["releves"]):
            if not JsonParser.__has_consumption(releve):
                pending.append((start, end, releve))
                continue

            gap = JsonParser.__gap(last_end, last_index, last_coefficient, start, releve)
            if gap is None:
                for no_data in pending:
                    res.extend(JsonParser.__no_data_rows(*no_data, temperatures, data_timestamp))
            else:
                res.extend(JsonParser.__spread(*gap, temperatures, data_timestamp))
            pending = []

            res.extend(JsonParser.__spread(start, end, releve, temperatures, data_timestamp))
            last_end, last_index, last_coefficient = end, releve.get("indexFin"), releve["coeffConversion"]

        for no_data in pending:
            res.extend(JsonParser.__no_data_rows(*no_data, temperatures, data_timestamp))

        Logger.debug("Daily data read successfully from Json")

        return res

    # ------------------------------------------------------
    @staticmethod
    def __periods(releves: list[dict[str, Any]]) -> list[tuple[date, date, dict[str, Any]]]:
        """Returns the periods as (first day, day after the last day, record), in chronological order."""

        periods = []
        for releve in releves:
            if releve.get("journeeGaziere") is not None:
                start = datetime.strptime(releve["journeeGaziere"], INPUT_DATE_FORMAT).date()
                periods.append((start, start + timedelta(days=1), releve))
            elif releve.get("dateDebutReleve") is None or releve.get("dateFinReleve") is None:
                Logger.warning("Reading ignored because it has no start or end date")
            else:
                start = datetime.fromisoformat(releve["dateDebutReleve"]).date()
                end = datetime.fromisoformat(releve["dateFinReleve"]).date()
                if end <= start:
                    Logger.warning("Published reading ignored because its period is empty")
                else:
                    periods.append((start, end, releve))

        return sorted(periods, key=lambda period: period[0])

    # ------------------------------------------------------
    @staticmethod
    def __has_consumption(releve: dict[str, Any]) -> bool:
        """Tells whether a record has its volume, energy and coefficient, as opposed to a day without data."""

        return all(releve.get(key) is not None for key in ("volumeBrutConsomme", "energieConsomme", "coeffConversion"))

    # ------------------------------------------------------
    @staticmethod
    def __gap(
        last_end: date | None,
        last_index: int | None,
        last_coefficient: float | None,
        start: date,
        releve: dict[str, Any],
    ) -> tuple[date, date, dict[str, Any]] | None:
        """Returns the period that fills the gap before a record, or None when there is no gap to fill.

        The gap starts where the previous period ends and ends where this record starts. Its volume is the difference of
        the meter indexes at both ends, and its energy is that volume times the average coefficient of both periods.
        Periods that do not chain by their indexes are reported, and nothing is filled.
        """

        if last_end is None:
            return None

        index_start = releve.get("indexDebut")

        if start == last_end:
            if last_index is not None and index_start is not None and last_index != index_start:
                Logger.warning(f"Periods do not chain: the index is {last_index} on {start}, then {index_start}")
            return None

        if start < last_end:
            Logger.warning(f"Periods overlap: a period ends on {last_end}, and the next starts on {start}")
            return None

        if last_index is None or index_start is None or index_start < last_index:
            Logger.warning(f"Periods do not chain: the gap from {last_end} to {start} cannot be rebuilt")
            return None

        volume = index_start - last_index
        coefficient = (last_coefficient + releve["coeffConversion"]) / 2
        Logger.warning(f"Periods do not chain: the gap from {last_end} to {start} is rebuilt ({volume} m3)")

        gap_record = {
            "journeeGaziere": None,
            "indexDebut": last_index,
            "indexFin": index_start,
            "volumeBrutConsomme": volume,
            "energieConsomme": round(volume * coefficient),
            "coeffConversion": coefficient,
            "temperature": None,
        }
        return last_end, start, gap_record

    # ------------------------------------------------------
    @staticmethod
    def __spread(
        start: date, end: date, releve: dict[str, Any], temperatures: Any, data_timestamp: str
    ) -> list[dict[str, Any]]:
        """Returns the rows of a period, from start (included) to end (excluded).

        A measured record of one day is returned as GrDF reports it. A derived period, which is a published period or a
        gap, is spread over its days: volume is split evenly, energy follows it in proportion, and indexes are
        interpolated. Each total is split in units of its own published precision, so the parts sum exactly to the
        totals. The temperature of each derived day comes from the meteo data.
        """

        if releve.get("journeeGaziere") is not None:
            return [JsonParser.__measured_row(start, releve, temperatures, data_timestamp)]

        (index_start, index_end), index_scale = JsonParser.__to_units(releve["indexDebut"], releve["indexFin"])
        (volume,), volume_scale = JsonParser.__to_units(releve["volumeBrutConsomme"])
        (energy,), energy_scale = JsonParser.__to_units(releve["energieConsomme"])

        days = (end - start).days
        volume_bounds = JsonParser.__bounds(0, volume, days)
        index_bounds = JsonParser.__bounds(index_start, index_end, days)

        # Volume is the reference: energy follows it, so each day gets the share of the energy that matches its share
        # of the volume. Without volume, energy is spread evenly over the days.
        if volume != 0:
            energy_bounds = [energy * bound // volume for bound in volume_bounds]
        else:
            energy_bounds = JsonParser.__bounds(0, energy, days)

        res = []
        for i in range(days):
            day = start + timedelta(days=i)

            item: dict[str, Any] = {}
            item[PropertyName.TIME_PERIOD.value] = day.strftime(OUTPUT_DATE_FORMAT)
            item[PropertyName.START_INDEX.value] = JsonParser.__to_output(Decimal(index_bounds[i]) / index_scale)
            item[PropertyName.END_INDEX.value] = JsonParser.__to_output(Decimal(index_bounds[i + 1]) / index_scale)
            item[PropertyName.VOLUME.value] = JsonParser.__to_output(
                Decimal(volume_bounds[i + 1] - volume_bounds[i]) / volume_scale
            )
            item[PropertyName.ENERGY.value] = JsonParser.__to_output(
                Decimal(energy_bounds[i + 1] - energy_bounds[i]) / energy_scale
            )
            item[PropertyName.CONVERTER_FACTOR.value] = releve["coeffConversion"]
            item[PropertyName.TEMPERATURE.value] = JsonParser.__meteo(temperatures, day)
            item[PropertyName.TYPE.value] = CALCULATED_TYPE
            item[PropertyName.TIMESTAMP.value] = data_timestamp

            res.append(item)

        return res

    # ------------------------------------------------------
    @staticmethod
    def __measured_row(day: date, releve: dict[str, Any], temperatures: Any, data_timestamp: str) -> dict[str, Any]:
        """Returns the row of a measured one-day record, with the values GrDF reports."""

        temperature = releve.get("temperature")

        item: dict[str, Any] = {}
        item[PropertyName.TIME_PERIOD.value] = day.strftime(OUTPUT_DATE_FORMAT)
        item[PropertyName.START_INDEX.value] = releve.get("indexDebut")
        item[PropertyName.END_INDEX.value] = releve.get("indexFin")
        item[PropertyName.VOLUME.value] = releve["volumeBrutConsomme"]
        item[PropertyName.ENERGY.value] = releve["energieConsomme"]
        item[PropertyName.CONVERTER_FACTOR.value] = releve["coeffConversion"]
        item[PropertyName.TEMPERATURE.value] = (
            temperature if temperature is not None else JsonParser.__meteo(temperatures, day)
        )
        item[PropertyName.TYPE.value] = releve["qualificationReleve"]
        item[PropertyName.TIMESTAMP.value] = data_timestamp

        return item

    # ------------------------------------------------------
    @staticmethod
    def __no_data_rows(
        start: date, end: date, releve: dict[str, Any], temperatures: Any, data_timestamp: str
    ) -> list[dict[str, Any]]:
        """Returns one row per day of a record without consumption, typed as GrDF qualifies it."""

        res = []
        for i in range((end - start).days):
            day = start + timedelta(days=i)

            item: dict[str, Any] = {}
            item[PropertyName.TIME_PERIOD.value] = day.strftime(OUTPUT_DATE_FORMAT)
            item[PropertyName.START_INDEX.value] = None
            item[PropertyName.END_INDEX.value] = None
            item[PropertyName.VOLUME.value] = None
            item[PropertyName.ENERGY.value] = None
            item[PropertyName.CONVERTER_FACTOR.value] = None
            item[PropertyName.TEMPERATURE.value] = JsonParser.__meteo(temperatures, day)
            item[PropertyName.TYPE.value] = releve.get("qualificationReleve")
            item[PropertyName.TIMESTAMP.value] = data_timestamp

            res.append(item)

        return res

    # ------------------------------------------------------
    @staticmethod
    def __meteo(temperatures: Any, day: date) -> Any:
        """Returns the meteo temperature of a day, or None when there is none."""

        return temperatures.get(day.strftime(INPUT_DATE_FORMAT)) if temperatures else None

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
