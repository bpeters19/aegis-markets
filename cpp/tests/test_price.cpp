#include <gtest/gtest.h>

#include <stdexcept>

#include "aegis/price.hpp"

using aegis::parse_price;

TEST(ParsePrice, ConvertsDecimalsToExactTicks) {
    EXPECT_EQ(parse_price("100.25"), 10025);
    EXPECT_EQ(parse_price("100.5"), 10050);
    EXPECT_EQ(parse_price("100"), 10000);
    EXPECT_EQ(parse_price("0.01"), 1);
}

TEST(ParsePrice, SupportsOtherTickSizes) {
    EXPECT_EQ(parse_price("1.2345", 4), 12345);
    EXPECT_EQ(parse_price("42", 0), 42);
}

TEST(ParsePrice, RejectsMoreThanOneTickOfPrecision) {
    EXPECT_THROW(parse_price("100.255"), std::invalid_argument);
}

TEST(ParsePrice, RejectsMalformedText) {
    for (const char* bad : {"", ".", "1.2.3", "-5", "12a", " 1"}) {
        EXPECT_THROW(parse_price(bad), std::invalid_argument) << "input: " << bad;
    }
}

TEST(ParsePrice, RejectsValuesThatDoNotFitIn64Bits) {
    EXPECT_THROW(parse_price("99999999999999999999"), std::out_of_range);
}

TEST(ParsePrice, TicksAreExactWhereFloatsAreNot) {
    // In binary floating point 0.1 + 0.2 is not exactly 0.3; integer ticks have no such problem.
    const double a = 0.1;
    const double b = 0.2;
    EXPECT_NE(a + b, 0.3);
    EXPECT_EQ(parse_price("0.10") + parse_price("0.20"), parse_price("0.30"));
}
