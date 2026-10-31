"""Initial persisted demo schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("cache_entries", sa.Column("id", sa.String(36), primary_key=True), sa.Column("namespace", sa.String(100), nullable=False), sa.Column("query", sa.Text(), nullable=False), sa.Column("normalized_query", sa.String(1000), nullable=False), sa.Column("response", sa.Text(), nullable=False), sa.Column("embedding", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("invalidated", sa.Boolean(), nullable=False))
    op.create_index("ix_cache_entries_namespace", "cache_entries", ["namespace"])
    op.create_index("ix_cache_entries_normalized_query", "cache_entries", ["normalized_query"])
    op.create_index("ix_cache_entries_expires_at", "cache_entries", ["expires_at"])
    op.create_table("experiments", sa.Column("id", sa.String(36), primary_key=True), sa.Column("type", sa.String(40), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("configuration", sa.JSON(), nullable=False), sa.Column("dataset_ref", sa.String(200)), sa.Column("metrics", sa.JSON(), nullable=False), sa.Column("results", sa.JSON(), nullable=False), sa.Column("error", sa.Text()), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_experiments_type", "experiments", ["type"])
    op.create_index("ix_experiments_status", "experiments", ["status"])
    op.create_table("evaluation_records", sa.Column("id", sa.String(36), primary_key=True), sa.Column("prompt", sa.Text(), nullable=False), sa.Column("reference", sa.Text()), sa.Column("candidate", sa.Text(), nullable=False), sa.Column("scores", sa.JSON(), nullable=False), sa.Column("overall", sa.Float(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("security_records", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("cases", sa.Integer(), nullable=False), sa.Column("blocked", sa.Integer(), nullable=False), sa.Column("successful", sa.Integer(), nullable=False), sa.Column("results", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("security_records")
    op.drop_table("evaluation_records")
    op.drop_index("ix_experiments_status", table_name="experiments")
    op.drop_index("ix_experiments_type", table_name="experiments")
    op.drop_table("experiments")
    op.drop_index("ix_cache_entries_expires_at", table_name="cache_entries")
    op.drop_index("ix_cache_entries_normalized_query", table_name="cache_entries")
    op.drop_index("ix_cache_entries_namespace", table_name="cache_entries")
    op.drop_table("cache_entries")
