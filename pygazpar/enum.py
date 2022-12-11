import json
from enum import Enum


# ------------------------------------------------------------------------------------------------------------
class PropertyName(Enum):
    TIME_PERIOD = "time_period"
    START_INDEX = "start_index_m3"
    END_INDEX = "end_index_m3"
    VOLUME = "volume_m3"
    ENERGY = "energy_kwh"
    CONVERTER_FACTOR = "converter_factor_kwh/m3"
    TEMPERATURE = "temperature_degC"
    TYPE = "type"
    TIMESTAMP = "timestamp"

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.__str__()


# ------------------------------------------------------------------------------------------------------------
class Frequency(Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.__str__()


# ------------------------------------------------------------------------------------------------------------
class JSONEncoder(json.JSONEncoder):

    def default(self, obj):

        if isinstance(obj, PropertyName) or isinstance(obj, Frequency):
            return str(obj)

        # Call the default method for other types
        return json.JSONEncoder.default(self, obj)