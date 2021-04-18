from enum import Enum


# ------------------------------------------------------------------------------------------------------------
class PropertyName(Enum):
    DATE = "date"
    START_INDEX_M3 = "start_index_m3"
    END_INDEX_M3 = "end_index_m3"
    VOLUME_M3 = "volume_m3"
    ENERGY_KWH = "energy_kwh"
    CONVERTER_FACTOR = "converter_factor"
    LOCAL_TEMPERATURE = "local_temperature"
    TYPE = "type"
    TIMESTAMP = "timestamp"


# ------------------------------------------------------------------------------------------------------------
class Frequency(Enum):
    HOURLY = 0
    DAILY = 1
    WEEKLY = 2
    MONTHLY = 3

    def __str__(self):
        return self.name
