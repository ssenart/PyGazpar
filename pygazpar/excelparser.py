import logging
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell, MergedCell
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import ValidationError

from pygazpar.model import (
    DailyReading,
    Frequency,
    PeriodReading,
    PropertyName,
    parse_period_label,
)

FIRST_DATA_LINE_NUMBER = 10

Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class ExcelParser:
    # ------------------------------------------------------
    @staticmethod
    def parse(data_filename: str, data_reading_frequency: Frequency) -> Sequence[PeriodReading]:

        parse_by_frequency: dict[Frequency, Any] = {
            Frequency.HOURLY: ExcelParser._parse_hourly,
            Frequency.DAILY: ExcelParser._parse_daily,
            Frequency.WEEKLY: ExcelParser._parse_weekly,
            Frequency.MONTHLY: ExcelParser._parse_monthly,
        }

        Logger.debug(f"Loading Excel data file '{data_filename}'...")

        workbook = load_workbook(filename=data_filename)

        worksheet = workbook.active

        res = parse_by_frequency[data_reading_frequency](worksheet)  # type: ignore

        workbook.close()

        Logger.debug("Processed Excel %s data: %s", data_reading_frequency, res)

        return res

    # ------------------------------------------------------
    @staticmethod
    def _number(cell: Cell | MergedCell) -> int | float | None:
        """Returns the number of a cell, written with a comma or with a point, or None when the cell is empty."""

        value = cell.value
        if value is None:
            return None
        if isinstance(value, str):
            return float(value.replace(",", ".")) if len(value.strip()) > 0 else None
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(f"not a number: {value!r}")

        return float(value) if isinstance(value, Decimal) else value

    # ------------------------------------------------------
    @staticmethod
    def _text(cell: Cell | MergedCell) -> str | None:
        """Returns the text of a cell, without surrounding spaces, or None when the cell is empty."""

        value = cell.value
        if value is None:
            return None

        return value.strip() if isinstance(value, str) else str(value)

    # ------------------------------------------------------
    @staticmethod
    def _parse_hourly(worksheet: Worksheet) -> list[PeriodReading]:  # noqa: ARG004
        return []

    # ------------------------------------------------------
    @staticmethod
    def _parse_daily(worksheet: Worksheet) -> list[PeriodReading]:

        res: list[PeriodReading] = []

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        min_row_num = FIRST_DATA_LINE_NUMBER
        max_row_num = len(worksheet["B"])
        for rownum in range(min_row_num, max_row_num + 1):
            label = worksheet.cell(column=2, row=rownum)
            if label.value is None:
                continue
            try:
                start_date, end_date = parse_period_label(Frequency.DAILY, str(label.value))
                res.append(
                    DailyReading.model_validate(
                        {
                            PropertyName.START_DATE.value: start_date,
                            PropertyName.END_DATE.value: end_date,
                            PropertyName.FREQUENCY.value: Frequency.DAILY,
                            PropertyName.START_INDEX.value: ExcelParser._number(worksheet.cell(column=3, row=rownum)),
                            PropertyName.END_INDEX.value: ExcelParser._number(worksheet.cell(column=4, row=rownum)),
                            PropertyName.VOLUME.value: ExcelParser._number(worksheet.cell(column=5, row=rownum)),
                            PropertyName.ENERGY.value: ExcelParser._number(worksheet.cell(column=6, row=rownum)),
                            PropertyName.CONVERTER_FACTOR.value: ExcelParser._number(
                                worksheet.cell(column=7, row=rownum)
                            ),
                            PropertyName.TEMPERATURE.value: ExcelParser._number(worksheet.cell(column=8, row=rownum)),
                            PropertyName.TYPE.value: ExcelParser._text(worksheet.cell(column=9, row=rownum)),
                            PropertyName.TIMESTAMP.value: data_timestamp,
                        }
                    )
                )
            except (ValueError, ValidationError) as error:
                Logger.warning(f"Excel row #{rownum} ignored: {error}")

        Logger.debug(f"Daily data read successfully between row #{min_row_num} and row #{max_row_num}")

        return res

    # ------------------------------------------------------
    @staticmethod
    def _parse_weekly(worksheet: Worksheet) -> list[PeriodReading]:
        return ExcelParser._parse_periods(worksheet, Frequency.WEEKLY)

    # ------------------------------------------------------
    @staticmethod
    def _parse_monthly(worksheet: Worksheet) -> list[PeriodReading]:
        return ExcelParser._parse_periods(worksheet, Frequency.MONTHLY)

    # ------------------------------------------------------
    @staticmethod
    def _parse_periods(worksheet: Worksheet, frequency: Frequency) -> list[PeriodReading]:
        """Reads the weekly or monthly rows: a label, the volume and the energy of the period."""

        res: list[PeriodReading] = []

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        min_row_num = FIRST_DATA_LINE_NUMBER
        max_row_num = len(worksheet["B"])
        for rownum in range(min_row_num, max_row_num + 1):
            label = worksheet.cell(column=2, row=rownum)
            if label.value is None:
                continue
            try:
                start_date, end_date = parse_period_label(frequency, str(label.value))
                res.append(
                    PeriodReading.model_validate(
                        {
                            PropertyName.START_DATE.value: start_date,
                            PropertyName.END_DATE.value: end_date,
                            PropertyName.FREQUENCY.value: frequency,
                            PropertyName.VOLUME.value: ExcelParser._number(worksheet.cell(column=3, row=rownum)),
                            PropertyName.ENERGY.value: ExcelParser._number(worksheet.cell(column=4, row=rownum)),
                            PropertyName.TIMESTAMP.value: data_timestamp,
                        }
                    )
                )
            except (ValueError, ValidationError) as error:
                Logger.warning(f"Excel row #{rownum} ignored: {error}")

        Logger.debug(f"{frequency} data read successfully between row #{min_row_num} and row #{max_row_num}")

        return res
