"""Straightforward Python order book with the same rules as the C++ one: price-time priority,
trades at the resting order's price, market orders never rest. Written to be obviously correct."""
from bisect import insort
from collections import deque


class ReferenceBook:
    def __init__(self) -> None:
        self.levels: dict[str, dict[int, deque]] = {"B": {}, "S": {}}
        self.prices: dict[str, list[int]] = {"B": [], "S": []}  # sorted ascending
        self.index: dict[int, tuple[str, int, list]] = {}

    def best(self, side: str) -> int | None:
        prices = self.prices[side]
        if not prices:
            return None
        return prices[-1] if side == "B" else prices[0]

    def _match(self, taker: int, side: str, remaining: int, limit: int | None):
        opposite = "S" if side == "B" else "B"
        trades = []
        while remaining > 0:
            price = self.best(opposite)
            if price is None:
                break
            if limit is not None and (price > limit if side == "B" else price < limit):
                break
            queue = self.levels[opposite][price]
            while remaining > 0 and queue:
                maker = queue[0]
                fill = min(remaining, maker[1])
                trades.append((maker[0], taker, side, price, fill))
                maker[1] -= fill
                remaining -= fill
                if maker[1] == 0:
                    queue.popleft()
                    del self.index[maker[0]]
            if not queue:
                del self.levels[opposite][price]
                self.prices[opposite].remove(price)
        return trades, remaining

    def limit(self, order_id: int, side: str, price: int, qty: int):
        trades, remaining = self._match(order_id, side, qty, price)
        if remaining > 0:
            levels = self.levels[side]
            if price not in levels:
                levels[price] = deque()
                insort(self.prices[side], price)
            entry = [order_id, remaining]
            levels[price].append(entry)
            self.index[order_id] = (side, price, entry)
        return trades

    def market(self, order_id: int, side: str, qty: int):
        return self._match(order_id, side, qty, None)[0]

    def cancel(self, order_id: int) -> bool:
        found = self.index.pop(order_id, None)
        if found is None:
            return False
        side, price, entry = found
        queue = self.levels[side][price]
        queue.remove(entry)
        if not queue:
            del self.levels[side][price]
            self.prices[side].remove(price)
        return True


def parse(lines: list[str]) -> list[tuple]:
    ops = []
    for line in lines:
        f = line.split(",")
        if f[0] == "C":
            ops.append(("C", int(f[1])))
        elif f[0] == "L":
            ops.append(("L", int(f[1]), f[2], int(f[3]), int(f[4])))
        else:
            ops.append(("M", int(f[1]), f[2], int(f[3])))
    return ops


def apply(book: ReferenceBook, op: tuple):
    if op[0] == "C":
        book.cancel(op[1])
        return []
    if op[0] == "L":
        return book.limit(op[1], op[2], op[3], op[4])
    return book.market(op[1], op[2], op[3])


def replay_lines(lines: list[str]) -> list[str]:
    """Trades as 'maker,taker,side,price,qty' plus a final summary line, matching the C++ replay tool."""
    book = ReferenceBook()
    out = []
    for op in parse(lines):
        out.extend(f"{m},{t},{s},{p},{q}" for m, t, s, p, q in apply(book, op))
    fmt = lambda v: "-" if v is None else str(v)
    out.append(f"#summary,{len(book.index)},{fmt(book.best('B'))},{fmt(book.best('S'))}")
    return out
