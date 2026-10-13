#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <list>
#include <map>
#include <optional>
#include <unordered_map>
#include <vector>

#include "aegis/price.hpp"

namespace aegis {

using OrderId = std::uint64_t;

enum class Side { Buy, Sell };

// One execution: the resting order (maker) traded with the incoming order (taker) at the maker's price.
struct Trade {
    OrderId maker_id;
    OrderId taker_id;
    Side taker_side;
    Price price;
    Quantity quantity;

    bool operator==(const Trade&) const = default;
};

// Limit order book for one instrument with price-time priority.
class OrderBook {
public:
    // Matches against the opposite side up to `price`; any unfilled remainder rests in the book.
    std::vector<Trade> submit_limit(OrderId id, Side side, Price price, Quantity quantity);

    // Matches against the best available prices; any unfilled remainder is cancelled, never rests.
    std::vector<Trade> submit_market(OrderId id, Side side, Quantity quantity);

    // Removes a resting order. Returns false if the id is unknown or already fully filled.
    bool cancel(OrderId id);

    std::optional<Price> best_bid() const;
    std::optional<Price> best_ask() const;
    Quantity depth_at(Side side, Price price) const;
    std::size_t order_count() const { return index_.size(); }

private:
    struct RestingOrder {
        OrderId id;
        Quantity remaining;
    };
    struct Level {
        std::list<RestingOrder> orders;  // arrival order: front fills first
        Quantity total = 0;
    };
    struct Locator {
        Side side;
        Price price;
        std::list<RestingOrder>::iterator position;  // list iterators stay valid as other orders come and go
    };

    using Bids = std::map<Price, Level, std::greater<Price>>;  // highest bid first
    using Asks = std::map<Price, Level, std::less<Price>>;     // lowest ask first

    template <class Book, class Crosses>
    void match(Book& opposite, OrderId taker, Side taker_side, Quantity& remaining, Crosses crosses,
               std::vector<Trade>& trades);
    void rest(OrderId id, Side side, Price price, Quantity quantity);
    void validate_new(OrderId id, Quantity quantity) const;

    Bids bids_;
    Asks asks_;
    std::unordered_map<OrderId, Locator> index_;
};

}  // namespace aegis
