"""Esquemas de entrada (validación estricta). Las salidas se serializan en cada router."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def clean_tags(v: list[str]) -> list[str]:
    out: list[str] = []
    for t in v:
        t = t.strip().lower()[:32]
        if t and t not in out:
            out.append(t)
    return out


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LocalLogin(Strict):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=80)


class ProjectCreate(Strict):
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=2000)
    problem: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return clean_tags(v)


class ProjectUpdate(Strict):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    problem: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = Field(default=None, max_length=12)
    status: Literal["active", "archived"] | None = None


class MemberUpsert(Strict):
    email: EmailStr
    role: Literal["lead", "engineer", "reviewer", "reader"]


class ArchitectureCreate(Strict):
    name: str = Field(min_length=2, max_length=80)
    family: Literal["feedforward", "rnn", "cnn", "gan"]
    justification: str = Field(default="", max_length=2000)
    config: dict


class ArchitectureValidate(Strict):
    family: Literal["feedforward", "rnn", "cnn", "gan"]
    config: dict


class TrainingParams(Strict):
    epochs: int = Field(ge=1, le=5000)
    batch_size: int = Field(default=32, ge=1, le=4096)
    optimizer: Literal["adam", "sgd", "rmsprop"] = "adam"
    learning_rate: float = Field(default=0.01, gt=0, le=1)
    seed: int | None = Field(default=42, ge=0, le=2**31 - 1)
    # Modo observación: cada época dura al menos ~150 ms para que la animación de la red sea visible.
    observe: bool = True


class TrainingJobCreate(Strict):
    architecture_id: str
    dataset_id: str
    params: TrainingParams
    priority: int = Field(default=0, ge=0, le=10)


class CancelRequest(Strict):
    reason: str = Field(default="Cancelado por el usuario", max_length=300)


class ModelStatusUpdate(Strict):
    status: Literal["reviewed", "approved", "retired"]
    notes: str = Field(default="", max_length=2000)


class EvaluationNote(Strict):
    note: str = Field(min_length=3, max_length=2000)


class UserAdminUpdate(Strict):
    is_admin: bool | None = None
    status: Literal["active", "suspended"] | None = None


class LimitsUpdate(Strict):
    values: dict[str, int]
