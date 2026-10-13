#include <gtest/gtest.h>

#include <stdexcept>
#include <vector>

#include "aegis/order_book.hpp"

using aegis::OrderBook;
using aegis::Side;
using aegis::Trade;

TEST(OrderBook, EmptyBookHasNoPrices) {
    OrderBook book;
    EXPECT_FALSE(book.best_bid());
    EXPECT_FALSE(book.best_ask());
    EXPECT_EQ(book.order_count(), 0u);
}

TEST(OrderBook, RestingOrdersSetBestPricesAndDepth) {
    OrderBook book;
    EXPECT_TRUE(book.submit_limit(1, Side::Buy, 9900, 10).empty());
    book.submit_limit(2, Side::Buy, 9950, 5);
    book.submit_limit(3, Side::Buy, 9950, 7);
    book.submit_limit(4, Side::Sell, 10050, 4);
    EXPECT_EQ(book.best_bid(), 9950);
    EXPECT_EQ(book.best_ask(), 10050);
    EXPECT_EQ(book.depth_at(Side::Buy, 9950), 12);
    EXPECT_EQ(book.order_count(), 4u);
}

TEST(OrderBook, CrossingOrderTradesAtTheRestingPrice) {
    OrderBook book;
    book.submit_limit(1, Side::Sell, 10000, 10);
    const auto trades = book.submit_limit(2, Side::Buy, 10100, 4);  // willing to pay $101, pays $100
    ASSERT_EQ(trades.size(), 1u);
    EXPECT_EQ(trades[0], (Trade{1, 2, Side::Buy, 10000, 4}));
    EXPECT_EQ(book.depth_at(Side::Sell, 10000), 6);
    EXPECT_FALSE(book.best_bid());
}

TEST(OrderBook, BetterPricesFillFirst) {
    OrderBook book;
    book.submit_limit(1, Side::Sell, 10100, 5);
    book.submit_limit(2, Side::Sell, 10000, 5);
    const auto trades = book.submit_limit(3, Side::Buy, 10100, 7);
    const std::vector<Trade> expected{{2, 3, Side::Buy, 10000, 5}, {1, 3, Side::Buy, 10100, 2}};
    EXPECT_EQ(trades, expected);
    EXPECT_EQ(book.depth_at(Side::Sell, 10100), 3);
}

TEST(OrderBook, EarlierOrdersFillFirstAtTheSamePrice) {
    OrderBook book;
    book.submit_limit(1, Side::Sell, 10000, 5);
    book.submit_limit(2, Side::Sell, 10000, 5);
    const auto trades = book.submit_limit(3, Side::Buy, 10000, 6);
    const std::vector<Trade> expected{{1, 3, Side::Buy, 10000, 5}, {2, 3, Side::Buy, 10000, 1}};
    EXPECT_EQ(trades, expected);
    EXPECT_EQ(book.depth_at(Side::Sell, 10000), 4);
    EXPECT_EQ(book.order_count(), 1u);
}

TEST(OrderBook, UnfilledRemainderRestsAtTheLimitPrice) {
    OrderBook book;
    book.submit_limit(1, Side::Sell, 10000, 3);
    const auto trades = book.submit_limit(2, Side::Buy, 10050, 10);
    ASSERT_EQ(trades.size(), 1u);
    EXPECT_EQ(trades[0].quantity, 3);
    EXPECT_EQ(book.best_bid(), 10050);
    EXPECT_EQ(book.depth_at(Side::Buy, 10050), 7);
    EXPECT_FALSE(book.best_ask());
}

TEST(OrderBook, MarketOrderSweepsLevelsAndNeverRests) {
    OrderBook book;
    book.submit_limit(1, Side::Sell, 10000, 3);
    book.submit_limit(2, Side::Sell, 10100, 3);
    const auto trades = book.submit_market(3, Side::Buy, 10);
    const std::vector<Trade> expected{{1, 3, Side::Buy, 10000, 3}, {2, 3, Side::Buy, 10100, 3}};
    EXPECT_EQ(trades, expected);
    EXPECT_FALSE(book.best_bid());
    EXPECT_EQ(book.order_count(), 0u);
}

TEST(OrderBook, CancelRemovesOnlyThatOrder) {
    OrderBook book;
    book.submit_limit(1, Side::Buy, 9900, 5);
    book.submit_limit(2, Side::Buy, 9900, 5);
    EXPECT_TRUE(book.cancel(1));
    EXPECT_EQ(book.depth_at(Side::Buy, 9900), 5);
    EXPECT_FALSE(book.cancel(1));
    EXPECT_FALSE(book.cancel(999));
    const auto trades = book.submit_limit(3, Side::Sell, 9900, 5);
    ASSERT_EQ(trades.size(), 1u);
    EXPECT_EQ(trades[0].maker_id, 2u);
}

TEST(OrderBook, FilledOrdersCannotBeCancelled) {
    OrderBook book;
    book.submit_limit(1, Side::Sell, 10000, 5);
    book.submit_limit(2, Side::Buy, 10000, 5);
    EXPECT_FALSE(book.cancel(1));
    EXPECT_EQ(book.order_count(), 0u);
}

TEST(OrderBook, RejectsInvalidOrders) {
    OrderBook book;
    EXPECT_THROW(book.submit_limit(1, Side::Buy, 10000, 0), std::invalid_argument);
    EXPECT_THROW(book.submit_limit(1, Side::Buy, 0, 5), std::invalid_argument);
    book.submit_limit(1, Side::Buy, 10000, 5);
    EXPECT_THROW(book.submit_limit(1, Side::Sell, 10100, 5), std::invalid_argument);
}
