"""
sqlfy.contracts.common.envelope
================================
Generic response envelope for wrapping contract payloads.

The envelope is optional and is **not** used by the current CLI commands,
which emit the raw contract JSON directly.  It is provided for future
use cases where callers need top-level metadata alongside the payload
(e.g. HTTP API responses, streaming protocols).

Example::

    from sqlfy.contracts.common.envelope import ResponseEnvelope
    from sqlfy.contracts.analysis.v1 import InsightsV1

    envelope = ResponseEnvelope[InsightsV1](
        schema_version="v1",
        contract="insights",
        data=insights_model_instance,
    )
    print(envelope.model_dump_json(by_alias=True))
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    """Top-level wrapper that adds version and timing metadata to any contract payload.

    Consumers that do not need the envelope can use the contract model directly.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    schema_version: str = Field(
        ...,
        description="Contract slot version, e.g. 'v1'.",
    )
    contract: str = Field(
        ...,
        description="Contract name, e.g. 'insights'.",
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp of response generation.",
    )
    data: T = Field(
        ...,
        description="The contract payload.",
    )
