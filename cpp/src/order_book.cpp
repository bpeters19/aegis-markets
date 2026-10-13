#include "aegis/order_book.hpp"

#include <algorithm>
#include <iterator>
#include <stdexcept>

namespace aegis {

void OrderBook::validate_new(OrderId id, Quantity quantity) const {
    if (quantity <= 0) {
        throw std::invalid_argument("quantity must be positive");
    }
    if (index_.contains(id)) {
        throw std::invalid_argument("duplicate order id");
    }
}

template <class Book, class Crosses>
void OrderBook::match(Book& opposite, OrderId taker, Side taker_side, Quantity& remaining, Crosses crosses,
                      std::vector<Trade>& trades) {
    while (remaining > 0 && !opposite.empty()) {
        auto level_it = opposite.begin();  // best opposite price
        if (!crosses(level_it->first)) {
            break;
        }
        Level& level = level_it->second;
        while (remaining > 0 && !level.orders.empty()) {
            RestingOrder& maker = level.orders.front();  // earliest order at this price
            const Quantity fill = std::min(remaining, maker.remaining);
            trades.push_back(Trade{maker.id, taker, taker_side, level_it->first, fill});
            maker.remaining -= fill;
            level.total -= fill;
            remaining -= fill;
            if (maker.remaining == 0) {
                index_.erase(maker.id);
                level.orders.pop_front();
            }
        }
        if (level.orders.empty()) {
            opposite.erase(level_it);
        }
    }
}

void OrderBook::rest(OrderId id, Side side, Price price, Quantity quantity) {
    auto place = [&](auto& book) {
        Level& level = book[price];
        level.orders.push_back(RestingOrder{id, quantity});
        level.total += quantity;
        index_.emplace(id, Locator{side, price, std::prev(level.orders.end())});
    };
    if (side == Side::Buy) {
        place(bids_);
    } else {
        place(asks_);
    }
}

std::vector<Trade> OrderBook::submit_limit(OrderId id, Side side, Price price, Quantity quantity) {
    validate_new(id, quantity);
    if (price <= 0) {
        throw std::invalid_argument("price must be positive");
    }
    std::vector<Trade> trades;
    Quantity remaining = quantity;
    if (side == Side::Buy) {
        match(asks_, id, side, remaining, [price](Price ask) { return ask <= price; }, trades);
    } else {
        match(bids_, id, side, remaining, [price](Price bid) { return bid >= price; }, trades);
    }
    if (remaining > 0) {
        rest(id, side, price, remaining);
    }
    return trades;
}

std::vector<Trade> OrderBook::submit_market(OrderId id, Side side, Quantity quantity) {
    validate_new(id, quantity);
    std::vector<Trade> trades;
    Quantity remaining = quantity;
    const auto any_price = [](Price) { return true; };
    if (side == Side::Buy) {
        match(asks_, id, side, remaining, any_price, trades);
    } else {
        match(bids_, id, side, remaining, any_price, trades);
    }
    return trades;  // any unfilled remainder is dropped
}

bool OrderBook::cancel(OrderId id) {
    const auto found = index_.find(id);
    if (found == index_.end()) {
        return false;
    }
    const Locator locator = found->second;
    index_.erase(found);
    auto remove = [&](auto& book) {
        auto level_it = book.find(locator.price);
        level_it->second.total -= locator.position->remaining;
        level_it->second.orders.erase(locator.position);
        if (level_it->second.orders.empty()) {
            book.erase(level_it);
        }
    };
    if (locator.side == Side::Buy) {
        remove(bids_);
    } else {
        remove(asks_);
    }
    return true;
}

std::optional<Price> OrderBook::best_bid() const {
    if (bids_.empty()) {
        return std::nullopt;
    }
    return bids_.begin()->first;
}

std::optional<Price> OrderBook::best_ask() const {
    if (asks_.empty()) {
        return std::nullopt;
    }
    return asks_.begin()->first;
}

Quantity OrderBook::depth_at(Side side, Price price) const {
    auto lookup = [price](const auto& book) -> Quantity {
        const auto it = book.find(price);
        return it == book.end() ? 0 : it->second.total;
    };
    return side == Side::Buy ? lookup(bids_) : lookup(asks_);
}

}  // namespace aegis
