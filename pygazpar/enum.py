from enum import Enum


class PropertyNameEnum(Enum):
    DATE = "date"
    START_INDEX_M3 = "start_index_m3"
    END_INDEX_M3 = "end_index_m3"
    VOLUME_M3 = "volume_m3"
    ENERGY_KWH = "energy_kwh"
    CONVERTER_FACTOR = "converter_factor"
    LOCAL_TEMPERATURE = "local_temperature"
    TYPE = "type"
    TIMESTAMP = "timestamp"
