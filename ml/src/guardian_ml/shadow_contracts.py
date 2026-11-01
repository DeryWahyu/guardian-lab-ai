"""Typed shadow API: no response or error echoes the submitted target."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InputType = Literal["URL", "QR"]
RiskBand = Literal["LOW", "MEDIUM", "HIGH"]


class PredictionRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    url: str = Field(min_length=1, max_length=16384)
    input_type: InputType = "URL"


class HumanView(BaseModel):
    title: str
    explanation: str
    recommended_action: Literal["perlu_verifikasi"] = "perlu_verifikasi"


class GeekView(BaseModel):
    scope: Literal["url_only"] = "url_only"
    model_version: str | None = None
    artifact_sha256: str | None = None
    feature_schema: str | None = None
    score_reference: str = "research_calibration_not_traffic_probability"
    thresholds: dict[str, float] | None = None
    context_flags: list[str] = Field(default_factory=list)
    content_inspected: Literal[False] = False
    qr_image_decoded_by_service: Literal[False] = False


class ShadowResult(BaseModel):
    mode: Literal["shadow"] = "shadow"
    status: Literal["complete", "unsupported_input", "unavailable"]
    input_type: InputType
    decision: Literal["needs_review"] = "needs_review"
    needs_further_review: Literal[True] = True
    production_ready: Literal[False] = False
    noncommercial_research_only: Literal[True] = True
    risk_band: RiskBand | None = None
    model_score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    reason_codes: list[str] = Field(default_factory=list)
    human: HumanView
    geek: GeekView

    @model_validator(mode="after")
    def score_only_for_completed_inference(self):
        if self.status != "complete" and (
            self.model_score is not None or self.risk_band is not None
        ):
            raise ValueError("unsupported_or_unavailable_cannot_be_low_risk")
        if self.status == "complete" and (self.model_score is None or self.risk_band is None):
            raise ValueError("completed_inference_requires_model_score")
        return self
