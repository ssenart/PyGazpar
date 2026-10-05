"""The records of the GrDF consumption API, validated as they are read.

GrDF can change its API at any time, so these models stay separate from the daily data model of PyGazpar (see model.py).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, RootModel, model_validator


class GrdfRecord(BaseModel):
    """One record of the GrDF consumption API: an informative gas day, or a published period.

    Unknown fields are kept, so that a new field from GrDF does not make the record invalid.
    """

    model_config = ConfigDict(extra="allow")

    journeeGaziere: date | None = None
    dateDebutReleve: datetime | None = None
    dateFinReleve: datetime | None = None
    indexDebut: Decimal | None = None
    indexFin: Decimal | None = None
    volumeBrutConsomme: Decimal | None = None
    energieConsomme: Decimal | None = None
    coeffConversion: Decimal | None = None
    temperature: Decimal | None = None
    qualificationReleve: str | None = None

    @model_validator(mode="after")
    def check_consistency(self) -> "GrdfRecord":
        """Rejects the values that cannot be true.

        A published period must give its indexes and consumption, since they are what its days are made from. Negative
        consumption and periods that end before they start are rejected too.
        """

        if self.journeeGaziere is None:
            values = (
                self.indexDebut,
                self.indexFin,
                self.volumeBrutConsomme,
                self.energieConsomme,
                self.coeffConversion,
            )
            if any(value is None for value in values):
                raise ValueError("a published period needs its indexes, volume, energy and coefficient")

        for name in ("volumeBrutConsomme", "energieConsomme"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} is negative: {value}")

        if self.dateDebutReleve is not None and self.dateFinReleve is not None:
            if self.dateFinReleve.date() <= self.dateDebutReleve.date():
                raise ValueError("the period is empty")

        return self


class GrdfPce(BaseModel):
    """One PCE of the account, as the PCE list returns it. Unknown fields are kept."""

    model_config = ConfigDict(extra="allow")

    idObject: str


class GrdfPceList(RootModel[list[GrdfPce]]):
    """The PCE list of the account."""


class GrdfPceConsumption(BaseModel):
    """The consumption of one PCE. Its records are validated one by one by the parser."""

    model_config = ConfigDict(extra="allow")

    idPce: str | None = None
    frequence: str | None = None
    releves: list[Any]


class GrdfConsumptionResponse(RootModel[dict[str, GrdfPceConsumption]]):
    """The consumption response, keyed by PCE identifier."""


class GrdfMeteoResponse(RootModel[dict[date, float | None]]):
    """The temperature of each day, keyed by date."""


class GrdfExcelSheet(BaseModel):
    """An Excel file of consumption, as the API sends it."""

    filename: str
    content: bytes
