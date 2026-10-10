"""The data model of PyGazpar: the readings that users get, for any frequency.

A reading covers a period: a day, a week, a month or a year. Its dates and frequency validate the period, and its
time_period label is computed from them. The keys of the dict form are the values of PropertyName, which is defined in this module.
"""

import re
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

# The names of the keys of the dict form. PropertyName and the model fields both use them.
TIME_PERIOD_KEY: Final = "time_period"
FREQUENCY_KEY: Final = "frequency"
START_DATE_KEY: Final = "start_date"
END_DATE_KEY: Final = "end_date"
START_INDEX_KEY: Final = "start_index_m3"
END_INDEX_KEY: Final = "end_index_m3"
VOLUME_KEY: Final = "volume_m3"
ENERGY_KEY: Final = "energy_kwh"
CONVERTER_FACTOR_KEY: Final = "converter_factor_kwh/m3"
TEMPERATURE_KEY: Final = "temperature_degC"
TYPE_KEY: Final = "type"
TIMESTAMP_KEY: Final = "timestamp"


# ------------------------------------------------------------------------------------------------------------
class PropertyName(Enum):
    TIME_PERIOD = TIME_PERIOD_KEY
    FREQUENCY = FREQUENCY_KEY
    START_DATE = START_DATE_KEY
    END_DATE = END_DATE_KEY
    START_INDEX = START_INDEX_KEY
    END_INDEX = END_INDEX_KEY
    VOLUME = VOLUME_KEY
    ENERGY = ENERGY_KEY
    CONVERTER_FACTOR = CONVERTER_FACTOR_KEY
    TEMPERATURE = TEMPERATURE_KEY
    TYPE = TYPE_KEY
    TIMESTAMP = TIMESTAMP_KEY

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.__str__()


