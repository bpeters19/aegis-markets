"""make paper_days append-only

Revision ID: c7d1a2b3e4f5
Revises: 0a6a12052037
"""
from alembic import op

revision = "c7d1a2b3e4f5"
down_revision = "0a6a12052037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION forbid_paper_day_changes() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'paper_days is append-only (% blocked)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER paper_days_no_update_delete
        BEFORE UPDATE OR DELETE ON paper_days
        FOR EACH ROW EXECUTE FUNCTION forbid_paper_day_changes();
        """
    )
    op.execute(
        """
        CREATE TRIGGER paper_days_no_truncate
        BEFORE TRUNCATE ON paper_days
        FOR EACH STATEMENT EXECUTE FUNCTION forbid_paper_day_changes();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS paper_days_no_truncate ON paper_days")
    op.execute("DROP TRIGGER IF EXISTS paper_days_no_update_delete ON paper_days")
    op.execute("DROP FUNCTION IF EXISTS forbid_paper_day_changes()")
