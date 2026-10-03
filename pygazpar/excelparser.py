import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
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
class ExcelParser:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    @staticmethod
    def parse(dataFilename: str, dataReadingFrequency: Frequency) -> Sequence[PeriodReading]:

        parseByFrequency: dict[Frequency, Any] = {
            Frequency.HOURLY: ExcelParser.__parseHourly,
            Frequency.DAILY: ExcelParser.__parseDaily,
            Frequency.WEEKLY: ExcelParser.__parseWeekly,
            Frequency.MONTHLY: ExcelParser.__parseMonthly,
        }

        Logger.debug(f"Loading Excel data file '{dataFilename}'...")

        workbook = load_workbook(filename=dataFilename)

        worksheet = workbook.active

        res = parseByFrequency[dataReadingFrequency](worksheet)  # type: ignore

        workbook.close()

        Logger.debug("Processed Excel %s data: %s", dataReadingFrequency, res)

        return res

    # ------------------------------------------------------
    @staticmethod
    def __number(cell: Cell) -> int | float | None:
        """Returns the number of a cell, written with a comma or with a point, or None when the cell is empty."""

        if cell.value is None:
            return None
        if isinstance(cell.value, str):
            return float(cell.value.replace(",", ".")) if len(cell.value.strip()) > 0 else None
        return cell.value

    # ------------------------------------------------------
    @staticmethod
    def __text(cell: Cell) -> Any:
        """Returns the text of a cell, without surrounding spaces, or None when the cell is empty."""

        return cell.value.strip() if isinstance(cell.value, str) else cell.value

    # ------------------------------------------------------
    @staticmethod
    def __parseHourly(worksheet: Worksheet) -> list[PeriodReading]:  # pylint: disable=unused-argument
        return []

    # ------------------------------------------------------
    @staticmethod
    def __parseDaily(worksheet: Worksheet) -> list[PeriodReading]:

        res: list[PeriodReading] = []

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        minRowNum = FIRST_DATA_LINE_NUMBER
        maxRowNum = len(worksheet["B"])
        for rownum in range(minRowNum, maxRowNum + 1):
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
                            PropertyName.START_INDEX.value: ExcelParser.__number(worksheet.cell(column=3, row=rownum)),
                            PropertyName.END_INDEX.value: ExcelParser.__number(worksheet.cell(column=4, row=rownum)),
                            PropertyName.VOLUME.value: ExcelParser.__number(worksheet.cell(column=5, row=rownum)),
                            PropertyName.ENERGY.value: ExcelParser.__number(worksheet.cell(column=6, row=rownum)),
                            PropertyName.CONVERTER_FACTOR.value: ExcelParser.__number(
                                worksheet.cell(column=7, row=rownum)
                            ),
                            PropertyName.TEMPERATURE.value: ExcelParser.__number(worksheet.cell(column=8, row=rownum)),
                            PropertyName.TYPE.value: ExcelParser.__text(worksheet.cell(column=9, row=rownum)),
                            PropertyName.TIMESTAMP.value: data_timestamp,
                        }
                    )
                )
            except (ValueError, ValidationError) as error:
                Logger.warning(f"Excel row #{rownum} ignored: {error}")

        Logger.debug(f"Daily data read successfully between row #{minRowNum} and row #{maxRowNum}")

        return res

    # ------------------------------------------------------
    @staticmethod
    def __parseWeekly(worksheet: Worksheet) -> list[PeriodReading]:
        return ExcelParser.__parsePeriods(worksheet, Frequency.WEEKLY)

    # ------------------------------------------------------
    @staticmethod
    def __parseMonthly(worksheet: Worksheet) -> list[PeriodReading]:
        return ExcelParser.__parsePeriods(worksheet, Frequency.MONTHLY)

    # ------------------------------------------------------
    @staticmethod
    def __parsePeriods(worksheet: Worksheet, frequency: Frequency) -> list[PeriodReading]:
        """Reads the weekly or monthly rows: a label, the volume and the energy of the period."""

        res: list[PeriodReading] = []

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        minRowNum = FIRST_DATA_LINE_NUMBER
        maxRowNum = len(worksheet["B"])
        for rownum in range(minRowNum, maxRowNum + 1):
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
                            PropertyName.VOLUME.value: ExcelParser.__number(worksheet.cell(column=3, row=rownum)),
                            PropertyName.ENERGY.value: ExcelParser.__number(worksheet.cell(column=4, row=rownum)),
                            PropertyName.TIMESTAMP.value: data_timestamp,
                        }
                    )
                )
            except (ValueError, ValidationError) as error:
                Logger.warning(f"Excel row #{rownum} ignored: {error}")

        Logger.debug(f"{frequency} data read successfully between row #{minRowNum} and row #{maxRowNum}")

        return res
