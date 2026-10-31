"""Allow exact-only demo cache rows and mark embedding model provenance."""
from alembic import op
import sqlalchemy as sa


revision = "0002_provider_cache"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("cache_entries", "embedding", existing_type=sa.JSON(), nullable=True)
    op.add_column("cache_entries", sa.Column("embedding_model", sa.String(length=120), nullable=True))
    op.create_index("ix_cache_entries_embedding_model", "cache_entries", ["embedding_model"])


def downgrade():
    bind = op.get_bind()
    null_embeddings = bind.execute(sa.text("SELECT count(*) FROM cache_entries WHERE embedding IS NULL")).scalar_one()
    if null_embeddings:
        raise RuntimeError("Cannot downgrade: exact-only cache rows have no embeddings")
    op.drop_index("ix_cache_entries_embedding_model", table_name="cache_entries")
    op.drop_column("cache_entries", "embedding_model")
    op.alter_column("cache_entries", "embedding", existing_type=sa.JSON(), nullable=False)
