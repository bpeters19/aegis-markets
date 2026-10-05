"""Import every model module so Base.metadata knows about all tables (used by Alembic)."""
import app.market_data.models  # noqa: F401
import app.oms.models  # noqa: F401
