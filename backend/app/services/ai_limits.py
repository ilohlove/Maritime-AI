"""Conservative durable token quota, rate limits and single-worker concurrency."""

from contextlib import contextmanager
from datetime import UTC, datetime
from threading import BoundedSemaphore

from sqlalchemy import text
from app.db.session import security_transaction
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
            with security_transaction(self.engine) as connection:
                connection.execute(
                    text(
                        "INSERT INTO ai_daily_usage(user_id,day,reserved_tokens,input_tokens,output_tokens,requests) VALUES (:user,:day,0,0,0,0) ON CONFLICT DO NOTHING"
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
        if self.settings.disposable_test_mode:
            raise WorkflowError(
                "disposable_ai_disabled",
                "Real inference is forbidden in disposable testing: quota state can reset. Use a durable, separately authorized API test environment.",
                403,
            )
        if self.settings.online_mvp_mode and not self.settings.ai_enabled:
            raise WorkflowError(
                "paid_inference_disabled",
                "Online inference is disabled by the backend administrator.",
                403,
            )
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

    def record_usage(self, user, model, usage):
        if (
            model not in self.settings.openai_models
            or not isinstance(usage, dict)
            or any(
                type(usage.get(key)) is not int or usage[key] < 0
                for key in ("input_tokens", "output_tokens")
            )
        ):
            raise WorkflowError(
                "usage_invalid",
                "Provider usage accounting is invalid; answer withheld.",
                502,
            )
        day = datetime.now(UTC).date().isoformat()
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO ai_daily_usage(user_id,day,reserved_tokens,input_tokens,output_tokens,requests) "
                        "VALUES (:user,:day,0,:input,:output,1) ON CONFLICT(user_id,day) DO UPDATE SET "
                        "input_tokens=ai_daily_usage.input_tokens+:input,output_tokens=ai_daily_usage.output_tokens+:output,requests=ai_daily_usage.requests+1"
                    ),
                    {
                        "user": user,
                        "day": day,
                        "input": usage["input_tokens"],
                        "output": usage["output_tokens"],
                    },
                )
        except SQLAlchemyError:
            raise WorkflowError(
                "usage_unavailable",
                "Cannot persist provider usage; answer withheld. Reserved quota remains charged.",
            ) from None

    def usage(self, user):
        from decimal import Decimal

        day = datetime.now(UTC).date().isoformat()
        try:
            with self.engine.connect() as connection:
                row = (
                    connection.execute(
                        text(
                            "SELECT reserved_tokens,input_tokens,output_tokens,requests FROM ai_daily_usage WHERE user_id=:user AND day=:day"
                        ),
                        {"user": user, "day": day},
                    )
                    .mappings()
                    .first()
                )
        except SQLAlchemyError:
            raise WorkflowError(
                "usage_unavailable", "Cannot read durable usage accounting."
            ) from None
        result = (
            dict(row)
            if row
            else {
                key: 0
                for key in (
                    "reserved_tokens",
                    "input_tokens",
                    "output_tokens",
                    "requests",
                )
            }
        )
        input_price = Decimal(self.settings.ai_input_usd_per_million)
        output_price = Decimal(self.settings.ai_output_usd_per_million)
        estimate = (
            result["input_tokens"] * input_price
            + result["output_tokens"] * output_price
        ) / Decimal(1000000)
        upper = (
            result["reserved_tokens"]
            * max(input_price, output_price)
            / Decimal(1000000)
        )
        return result | {
            "day": day,
            "daily_token_budget": self.settings.ai_daily_token_budget,
            "estimated_recorded_cost_usd": str(estimate),
            "reserved_cost_upper_bound_usd": str(upper),
            "pricing_model": self.settings.openai_model,
            "input_usd_per_million": str(input_price),
            "output_usd_per_million": str(output_price),
            "note": "Operator-configured estimates, not billing. Unknown/failed calls retain full quota reservation; usage may be unreported.",
        }
