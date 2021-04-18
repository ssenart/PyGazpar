import logging
from datetime import datetime
from pygazpar.enum import Frequency
from pygazpar.enum import PropertyName
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl import load_workbook


# ------------------------------------------------------------------------------------------------------------
class DataFileParser:

    logger = logging.getLogger(__name__)

    @staticmethod
    def parse(dataFilename: str, dataReadingFrequency: Frequency, lastNRows: int) -> dict:

        parseByFrequency = {
            Frequency.HOURLY: DataFileParser.__parseHourly,
            Frequency.DAILY: DataFileParser.__parseDaily,
            Frequency.WEEKLY: DataFileParser.__parseWeekly,
            Frequency.MONTHLY: DataFileParser.__parseMonthly
        }

        worksheetNameByFrequency = {
            Frequency.HOURLY: "Historique par heure",
            Frequency.DAILY: "Historique par jour",
            Frequency.WEEKLY: "Historique par semaine",
            Frequency.MONTHLY: "Historique par mois"
        }

        DataFileParser.logger.debug(f"Loading Excel data file '{dataFilename}'...")

        workbook = load_workbook(filename=dataFilename)

        worksheet = workbook[worksheetNameByFrequency[dataReadingFrequency]]

        res = parseByFrequency[dataReadingFrequency](worksheet, lastNRows)

        workbook.close()

        return res

    @staticmethod
    def __parseHourly(worksheet: Worksheet, lastNRows: int) -> dict:
        raise NotImplementedError("__parseHourly not yet implemented")

    @staticmethod
    def __parseDaily(worksheet: Worksheet, lastNRows: int) -> dict:

        res = []

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        minRowNum = max(8, len(worksheet['B']) + 1 - lastNRows) if lastNRows > 0 else 8
        maxRowNum = len(worksheet['B'])
        for rownum in range(minRowNum, maxRowNum + 1):
            row = {}
            if worksheet.cell(column=2, row=rownum).value is not None:
                row[PropertyName.DATE.value] = worksheet.cell(column=2, row=rownum).value
                row[PropertyName.START_INDEX_M3.value] = worksheet.cell(column=3, row=rownum).value
                row[PropertyName.END_INDEX_M3.value] = worksheet.cell(column=4, row=rownum).value
                row[PropertyName.VOLUME_M3.value] = worksheet.cell(column=5, row=rownum).value
                row[PropertyName.ENERGY_KWH.value] = worksheet.cell(column=6, row=rownum).value
                row[PropertyName.CONVERTER_FACTOR.value] = worksheet.cell(column=7, row=rownum).value
                row[PropertyName.LOCAL_TEMPERATURE.value] = worksheet.cell(column=8, row=rownum).value
                row[PropertyName.TYPE.value] = worksheet.cell(column=9, row=rownum).value
                row[PropertyName.TIMESTAMP.value] = data_timestamp
                res.append(row)

        DataFileParser.logger.debug(f"Daily data read successfully between row #{minRowNum} and row #{maxRowNum}")

        return res

    @staticmethod
    def __parseWeekly(worksheet: Worksheet, lastNRows: int) -> dict:

        res = []

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        minRowNum = max(8, len(worksheet['B']) + 1 - lastNRows) if lastNRows > 0 else 8
        maxRowNum = len(worksheet['B'])
        for rownum in range(minRowNum, maxRowNum + 1):
            row = {}
            if worksheet.cell(column=2, row=rownum).value is not None:
                row[PropertyName.DATE.value] = worksheet.cell(column=2, row=rownum).value
                row[PropertyName.VOLUME_M3.value] = worksheet.cell(column=3, row=rownum).value
                row[PropertyName.ENERGY_KWH.value] = worksheet.cell(column=4, row=rownum).value
                row[PropertyName.TIMESTAMP.value] = data_timestamp
                res.append(row)

        DataFileParser.logger.debug(f"Weekly data read successfully between row #{minRowNum} and row #{maxRowNum}")

        return res

    @staticmethod
    def __parseMonthly(worksheet: Worksheet, lastNRows: int) -> dict:

        res = []

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        minRowNum = max(8, len(worksheet['B']) + 1 - lastNRows) if lastNRows > 0 else 8
        maxRowNum = len(worksheet['B'])
        for rownum in range(minRowNum, maxRowNum + 1):
            row = {}
            if worksheet.cell(column=2, row=rownum).value is not None:
                row[PropertyName.DATE.value] = worksheet.cell(column=2, row=rownum).value
                row[PropertyName.VOLUME_M3.value] = worksheet.cell(column=3, row=rownum).value
                row[PropertyName.ENERGY_KWH.value] = worksheet.cell(column=4, row=rownum).value
                row[PropertyName.TIMESTAMP.value] = data_timestamp
                res.append(row)

        DataFileParser.logger.debug(f"Monthly data read successfully between row #{minRowNum} and row #{maxRowNum}")

        return res
