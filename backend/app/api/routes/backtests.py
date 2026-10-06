from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.backtest.metrics import CurveStats
from app.backtest.service import BacktestOutput, run_backtest
from app.database.session import get_session
from app.engine.feed import bar_from_record
from app.market_data.domain import Timeframe
from app.market_data.models import BarRecord
from app.market_data.repository import fetch_bars

router = APIRouter(tags=["backtests"])

MAX_SYMBOLS = 10
MAX_YEARS = 10
CENT = Decimal("0.01")
PRICE_STEP = Decimal("0.0001")


class SymbolInfo(BaseModel):
    symbol: str
    timeframe: str
    bars: int
    first: datetime
    last: datetime


class BacktestRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=MAX_SYMBOLS)
    start: date
    end: date
    fast: int = Field(10, ge=1)
    slow: int = Field(30, ge=2)
    capital: Decimal = Field(Decimal("100000"), gt=0)
    cash_rate: Decimal = Field(Decimal("0.02"), ge=0, le=Decimal("0.20"))
    benchmark: str = "SPY"

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(s.strip().upper() for s in value if s.strip()))
        if not cleaned:
            raise ValueError("at least one symbol is required")
        return cleaned

    @field_validator("benchmark")
    @classmethod
    def normalize_benchmark(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def check_ranges(self) -> "BacktestRequest":
        if self.fast >= self.slow:
            raise ValueError("fast window must be shorter than slow window")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        if (self.end - self.start).days > MAX_YEARS * 366:
            raise ValueError(f"period cannot exceed {MAX_YEARS} years")
        return self


class CurveMetrics(BaseModel):
    total_return: float
    cagr: float | None
    volatility: float | None
    sharpe: float | None
    sortino: float | None
    calmar: float | None
    max_drawdown: float
    drawdown_peak: date | None
    drawdown_trough: date | None
    drawdown_recovered: date | None
    drawdown_days: int


class RelativeMetrics(BaseModel):
    beta: float | None
    correlation: float | None
    alpha: float | None


class TradeSummary(BaseModel):
    count: int
    wins: int
    losses: int
    win_rate: float | None
    avg_win: float | None
    avg_loss: float | None
    payoff_ratio: float | None
    profit_factor: float | None
    expectancy: float | None
    avg_holding_days: float | None
    best_trade_share: float | None


class EquityPoint(BaseModel):
    date: date
    equity: Decimal
    benchmark: Decimal | None
    exposure: float


class TradeOut(BaseModel):
    symbol: str
    opened_at: datetime
    closed_at: datetime
    quantity: int
    avg_entry: Decimal
    avg_exit: Decimal
    net_pnl: Decimal
    exit_reason: str


class BacktestResponse(BaseModel):
    run_id: str
    params: BacktestRequest
    trading_days: int
    starting_value: Decimal
    strategy: CurveMetrics
    benchmark: CurveMetrics | None
    relative: RelativeMetrics
    trade_summary: TradeSummary
    counts: dict[str, int]
    open_positions: dict[str, int]
    equity_curve: list[EquityPoint]
    trades: list[TradeOut]


def curve_metrics(stats: CurveStats) -> CurveMetrics:
    dd = stats.drawdown
    return CurveMetrics(
        total_return=stats.total_return, cagr=stats.cagr, volatility=stats.volatility,
        sharpe=stats.sharpe, sortino=stats.sortino, calmar=stats.calmar,
        max_drawdown=dd.max_drawdown, drawdown_peak=dd.peak, drawdown_trough=dd.trough,
        drawdown_recovered=dd.recovered, drawdown_days=dd.duration_days,
    )


def to_response(out: BacktestOutput, request: BacktestRequest) -> BacktestResponse:
    bench_by_day = dict(out.benchmark_curve)
    exposure_by_day = dict(out.exposure)
    t = out.trade_summary
    return BacktestResponse(
        run_id=out.run_id,
        params=request,
        trading_days=len(out.curve),
        starting_value=out.starting_value.quantize(CENT),
        strategy=curve_metrics(out.strategy),
        benchmark=curve_metrics(out.benchmark) if out.benchmark else None,
        relative=RelativeMetrics(beta=out.relative.beta, correlation=out.relative.correlation, alpha=out.relative.alpha),
        trade_summary=TradeSummary(
            count=t.count, wins=t.wins, losses=t.losses, win_rate=t.win_rate, avg_win=t.avg_win,
            avg_loss=t.avg_loss, payoff_ratio=t.payoff_ratio, profit_factor=t.profit_factor,
            expectancy=t.expectancy, avg_holding_days=t.avg_holding_days, best_trade_share=t.best_trade_share,
        ),
        counts=out.counts,
        open_positions=out.open_positions,
        equity_curve=[
            EquityPoint(
                date=d,
                equity=v.quantize(CENT),
                benchmark=bench_by_day[d].quantize(CENT) if d in bench_by_day else None,
                exposure=float(exposure_by_day.get(d, 0)),
            )
            for d, v in out.curve
        ],
        trades=[
            TradeOut(
                symbol=tr.symbol, opened_at=tr.opened_at, closed_at=tr.closed_at, quantity=tr.quantity,
                avg_entry=tr.avg_entry.quantize(PRICE_STEP), avg_exit=tr.avg_exit.quantize(PRICE_STEP),
                net_pnl=tr.net_pnl.quantize(CENT), exit_reason=tr.exit_reason,
            )
            for tr in out.trades
        ],
    )


@router.get("/symbols", response_model=list[SymbolInfo])
def list_symbols(session: Session = Depends(get_session)) -> list[SymbolInfo]:
    rows = session.execute(
        select(BarRecord.symbol, BarRecord.timeframe, func.count(), func.min(BarRecord.ts), func.max(BarRecord.ts))
        .group_by(BarRecord.symbol, BarRecord.timeframe)
        .order_by(BarRecord.symbol)
    ).all()
    return [SymbolInfo(symbol=r[0], timeframe=r[1], bars=r[2], first=r[3], last=r[4]) for r in rows]


@router.post("/backtests", response_model=BacktestResponse)
def create_backtest(request: BacktestRequest, session: Session = Depends(get_session)) -> BacktestResponse:
    start = datetime.combine(request.start, time.min, tzinfo=timezone.utc)
    end = datetime.combine(request.end, time.min, tzinfo=timezone.utc)
    load_from = start - timedelta(days=400)

    def load(symbol: str):
        records = fetch_bars(session, symbol, Timeframe.DAY_1, load_from, end, limit=1_000_000)
        return [bar_from_record(r) for r in records]

    series = {}
    for symbol in request.symbols:
        bars = load(symbol)
        if not any(b.ts >= start for b in bars):
            raise HTTPException(422, f"No daily bars stored for {symbol} between {request.start} and {request.end}")
        series[symbol] = bars
    benchmark_bars = series.get(request.benchmark) or load(request.benchmark)

    out = run_backtest(
        series, benchmark_bars, request.fast, request.slow, start, end, request.capital, request.cash_rate,
    )
    return to_response(out, request)
