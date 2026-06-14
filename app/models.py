import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Make SQLAlchemy store enum .value ("free") not .name ("FREE")
_VAL = lambda obj: [e.value for e in obj]  # noqa: E731


class ListingStatus(str, enum.Enum):
    ACTIVE = "active"
    SOLD = "sold"
    REMOVED = "removed"


class ChangeType(str, enum.Enum):
    PRICE_DROP = "price_drop"
    PRICE_RISE = "price_rise"
    SOLD = "sold"
    REMOVED = "removed"


class Verdict(str, enum.Enum):
    WORTH_LOOKING = "worth_looking"
    CAUTION = "caution"
    SKIP = "skip"


class InspectionStage(str, enum.Enum):
    DRAFT = "draft"
    PRE_INSPECTION = "pre_inspection"
    POST_INSPECTION = "post_inspection"


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    PRO = "pro"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verification_code: Mapped[str | None] = mapped_column(String(16))
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_reset_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    session_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    session_issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    subscription_plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan, values_callable=_VAL), default=SubscriptionPlan.FREE
    )
    subscription_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    inspections_this_month: Mapped[int] = mapped_column(Integer, default=0)
    month_reset_key: Mapped[str | None] = mapped_column(String(7))
    vin_reports_this_month: Mapped[int] = mapped_column(Integer, default=0)
    report_credits: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    inspections: Mapped[list["Inspection"]] = relationship(back_populates="user")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    vin_checks: Mapped[list["VinCheck"]] = relationship(back_populates="user")
    monitored_listings: Mapped[list["MonitoredListing"]] = relationship(
        back_populates="user", foreign_keys="MonitoredListing.user_id"
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount_rub: Mapped[int] = mapped_column(Integer)
    plan: Mapped[SubscriptionPlan] = mapped_column(Enum(SubscriptionPlan, values_callable=_VAL))
    product: Mapped[str] = mapped_column(String(32), default="subscription")
    report_credits: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, values_callable=_VAL), default=PaymentStatus.PENDING
    )
    yookassa_payment_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="payments")


class ProcessedWebhookEvent(Base):
    __tablename__ = "processed_webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    event_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VinCheck(Base):
    __tablename__ = "vin_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey("inspections.id"), nullable=True)
    vin: Mapped[str] = mapped_column(String(32), index=True)
    report_uid: Mapped[str | None] = mapped_column(String(128))
    summary: Mapped[str | None] = mapped_column(Text)
    report_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="vin_checks")


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    stage: Mapped[InspectionStage] = mapped_column(
        Enum(InspectionStage, values_callable=_VAL), default=InspectionStage.DRAFT
    )

    listing_url: Mapped[str | None] = mapped_column(String(1024))
    platform: Mapped[str | None] = mapped_column(String(64))

    brand: Mapped[str | None] = mapped_column(String(128))
    model: Mapped[str | None] = mapped_column(String(128))
    year: Mapped[int | None] = mapped_column(Integer)
    mileage_km: Mapped[int | None] = mapped_column(Integer)
    price_rub: Mapped[int | None] = mapped_column(Integer)
    engine: Mapped[str | None] = mapped_column(String(256))
    transmission: Mapped[str | None] = mapped_column(String(128))
    drive: Mapped[str | None] = mapped_column(String(64))
    body_type: Mapped[str | None] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(64))
    vin: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)

    user_preferences: Mapped[str | None] = mapped_column(Text)
    listing_repairs: Mapped[str | None] = mapped_column(Text)
    pre_defects: Mapped[str | None] = mapped_column(Text)
    post_defects: Mapped[str | None] = mapped_column(Text)
    post_notes: Mapped[str | None] = mapped_column(Text)
    photo_paths: Mapped[list | None] = mapped_column(JSON, default=list)
    photos_metadata: Mapped[list | None] = mapped_column(JSON, default=list)
    observed_defects: Mapped[list | None] = mapped_column(JSON, default=list)

    is_reseller: Mapped[bool] = mapped_column(Boolean, default=False)
    target_resale_price: Mapped[int | None] = mapped_column(Integer)
    final_recommendation: Mapped[str | None] = mapped_column(String(32))

    verdict: Mapped[Verdict | None] = mapped_column(Enum(Verdict, values_callable=_VAL))
    pre_report: Mapped[dict | None] = mapped_column(JSON)
    post_report: Mapped[dict | None] = mapped_column(JSON)
    parts_pricing: Mapped[dict | None] = mapped_column(JSON)

    repair_min_rub: Mapped[int | None] = mapped_column(Integer)
    repair_max_rub: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="inspections")
    monitored_listings: Mapped[list["MonitoredListing"]] = relationship(
        back_populates="inspection", foreign_keys="MonitoredListing.inspection_id"
    )


class MonitoredListing(Base):
    __tablename__ = "monitored_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    inspection_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspections.id"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(String(1024))
    platform: Mapped[str | None] = mapped_column(String(64))
    last_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, values_callable=_VAL), default=ListingStatus.ACTIVE
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(
        back_populates="monitored_listings", foreign_keys=[user_id]
    )
    inspection: Mapped["Inspection | None"] = relationship(
        back_populates="monitored_listings", foreign_keys=[inspection_id]
    )
    events: Mapped[list["ListingChangeEvent"]] = relationship(back_populates="monitored_listing")


class ListingChangeEvent(Base):
    __tablename__ = "listing_change_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monitored_listing_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_listings.id"), index=True
    )
    change_type: Mapped[ChangeType] = mapped_column(Enum(ChangeType, values_callable=_VAL))
    old_value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    monitored_listing: Mapped["MonitoredListing"] = relationship(back_populates="events")
