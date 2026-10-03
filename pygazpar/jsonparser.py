import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from pygazpar.grdf import (
    GrdfConsumptionResponse,
    GrdfMeteoResponse,
    GrdfPceConsumption,
    GrdfRecord,
)
from pygazpar.model import DailyReading, Frequency, PropertyName

INPUT_DATE_FORMAT = "%Y-%m-%d"

# Type of the rows derived from a published period or from a gap: volume, energy and indexes are calculated, not measured.
CALCULATED_TYPE = "Calculé"

Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class JsonParser:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    @staticmethod
    def parse(jsonStr: str, temperaturesStr: str, pceIdentifier: str) -> list[dict[str, Any]]:
        """Returns one row per day, as dicts. See readings_from_json() for the models."""

        return [
            reading.model_dump(by_alias=True)
            for reading in JsonParser.readings_from_json(jsonStr, temperaturesStr, pceIdentifier)
        ]

    # ------------------------------------------------------
    @staticmethod
    def readings_from_json(jsonStr: str, temperaturesStr: str, pceIdentifier: str) -> list[DailyReading]:
        """Returns one reading per day, from the JSON of the consumption and of the temperatures."""

        # Decimal numbers are read from the JSON text, so that the splits of volumes and energies stay exact.
        consumption = JsonParser.__consumption_of(json.loads(jsonStr, parse_float=Decimal))
        temperatures = JsonParser.__temperatures_of(json.loads(temperaturesStr))

        return JsonParser.readings(consumption, temperatures, pceIdentifier)

    # ------------------------------------------------------
    @staticmethod
    def __consumption_of(data: Any) -> dict[str, GrdfPceConsumption]:
        """Returns the consumption of a JSON document, empty when GrDF sends an empty list."""

        if type(data) is list and len(data) == 0:
            return {}

        return GrdfConsumptionResponse.model_validate(data).root

    # ------------------------------------------------------
    @staticmethod
    def __temperatures_of(data: Any) -> dict[date, float | None] | None:
        """Returns the temperatures of a JSON document, or None when there are none."""

        if data is None or (type(data) is list and len(data) == 0):
            return None

        return GrdfMeteoResponse.model_validate(data).root

    # ------------------------------------------------------
    @staticmethod
    def readings(
        consumption_by_pce: dict[str, GrdfPceConsumption],
        temperatures: dict[date, float | None] | None,
        pceIdentifier: str,
    ) -> list[DailyReading]:
        """Returns one reading per day.

        Every GrDF record is a period: an informative record is one gas day, and a published record covers several days.
        A gap between two periods, and a day without data between two known indexes, is rebuilt from the meter indexes.
        """

        res: list[DailyReading] = []

        if pceIdentifier not in consumption_by_pce:
            return res

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        last_end: date | None = None
        last_index: Decimal | None = None
        last_coefficient: Decimal | None = None
        # Days without consumption wait for the next period: a gap rebuilt from the indexes covers them when it can.
        pending: list[tuple[date, date, GrdfRecord]] = []
        for start, end, record in JsonParser.__periods(
            JsonParser.__validated(consumption_by_pce[pceIdentifier].releves)
        ):
            consumption = JsonParser.__consumption(record)
            if consumption is None:
                pending.append((start, end, record))
                continue
            volume, energy, coefficient = consumption

            gap = JsonParser.__gap(last_end, last_index, last_coefficient, start, record.indexDebut, coefficient)
            if gap is None:
                for no_data in pending:
                    res.extend(JsonParser.__no_data_rows(*no_data, temperatures, data_timestamp))
            else:
                res.extend(JsonParser.__spread_derived(*gap, temperatures, data_timestamp))
            pending = []

            if record.journeeGaziere is not None:
                res.append(JsonParser.__measured_row(start, record, coefficient, temperatures, data_timestamp))
            else:
                res.extend(
                    JsonParser.__spread_derived(
                        start,
                        end,
                        record.indexDebut,
                        record.indexFin,
                        volume,
                        energy,
                        coefficient,
                        temperatures,
                        data_timestamp,
                    )
                )
            last_end, last_index, last_coefficient = end, record.indexFin, coefficient

        for no_data in pending:
            res.extend(JsonParser.__no_data_rows(*no_data, temperatures, data_timestamp))

        Logger.debug("Daily data read successfully from Json")

        return res

    # ------------------------------------------------------
    @staticmethod
    def __validated(releves: list[dict[str, Any]]) -> list[GrdfRecord]:
        """Returns the records that are valid. An invalid record is reported and ignored."""

        records = []
        for releve in releves:
            try:
                records.append(GrdfRecord.model_validate(releve))
            except ValidationError as error:
                Logger.warning(f"Reading ignored because it is invalid: {error.errors()[0]['msg']}")

        return records

    # ------------------------------------------------------
    @staticmethod
    def __periods(records: list[GrdfRecord]) -> list[tuple[date, date, GrdfRecord]]:
        """Returns the periods as (first day, day after the last day, record), in chronological order."""

        periods = []
        for record in records:
            if record.journeeGaziere is not None:
                periods.append((record.journeeGaziere, record.journeeGaziere + timedelta(days=1), record))
            elif record.dateDebutReleve is None or record.dateFinReleve is None:
                Logger.warning("Reading ignored because it has no start or end date")
            else:
                periods.append((record.dateDebutReleve.date(), record.dateFinReleve.date(), record))

        return sorted(periods, key=lambda period: period[0])

    # ------------------------------------------------------
    @staticmethod
    def __consumption(record: GrdfRecord) -> tuple[Decimal, Decimal, Decimal] | None:
        """Returns the volume, energy and coefficient of a record, or None for a day without consumption."""

        if record.volumeBrutConsomme is None or record.energieConsomme is None or record.coeffConversion is None:
            return None

        return record.volumeBrutConsomme, record.energieConsomme, record.coeffConversion

    # ------------------------------------------------------
    @staticmethod
    def __gap(
        last_end: date | None,
        last_index: Decimal | None,
        last_coefficient: Decimal | None,
        start: date,
        index_start: Decimal | None,
        coefficient: Decimal,
    ) -> tuple[date, date, Decimal, Decimal, Decimal, Decimal, Decimal] | None:
        """Returns the derived period that fills the gap before a record, or None when there is no gap to fill.

        The gap starts where the previous period ends and ends where this record starts. Its volume is the difference of
        the meter indexes at both ends, and its energy is that volume times the average coefficient of both periods.
        Periods that do not chain by their indexes are reported, and nothing is filled.
        """

        if last_end is None:
            return None

        if start == last_end:
            if last_index is not None and index_start is not None and last_index != index_start:
                Logger.warning(f"Periods do not chain: the index is {last_index} on {start}, then {index_start}")
            return None

        if start < last_end:
            Logger.warning(f"Periods overlap: a period ends on {last_end}, and the next starts on {start}")
            return None

        if last_index is None or last_coefficient is None or index_start is None or index_start < last_index:
            Logger.warning(f"Periods do not chain: the gap from {last_end} to {start} cannot be rebuilt")
            return None

        volume = index_start - last_index
        gap_coefficient = (last_coefficient + coefficient) / 2
        Logger.warning(f"Periods do not chain: the gap from {last_end} to {start} is rebuilt ({volume} m3)")

        energy = Decimal(round(volume * gap_coefficient))
        return last_end, start, last_index, index_start, volume, energy, gap_coefficient

    # ------------------------------------------------------
    @staticmethod
    def __spread_derived(
        start: date,
        end: date,
        index_start: Decimal | None,
        index_end: Decimal | None,
        volume: Decimal,
        energy: Decimal,
        coefficient: Decimal,
        temperatures: Any,
        data_timestamp: str,
    ) -> list[DailyReading]:
        """Returns the rows of a derived period, from start (included) to end (excluded).

        Volume is split evenly, energy follows it in proportion, and indexes are interpolated. Each total is split in
        units of its own published precision, so the parts sum exactly to the totals. The temperature of each day comes
        from the meteo data.
        """

        (start_units, end_units), index_scale = JsonParser.__to_units(index_start, index_end)
        (volume_units,), volume_scale = JsonParser.__to_units(volume)
        (energy_units,), energy_scale = JsonParser.__to_units(energy)

        days = (end - start).days
        volume_bounds = JsonParser.__bounds(0, volume_units, days)
        index_bounds = JsonParser.__bounds(start_units, end_units, days)

        # Volume is the reference: energy follows it, so each day gets the share of the energy that matches its share
        # of the volume. Without volume, energy is spread evenly over the days.
        if volume_units != 0:
            energy_bounds = [energy_units * bound // volume_units for bound in volume_bounds]
        else:
            energy_bounds = JsonParser.__bounds(0, energy_units, days)

        res = []
        for i in range(days):
            day = start + timedelta(days=i)
            row = DailyReading.model_validate(
                {
                    PropertyName.START_DATE.value: day,
                    PropertyName.END_DATE.value: day + timedelta(days=1),
                    PropertyName.FREQUENCY.value: Frequency.DAILY,
                    PropertyName.START_INDEX.value: JsonParser.__to_output(Decimal(index_bounds[i]) / index_scale),
                    PropertyName.END_INDEX.value: JsonParser.__to_output(Decimal(index_bounds[i + 1]) / index_scale),
                    PropertyName.VOLUME.value: JsonParser.__to_output(
                        Decimal(volume_bounds[i + 1] - volume_bounds[i]) / volume_scale
                    ),
                    PropertyName.ENERGY.value: JsonParser.__to_output(
                        Decimal(energy_bounds[i + 1] - energy_bounds[i]) / energy_scale
                    ),
                    PropertyName.CONVERTER_FACTOR.value: float(coefficient),
                    PropertyName.TEMPERATURE.value: JsonParser.__meteo_of(temperatures, day),
                    PropertyName.TYPE.value: CALCULATED_TYPE,
                    PropertyName.TIMESTAMP.value: data_timestamp,
                }
            )
            res.append(row)

        return res

    # ------------------------------------------------------
    @staticmethod
    def __measured_row(
        start: date, record: GrdfRecord, coefficient: Decimal, temperatures: Any, data_timestamp: str
    ) -> DailyReading:
        """Returns the row of a measured one-day record, with the values GrDF reports."""

        temperature = record.temperature
        row = DailyReading.model_validate(
            {
                PropertyName.START_DATE.value: start,
                PropertyName.END_DATE.value: start + timedelta(days=1),
                PropertyName.FREQUENCY.value: Frequency.DAILY,
                PropertyName.START_INDEX.value: JsonParser.__to_output(record.indexDebut),
                PropertyName.END_INDEX.value: JsonParser.__to_output(record.indexFin),
                PropertyName.VOLUME.value: JsonParser.__to_output(record.volumeBrutConsomme),
                PropertyName.ENERGY.value: JsonParser.__to_output(record.energieConsomme),
                PropertyName.CONVERTER_FACTOR.value: float(coefficient),
                PropertyName.TEMPERATURE.value: (
                    float(temperature) if temperature is not None else JsonParser.__meteo_of(temperatures, start)
                ),
                PropertyName.TYPE.value: record.qualificationReleve,
                PropertyName.TIMESTAMP.value: data_timestamp,
            }
        )

        return row

    # ------------------------------------------------------
    @staticmethod
    def __no_data_rows(
        start: date, end: date, record: GrdfRecord, temperatures: Any, data_timestamp: str
    ) -> list[DailyReading]:
        """Returns one row per day of a record without consumption, typed as GrDF qualifies it."""

        res = []
        for i in range((end - start).days):
            day = start + timedelta(days=i)
            row = DailyReading.model_validate(
                {
                    PropertyName.START_DATE.value: day,
                    PropertyName.END_DATE.value: day + timedelta(days=1),
                    PropertyName.FREQUENCY.value: Frequency.DAILY,
                    PropertyName.START_INDEX.value: None,
                    PropertyName.END_INDEX.value: None,
                    PropertyName.VOLUME.value: None,
                    PropertyName.ENERGY.value: None,
                    PropertyName.CONVERTER_FACTOR.value: None,
                    PropertyName.TEMPERATURE.value: JsonParser.__meteo_of(temperatures, day),
                    PropertyName.TYPE.value: record.qualificationReleve,
                    PropertyName.TIMESTAMP.value: data_timestamp,
                }
            )
            res.append(row)

        return res

    # ------------------------------------------------------
    @staticmethod
    def __meteo_of(temperatures: dict[date, float | None] | None, day: date) -> float | None:
        """Returns the meteo temperature of a day, or None when there is none."""

        return temperatures.get(day) if temperatures else None

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
    def __to_output(value: Decimal | None) -> int | float | None:
        """Keeps whole numbers as int, and returns other values as float, at their published precision."""

        if value is None:
            return None

        return int(value) if value == value.to_integral_value() else float(value)
