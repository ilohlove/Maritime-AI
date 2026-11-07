"""Durable single-owner security state; session tokens are never stored raw."""

from sqlalchemy import String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[float]
    csrf_digest: Mapped[str] = mapped_column(String(64))
    credential_version: Mapped[str] = mapped_column(String(64))


class RateWindow(Base):
    __tablename__ = "rate_windows"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    window: Mapped[int]
    count: Mapped[int]


class DailyUsage(Base):
    __tablename__ = "ai_daily_usage"
    user_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )
    requests: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    reserved_tokens: Mapped[int]
