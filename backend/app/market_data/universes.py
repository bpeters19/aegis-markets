"""Named symbol universes for research. Prefer these over ad-hoc symbol lists."""

ETF_CORE = [
    # US equity
    "SPY", "QQQ", "IWM",
    # International equity
    "EFA", "EEM",
    # Real estate
    "VNQ",
    # US Treasuries: long, intermediate, short
    "TLT", "IEF", "SHY",
    # Credit and inflation-protected bonds
    "LQD", "HYG", "TIP",
    # Commodities and currency
    "GLD", "SLV", "DBC", "UUP",
]

UNIVERSES = {"etf_core": ETF_CORE}
