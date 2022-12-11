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
