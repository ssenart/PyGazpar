"""The records of the GrDF consumption API, validated as they are read.

GrDF can change its API at any time, so these models stay separate from the daily data model of PyGazpar (see model.py).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class GrdfRecord(BaseModel):
    """One record of the GrDF consumption API: an informative gas day, or a published period.

    Unknown fields are kept, so that a new field from GrDF does not make the record invalid.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    journee_gaziere: date | None = Field(default=None, alias="journeeGaziere")
    date_debut_releve: datetime | None = Field(default=None, alias="dateDebutReleve")
    date_fin_releve: datetime | None = Field(default=None, alias="dateFinReleve")
    index_debut: Decimal | None = Field(default=None, alias="indexDebut")
    index_fin: Decimal | None = Field(default=None, alias="indexFin")
    volume_brut_consomme: Decimal | None = Field(default=None, alias="volumeBrutConsomme")
    energie_consomme: Decimal | None = Field(default=None, alias="energieConsomme")
    coeff_conversion: Decimal | None = Field(default=None, alias="coeffConversion")
    temperature: Decimal | None = None
    qualification_releve: str | None = Field(default=None, alias="qualificationReleve")

    @model_validator(mode="after")
    def check_consistency(self) -> "GrdfRecord":
        """Rejects the values that cannot be true.

        A published period must give its indexes and consumption, since they are what its days are made from. Negative
        consumption and periods that end before they start are rejected too.
        """

        if self.journee_gaziere is None:
            values = (
                self.index_debut,
                self.index_fin,
                self.volume_brut_consomme,
                self.energie_consomme,
                self.coeff_conversion,
            )
            if any(value is None for value in values):
                raise ValueError("a published period needs its indexes, volume, energy and coefficient")

        for name, value in (
            ("volumeBrutConsomme", self.volume_brut_consomme),
            ("energieConsomme", self.energie_consomme),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} is negative: {value}")

        if self.date_debut_releve is not None and self.date_fin_releve is not None:
            if self.date_fin_releve.date() <= self.date_debut_releve.date():
                raise ValueError("the period is empty")

        return self


class GrdfPce(BaseModel):
    """One PCE of the account, as the PCE list returns it. Unknown fields are kept."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id_object: str = Field(alias="idObject")


class GrdfPceList(RootModel[list[GrdfPce]]):
    """The PCE list of the account."""


class GrdfPceConsumption(BaseModel):
    """The consumption of one PCE. Its records are validated one by one by the parser."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id_pce: str | None = Field(default=None, alias="idPce")
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
