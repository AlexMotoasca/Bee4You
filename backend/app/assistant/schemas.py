"""Voice assistant data shapes: LLM extraction output and the HTTP contract."""

from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.schemas.records import Temperament, Unit

EntryKind = Literal["treatment", "harvest", "inventory", "note", "unknown"]
InventoryAction = Literal["purchase", "used"]


class ExtractedEntry(BaseModel):
    """What the LLM pulls out of the conversation. It never contains ids.

    Every field is required-but-nullable so Groq strict JSON-schema mode accepts it.
    """

    model_config = ConfigDict(extra="forbid")

    kind: EntryKind = Field(
        description="treatment = medication/varroa treatment given to a hive; harvest = honey "
        "or other product taken; inventory = supplies bought or used up; note = inspection "
        "observation (queen seen, temperament, free text); unknown = cannot tell."
    )
    colony: str | None = Field(
        description="The hive as spoken, numbers as digits, e.g. '12' or 'Queen Anne'. Null if "
        "not said."
    )
    apiary: str | None = Field(description="Apiary / site name as spoken. Null if not said.")
    product: str | None = Field(
        description="Product or item name, e.g. 'oxalic acid', 'Apivar', 'sugar syrup'."
    )
    amount: float | None = Field(
        description="Amount or quantity as a number (digits). Null if not said - never guess."
    )
    unit: Unit | None = Field(description="Unit of the amount. Null if not said.")
    inventory_action: InventoryAction | None = Field(
        description="For inventory: purchase = stock added, used = stock consumed."
    )
    queen_seen: bool | None = Field(description="True/false only if the queen was mentioned.")
    temperament: Temperament | None = Field(description="Colony temperament if mentioned.")
    note: str | None = Field(
        description="Other observations worth keeping, in the user's language. Null if none."
    )
    date: str | None = Field(
        description="Date of the work as YYYY-MM-DD if the user said a day (e.g. yesterday). "
        "Null means today."
    )

    @model_validator(mode="before")
    @classmethod
    def _null_strings_are_null(cls, data: Any) -> Any:
        """Models sometimes write the string "null" (or "none", "") for a missing value."""
        if isinstance(data, dict):
            return {
                k: None
                if isinstance(v, str) and v.strip().casefold() in {"", "null", "none", "n/a"}
                else v
                for k, v in data.items()
            }
        return data


class VoiceContext(BaseModel):
    colony_id: UUID | None = None
    apiary_id: UUID | None = None


class StartVoiceSession(BaseModel):
    transcript: str = Field(min_length=1, max_length=2000)
    context: VoiceContext = VoiceContext()
    locale: str = Field(default="en-US", min_length=2, max_length=20)
    client_time: AwareDatetime | None = None


class VoiceReply(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


TurnStatus = Literal["question", "confirm", "saved", "not_understood", "cancelled"]
Haptic = Literal["saved", "needs_answer", "not_understood"]


class SavedRecord(BaseModel):
    table: str
    id: UUID


class VoiceTurn(BaseModel):
    thread_id: UUID
    status: TurnStatus
    speak: str
    haptic: Haptic
    draft: dict[str, Any] | None = None
    record: SavedRecord | None = None


class TranscriptionOut(BaseModel):
    text: str
