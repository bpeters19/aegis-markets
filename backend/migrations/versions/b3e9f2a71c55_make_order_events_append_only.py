"""make order_events append-only

Revision ID: b3e9f2a71c55
Revises: 085f19d9da69
"""
from alembic import op

revision = "b3e9f2a71c55"
down_revision = "085f19d9da69"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION forbid_order_event_changes() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'order_events is append-only (% blocked)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER order_events_no_update_delete
        BEFORE UPDATE OR DELETE ON order_events
        FOR EACH ROW EXECUTE FUNCTION forbid_order_event_changes();
        """
    )
    op.execute(
        """
        CREATE TRIGGER order_events_no_truncate
        BEFORE TRUNCATE ON order_events
        FOR EACH STATEMENT EXECUTE FUNCTION forbid_order_event_changes();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS order_events_no_truncate ON order_events")
    op.execute("DROP TRIGGER IF EXISTS order_events_no_update_delete ON order_events")
    op.execute("DROP FUNCTION IF EXISTS forbid_order_event_changes()")