# ------------------------------------------------------------------------------------------------------------
class Frequency(str, Enum):
    """The frequency of the readings. It is a string too, so that a result keyed by Frequency is read with "daily" as well."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.__str__()


OUTPUT_DATE_FORMAT = "%d/%m/%Y"

MONTHS = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]

WEEK_LABEL = re.compile(r"^Du (\d{2}/\d{2}/\d{4}) au (\d{2}/\d{2}/\d{4})$")
MONTH_LABEL = re.compile(r"^(\S+) (\d{4})$")
YEAR_LABEL = re.compile(r"^(\d{4})$")


def next_month_start(day: date) -> date:
    """Returns the first day of the month that follows the month of day."""

    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def monday_of(day: date) -> date:
    """Returns the Monday of the week of day."""

    return day - timedelta(days=day.weekday())


def period_label(frequency: Frequency, start_date: date, end_date: date) -> str:
    """Returns the label of a period, as users see it in time_period.

    A daily label is the day, a weekly label is the first and last day of the week, a monthly label is the month name and
    the year, and a yearly label is the year.
    """

    last_day = end_date - timedelta(days=1)
    if frequency == Frequency.DAILY:
        return start_date.strftime(OUTPUT_DATE_FORMAT)
    if frequency == Frequency.WEEKLY:
        return f"Du {start_date.strftime(OUTPUT_DATE_FORMAT)} au {last_day.strftime(OUTPUT_DATE_FORMAT)}"
    if frequency == Frequency.MONTHLY:
        return f"{MONTHS[start_date.month - 1]} {start_date.year}"
    if frequency == Frequency.YEARLY:
        return str(start_date.year)

    raise ValueError(f"no time_period label for the {frequency} frequency")


def parse_period_label(frequency: Frequency, label: str) -> tuple[date, date]:
    """Returns the dates of a period from its label: the inverse of period_label.

    The end date is excluded, as in every period of this model.
    """

    label = label.strip()
    if frequency == Frequency.DAILY:
        day = datetime.strptime(label, OUTPUT_DATE_FORMAT).date()
        return day, day + timedelta(days=1)

    if frequency == Frequency.WEEKLY:
        match = WEEK_LABEL.match(label)
        if match is None:
            raise ValueError(f"not a weekly label: {label!r}")
        first_day = datetime.strptime(match.group(1), OUTPUT_DATE_FORMAT).date()
        last_day = datetime.strptime(match.group(2), OUTPUT_DATE_FORMAT).date()
        return first_day, last_day + timedelta(days=1)

    if frequency == Frequency.MONTHLY:
        match = MONTH_LABEL.match(label)
        if match is None or match.group(1) not in MONTHS:
            raise ValueError(f"not a monthly label: {label!r}")
        start = date(int(match.group(2)), MONTHS.index(match.group(1)) + 1, 1)
        return start, next_month_start(start)

    if frequency == Frequency.YEARLY:
        match = YEAR_LABEL.match(label)
        if match is None:
            raise ValueError(f"not a yearly label: {label!r}")
        start = date(int(match.group(1)), 1, 1)
        return start, date(start.year + 1, 1, 1)

    raise ValueError(f"no time_period label for the {frequency} frequency")


def covers_frequency(frequency: Frequency, start_date: date, end_date: date) -> bool:
    """Tells whether a period lies within one bucket of its frequency: a day, a week from Monday to Sunday, a month or a year.

    A period can be partial inside its bucket, as the first or last week of a file usually is.
    """

    last_day = end_date - timedelta(days=1)
    if frequency == Frequency.DAILY:
        return end_date - start_date == timedelta(days=1)
    if frequency == Frequency.WEEKLY:
        return 1 <= (end_date - start_date).days <= 7 and monday_of(start_date) == monday_of(last_day)
    if frequency == Frequency.MONTHLY:
        return (start_date.year, start_date.month) == (last_day.year, last_day.month)
    if frequency == Frequency.YEARLY:
        return start_date.year == last_day.year

    return False


class PeriodReading(BaseModel):
    """Consumption over a period, from start_date (included) to end_date (excluded)."""

    model_config = ConfigDict(populate_by_name=True)

    start_date: date = Field(alias=START_DATE_KEY)
    end_date: date = Field(alias=END_DATE_KEY)
    frequency: Frequency = Field(alias=FREQUENCY_KEY)
    time_period: str | None = Field(default=None, alias=TIME_PERIOD_KEY)
    start_index_m3: int | float | None = Field(default=None, alias=START_INDEX_KEY)
    end_index_m3: int | float | None = Field(default=None, alias=END_INDEX_KEY)
    volume_m3: int | float | None = Field(default=None, alias=VOLUME_KEY)
    energy_kwh: int | float | None = Field(default=None, alias=ENERGY_KEY)
    timestamp: str = Field(alias=TIMESTAMP_KEY)

    @field_serializer("start_date", "end_date")
    def serialize_dates(self, value: date) -> str:
        """Writes a date as ISO text, such as 2026-01-02, in the dict form."""

        return value.isoformat()

    @field_serializer("frequency")
    def serialize_frequency(self, frequency: Frequency) -> str:
        """Writes the frequency as its name, such as daily, in the dict form."""

        return frequency.value

    @model_validator(mode="after")
    def check_period(self) -> "PeriodReading":
        """Checks the dates against the frequency, and the label against the dates."""

        if self.end_date <= self.start_date:
            raise ValueError("the period is empty")

        if not covers_frequency(self.frequency, self.start_date, self.end_date):
            raise ValueError(f"the period is not a {self.frequency} period")

        expected = period_label(self.frequency, self.start_date, self.end_date)
        if self.time_period is None:
            self.time_period = expected
        elif self.time_period != expected:
            raise ValueError(f"time_period {self.time_period!r} does not match {expected!r}")

        return self


class DailyReading(PeriodReading):
    """One day of consumption, with the converter factor, the temperature and the GrDF type of the day."""

    converter_factor_kwh_m3: float | None = Field(default=None, alias=CONVERTER_FACTOR_KEY)
    temperature_degC: float | None = Field(default=None, alias=TEMPERATURE_KEY)  # noqa: N815 (the name of the output key)
    type_: str | None = Field(default=None, alias=TYPE_KEY)
