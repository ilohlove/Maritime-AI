"""Conservative durable token quota, rate limits and single-worker concurrency."""

from contextlib import contextmanager
from datetime import UTC, datetime
from threading import BoundedSemaphore

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.services.auth import rate_limit
from app.services.document_ai import WorkflowError


class AIGuard:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.slots = BoundedSemaphore(settings.ai_concurrency)

    @property
    def reservation(self) -> int:
        # Reserve both maximum inputs and both bounded outputs, including the
        # translation call, before constructing a provider. Never refund failures.
        return (
            2 * self.settings.ai_max_input_tokens
            + self.settings.ai_output_tokens
            + self.settings.ai_translation_tokens
        )

    def reserve_budget(self, user: str):
        day = datetime.now(UTC).date().isoformat()
        try:
            with self.engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                connection.execute(
                    text(
                        "INSERT INTO ai_daily_usage(user_id,day,reserved_tokens) VALUES (:user,:day,0) ON CONFLICT DO NOTHING"
                    ),
                    {"user": user, "day": day},
                )
                changed = connection.execute(
                    text(
                        "UPDATE ai_daily_usage SET reserved_tokens=reserved_tokens+:amount WHERE user_id=:user AND day=:day AND reserved_tokens+:amount<=:budget"
                    ),
                    {
                        "user": user,
                        "day": day,
                        "amount": self.reservation,
                        "budget": self.settings.ai_daily_token_budget,
                    },
                ).rowcount
                if not changed:
                    connection.rollback()
                    raise WorkflowError(
                        "budget_exhausted",
                        "Daily application AI token allowance is exhausted. Try after UTC midnight or ask the administrator.",
                        429,
                    )
                connection.commit()
        except SQLAlchemyError:
            raise WorkflowError(
                "budget_unavailable",
                "Cannot enforce the AI budget; no inference was started.",
            ) from None

    @contextmanager
    def request(self, user: str):
        rate_limit(self.engine, "ai:" + user, self.settings.ai_rate_limit)
        if not self.slots.acquire(blocking=False):
            raise WorkflowError(
                "ai_busy",
                "AI concurrency limit reached. Wait for the current request to finish.",
                429,
            )
        try:
            self.reserve_budget(user)
            yield
        finally:
            self.slots.release()
