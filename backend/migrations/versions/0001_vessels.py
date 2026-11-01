"""Initial vessel profile schema. Migration intentionally independent of ORM metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vessels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vessel_name", sa.String(200), nullable=True),
        sa.Column("former_name", sa.String(200), nullable=True),
        sa.Column("imo_number", sa.String(200), nullable=True),
        sa.Column("mmsi", sa.String(200), nullable=True),
        sa.Column("call_sign", sa.String(200), nullable=True),
        sa.Column("flag", sa.String(200), nullable=True),
        sa.Column("port_of_registry", sa.String(200), nullable=True),
        sa.Column("vessel_type", sa.String(200), nullable=True),
        sa.Column("classification_society", sa.String(200), nullable=True),
        sa.Column("main_engine_manufacturer", sa.String(200), nullable=True),
        sa.Column("main_engine_model", sa.String(200), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("gross_tonnage", sa.Integer(), nullable=True),
        sa.Column("net_tonnage", sa.Integer(), nullable=True),
        sa.Column("length_overall", sa.Numeric(14, 3), nullable=True),
        sa.Column("length_between_perpendiculars", sa.Numeric(14, 3), nullable=True),
        sa.Column("breadth_moulded", sa.Numeric(14, 3), nullable=True),
        sa.Column("depth_moulded", sa.Numeric(14, 3), nullable=True),
        sa.Column("summer_draft", sa.Numeric(14, 3), nullable=True),
        sa.Column("summer_deadweight", sa.Numeric(14, 3), nullable=True),
        sa.Column("main_engine_power", sa.Numeric(14, 3), nullable=True),
        sa.Column("field_provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("vessels")
