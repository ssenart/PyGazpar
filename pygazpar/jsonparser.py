import json
import logging
from datetime import datetime, timedelta
from typing import Any

from pygazpar.enum import PropertyName

INPUT_DATE_FORMAT = "%Y-%m-%d"

OUTPUT_DATE_FORMAT = "%d/%m/%Y"

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
            reading_date = releve["journeeGaziere"]
            if reading_date is None:
                end_date = releve.get("dateFinReleve")
                if end_date is None:
                    Logger.warning("Reading ignored because it has no end date")
                    continue
                reading_date = (datetime.fromisoformat(end_date) - timedelta(days=1)).strftime(INPUT_DATE_FORMAT)

            temperature = releve["temperature"]
            if temperature is None and temperatures is not None and len(temperatures) > 0:
                temperature = temperatures.get(reading_date)

            item = {}
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
