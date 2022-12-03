import json
import logging
from datetime import datetime
from pygazpar.enum import PropertyName
from typing import Any, List, Dict

INPUT_DATE_FORMAT = "%Y-%m-%d"

OUTPUT_DATE_FORMAT = "%d/%m/%Y"

Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class JsonParser:

    # ------------------------------------------------------
    @staticmethod
    def parse(jsonStr: str, pceIdentifier: str) -> List[Dict[str, Any]]:

        res = []

        data = json.loads(jsonStr)

        # Timestamp of the data.
        data_timestamp = datetime.now().isoformat()

        for releve in data[pceIdentifier]['releves']:
            item = {}
            item[PropertyName.TIME_PERIOD.value] = datetime.strftime(datetime.strptime(releve['journeeGaziere'], INPUT_DATE_FORMAT), OUTPUT_DATE_FORMAT)
            item[PropertyName.START_INDEX.value] = releve['indexDebut']
            item[PropertyName.END_INDEX.value] = releve['indexFin']
            item[PropertyName.VOLUME.value] = releve['volumeBrutConsomme']
            item[PropertyName.ENERGY.value] = releve['energieConsomme']
            item[PropertyName.CONVERTER_FACTOR.value] = releve['coeffConversion']
            item[PropertyName.TEMPERATURE.value] = releve['temperature']
            item[PropertyName.TYPE.value] = releve['qualificationReleve']
            item[PropertyName.TIMESTAMP.value] = data_timestamp

            res.append(item)

        Logger.debug("Daily data read successfully from Json")

        return res
