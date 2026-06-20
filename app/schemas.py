from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class VerdictEnum(str, Enum):
    worth_looking = "worth_looking"
    caution = "caution"
    skip = "skip"


class FinalRecommendationEnum(str, Enum):
    BUY_WITH_CONFIDENCE = "BUY_WITH_CONFIDENCE"
    CAUTIOUS = "CAUTIOUS"
    REJECT = "REJECT"


class RiskSeverityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class PriorityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ConfidenceEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class EvidenceItem(BaseModel):
    source: str
    signal: str
    value: str | int | float | None = None
    details: str | None = None


class ParseListingStatusEnum(str, Enum):
    success = "success"
    captcha = "captcha"
    blocked = "blocked"
    browser_missing = "browser_missing"
    invalid_html = "invalid_html"
    transient_error = "transient_error"
    failed = "failed"


class TaskStatusEnum(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    unknown = "unknown"


class VehicleInput(BaseModel):
    brand: str | None = None
    model: str | None = None
    year: int | None = Field(None, ge=1980, le=2030)
    mileage_km: int | None = Field(None, ge=0)
    price_rub: int | None = Field(None, ge=0)
    engine: str | None = None
    transmission: str | None = None
    drive: str | None = None
    body_type: str | None = None
    color: str | None = None
    vin: str | None = None
    description: str | None = None


class ChecklistItem(BaseModel):
    zone: str
    title: str
    how_to_check: str
    tools: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    title: str
    severity: RiskSeverityEnum
    description: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    rationale: str | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    priority: RiskSeverityEnum | None = None
    action: str | None = None
    estimated_cost_min: int | None = None
    estimated_cost_max: int | None = None

    @model_validator(mode="after")
    def fill_precision_fields(self):
        if not self.evidence:
            self.evidence = [
                EvidenceItem(
                    source="analysis",
                    signal="risk_description",
                    details=self.description,
                )
            ]
        if not self.rationale:
            self.rationale = self.description
        if self.priority is None:
            self.priority = self.severity
        if self.confidence is None:
            self.confidence = (
                85
                if self.severity == RiskSeverityEnum.high
                else 70
                if self.severity == RiskSeverityEnum.medium
                else 60
            )
        if not self.action:
            self.action = "Подтвердите риск на диагностике и используйте его как аргумент для торга"
        return self

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            return [{"source": "analysis", "signal": "legacy_text", "details": text}]
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            normalized: list[dict | EvidenceItem] = []
            for item in value:
                if isinstance(item, str):
                    txt = item.strip()
                    if txt:
                        normalized.append(
                            {"source": "analysis", "signal": "legacy_text", "details": txt}
                        )
                    continue
                if isinstance(item, dict):
                    normalized.append(item)
                    continue
                if isinstance(item, EvidenceItem):
                    normalized.append(item)
            return normalized
        return []


class PhotoMetadataInput(BaseModel):
    photo_url: str | None = None
    photo_path: str | None = None
    zone: str | None = None
    note: str | None = None

    @field_validator("photo_url", "photo_path", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def validate_photo_source(self):
        if not self.photo_url and not self.photo_path:
            raise ValueError("Either photo_url or photo_path must be provided")
        return self


class ObservedDefectInput(BaseModel):
    zone: str
    title: str
    details: str | None = None
    severity: RiskSeverityEnum = Field(default=RiskSeverityEnum.medium)
    estimated_cost_min: int | None = Field(default=None, ge=0)
    estimated_cost_max: int | None = Field(default=None, ge=0)
    linked_photo_indexes: list[int] = Field(default_factory=list)

    @field_validator("linked_photo_indexes")
    @classmethod
    def validate_linked_photo_indexes(cls, value: list[int]) -> list[int]:
        if any(index < 0 for index in value):
            raise ValueError("linked_photo_indexes must be >= 0")
        return value

    @model_validator(mode="after")
    def validate_cost_bounds(self):
        if (
            self.estimated_cost_min is not None
            and self.estimated_cost_max is not None
            and self.estimated_cost_min > self.estimated_cost_max
        ):
            raise ValueError("estimated_cost_min cannot exceed estimated_cost_max")
        return self


class AvitoPartOffer(BaseModel):
    title: str
    price_rub: int
    url: str


class PhotoAnalysisFinding(BaseModel):
    source_photo_url: str
    zone: str | None = None
    title: str
    severity: RiskSeverityEnum = RiskSeverityEnum.low
    confidence: int = Field(default=60, ge=0, le=100)
    evidence: str
    recommendation: str | None = None


class VehiclePassport(BaseModel):
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    mileage_km: int | None = None
    price_rub: int | None = None
    engine: str | None = None
    transmission: str | None = None
    drive: str | None = None
    body_type: str | None = None
    color: str | None = None
    vin: str | None = None
    source_platform: str | None = None
    source_listing_url: str | None = None
    source_quality: str = "partial"


class PartPriceBlock(BaseModel):
    category: str
    part_name: str
    search_query: str
    search_url: str | None = None
    avito_offers: list[AvitoPartOffer] = Field(default_factory=list)
    avito_min: int | None = None
    avito_max: int | None = None
    avito_median: int | None = None
    market_min: int | None = None
    market_max: int | None = None
    market_median: int | None = None
    market_sources: list[str] = Field(default_factory=list)
    estimate_min: int | None = None
    estimate_max: int | None = None
    estimate_median: int | None = None
    note: str = ""
    links_available: bool = False


class RepairLine(BaseModel):
    category: str
    description: str
    min_rub: int
    max_rub: int
    parts_hint: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    rationale: str | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    priority: RiskSeverityEnum | None = None
    action: str | None = None

    @model_validator(mode="after")
    def fill_precision_fields(self):
        if not self.evidence:
            self.evidence = [
                EvidenceItem(
                    source="analysis",
                    signal="repair_line",
                    details=self.description,
                )
            ]
        if not self.rationale:
            self.rationale = self.description
        if self.priority is None:
            if self.max_rub >= 150000:
                self.priority = RiskSeverityEnum.high
            elif self.max_rub >= 60000:
                self.priority = RiskSeverityEnum.medium
            else:
                self.priority = RiskSeverityEnum.low
        if self.confidence is None:
            self.confidence = 80 if self.max_rub > 0 else 55
        if not self.action:
            self.action = "Уточните дефект на диагностике и запросите смету у профильного сервиса"
        return self

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            return [{"source": "analysis", "signal": "legacy_text", "details": text}]
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            normalized: list[dict | EvidenceItem] = []
            for item in value:
                if isinstance(item, str):
                    txt = item.strip()
                    if txt:
                        normalized.append(
                            {"source": "analysis", "signal": "legacy_text", "details": txt}
                        )
                    continue
                if isinstance(item, dict):
                    normalized.append(item)
                    continue
                if isinstance(item, EvidenceItem):
                    normalized.append(item)
            return normalized
        return []


class ReplacementPartSuggestion(BaseModel):
    category: str
    part_name: str
    search_query: str
    search_url: str | None = None
    rationale: str
    availability: str = "unknown"
    offer_urls: list[str] = Field(default_factory=list)
    source_platforms: list[str] = Field(default_factory=list)
    price_range_rub: str | None = None
    suggested_actions: list[str] = Field(default_factory=list)
    confidence: int | None = Field(default=70, ge=0, le=100)
    priority: RiskSeverityEnum = RiskSeverityEnum.medium
    offer_cards: list[AvitoPartOffer] = Field(default_factory=list)
    price_min_rub: int | None = None
    price_max_rub: int | None = None
    marketplace_links: list[str] = Field(default_factory=list)


class ImageFinding(BaseModel):
    source: str
    zone: str | None = None
    issue: str
    confidence: ConfidenceEnum = ConfidenceEnum.medium
    rationale: str | None = None
    action: str | None = None


class MarketComparison(BaseModel):
    median_price: int
    sample_count: int
    delta_pct: float  # положительный = дороже рынка
    verdict: str  # "above_market" | "below_market" | "fair_price"
    comment: str
    search_url: str | None = None


class ResaleEconomics(BaseModel):
    purchase_price: int
    repair_mid: int
    target_resale: int | None
    estimated_margin: int | None
    margin_percent: float | None
    comment: str


class AnalysisReport(BaseModel):
    verdict: VerdictEnum
    final_recommendation: FinalRecommendationEnum
    verdict_label: str
    summary: str
    vehicle_passport_summary: str | None = None
    risk_score: int = Field(default=0, ge=0, le=100)
    risks: list[RiskItem]
    checklist: list[ChecklistItem]
    repair_lines: list[RepairLine]
    repair_total_min: int
    repair_total_max: int
    parts_pricing: list[PartPriceBlock] = Field(default_factory=list)
    resale: ResaleEconomics | None = None
    model_weak_points: list[str] = Field(default_factory=list)
    vin_summary: str | None = None
    listing_repairs: list[str] = Field(default_factory=list)
    preference_notes: list[str] = Field(default_factory=list)
    analysis_rationale: list[str] = Field(default_factory=list)
    replacement_suggestions: list[ReplacementPartSuggestion] = Field(default_factory=list)
    vehicle_passport: VehiclePassport = Field(default_factory=VehiclePassport)
    photo_findings: list[PhotoAnalysisFinding] = Field(default_factory=list)
    image_findings: list[ImageFinding] = Field(default_factory=list)
    negotiation_tips: list[str] = Field(default_factory=list)
    market_comparison: MarketComparison | None = None


def _validate_defect_photo_links(
    observed_defects: list[ObservedDefectInput],
    photos_metadata: list[PhotoMetadataInput],
) -> None:
    photo_count = len(photos_metadata)
    if photo_count == 0:
        if any(item.linked_photo_indexes for item in observed_defects):
            raise ValueError(
                "linked_photo_indexes require at least one item in photos_metadata"
            )
        return
    for item in observed_defects:
        for index in item.linked_photo_indexes:
            if index >= photo_count:
                raise ValueError(
                    "linked_photo_indexes contains out-of-range index for photos_metadata"
                )


class InspectionCreate(BaseModel):
    listing_url: str | None = None
    vehicle: VehicleInput | None = None
    user_preferences: str | None = None
    listing_repairs: str | None = None
    pre_defects: str | None = None
    observed_defects: list[ObservedDefectInput] = Field(default_factory=list)
    photos_metadata: list[PhotoMetadataInput] = Field(default_factory=list)
    is_reseller: bool = False
    target_resale_price: int | None = None
    require_avito_parse: bool = False

    @model_validator(mode="after")
    def validate_photo_links(self):
        _validate_defect_photo_links(self.observed_defects, self.photos_metadata)
        return self


class InspectionPostUpdate(BaseModel):
    post_defects: str | None = None
    post_notes: str | None = None
    observed_defects: list[ObservedDefectInput] = Field(default_factory=list)
    photos_metadata: list[PhotoMetadataInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_photo_links(self):
        _validate_defect_photo_links(self.observed_defects, self.photos_metadata)
        return self


class InspectionResponse(BaseModel):
    id: int
    stage: str
    listing_url: str | None
    brand: str | None
    model: str | None
    year: int | None
    mileage_km: int | None
    price_rub: int | None
    vin: str | None = None
    verdict: str | None
    final_recommendation: FinalRecommendationEnum | None = None
    pre_report: AnalysisReport | dict | None
    post_report: AnalysisReport | dict | None
    parts_pricing: list[PartPriceBlock] | dict | None = None
    observed_defects: list[ObservedDefectInput] = Field(default_factory=list)
    photos_metadata: list[PhotoMetadataInput] = Field(default_factory=list)
    repair_min_rub: int | None
    repair_max_rub: int | None
    post_notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    password_confirm: str

    @model_validator(mode='after')
    def passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError('Пароли не совпадают')
        return self


class LoginRequest(BaseModel):
    email: str
    password: str


class VerificationRequest(BaseModel):
    channel: str = "email"
    email: str | None = None
    phone_number: str | None = None


class VerificationConfirmRequest(BaseModel):
    code: str = Field(min_length=4, max_length=8)
    channel: str = "email"


class VerificationStatusResponse(BaseModel):
    email_verified: bool = False
    phone_verified: bool = False
    email_masked: str | None = None
    phone_masked: str | None = None


class VinCheckRequest(BaseModel):
    vin: str = Field(min_length=11, max_length=17)
    inspection_id: int | None = None


class VinCheckResponse(BaseModel):
    id: int
    vin: str
    summary: str | None
    report_uid: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VinCheckTaskCreateResponse(BaseModel):
    task_id: str
    task: str = "vin_check"
    status: TaskStatusEnum = TaskStatusEnum.queued
    created_at: datetime


class TaskStatusResponse(BaseModel):
    task_id: str
    task: str
    status: TaskStatusEnum
    created_at: datetime | None = None
    updated_at: datetime | None = None
    result: dict | None = None
    error: str | None = None


class ParseListingRequest(BaseModel):
    url: HttpUrl | str


class ParseListingResponse(BaseModel):
    platform: str | None
    vehicle: VehicleInput
    raw_title: str | None = None
    parse_ok: bool = False
    parse_error: str | None = None
    parse_status: ParseListingStatusEnum | None = None
    parse_reason: str | None = None
    action_required: str | None = None
    listing_repairs: list[str] = Field(default_factory=list)
    photo_urls: list[str] = Field(default_factory=list)


class AvitoWarmupRequest(BaseModel):
    url: HttpUrl | str | None = None


class AvitoWarmupResponse(BaseModel):
    status: ParseListingStatusEnum
    reason: str
    action_required: str | None = None
    message: str | None = None
    attempts: int = 0
    diagnostics: dict | None = None


class InspectionComparisonItem(BaseModel):
    inspection_id: int
    label: str
    price_rub: int | None = None
    repair_mid_rub: int | None = None
    projected_total_rub: int | None = None
    final_recommendation: FinalRecommendationEnum | None = None
    verdict: str | None = None
    estimated_margin: int | None = None


class InspectionComparisonResponse(BaseModel):
    items: list[InspectionComparisonItem]


class AdminHealthResponse(BaseModel):
    ok: bool
    version: str
    app_version: str
    revision: str
    environment: str
    queue_enabled: bool
    queue_depth: int | None = None
    db_ok: bool = True


class AdminStatsResponse(BaseModel):
    users_total: int
    inspections_total: int
    payments_total: int
    succeeded_payments: int
    queue_depth: int | None = None


class AdminSupportStatusResponse(BaseModel):
    environment: str
    admin_auth_configured: bool
    rate_limit_enabled: bool
    trusted_proxy_hops: int
    trusted_proxy_cidrs: list[str]
    yookassa_enabled: bool
    autocode_enabled: bool
    queue_enabled: bool


# Auth schemas
class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


# Monitored listings schemas
class MonitoredListingCreate(BaseModel):
    url: str
    inspection_id: int | None = None


class MonitoredListingResponse(BaseModel):
    id: int
    url: str
    platform: str | None
    last_price: int | None
    last_status: str
    last_checked_at: datetime | None
    created_at: datetime
    is_active: bool
    inspection_id: int | None

    model_config = {"from_attributes": True}


class ListingChangeEventResponse(BaseModel):
    id: int
    monitored_listing_id: int
    change_type: str
    old_value: str | None
    new_value: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# Compare inspections schemas
class CompareRequest(BaseModel):
    inspection_ids: list[int] = Field(min_length=2, max_length=3)


class CompareItem(BaseModel):
    inspection_id: int
    label: str
    brand: str | None
    model: str | None
    year: int | None
    price_rub: int | None
    repair_min_rub: int | None
    repair_max_rub: int | None
    repair_mid_rub: int | None
    risk_score: int | None
    verdict: str | None
    final_recommendation: str | None




class CompareResult(BaseModel):
    items: list[CompareItem]
    winner_id: int | None
    winner_reason: str | None
