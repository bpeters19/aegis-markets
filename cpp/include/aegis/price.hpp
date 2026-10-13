#pragma once

#include <cstdint>
#include <string_view>

namespace aegis {

// Prices are integer ticks, never floating point: with 2 decimals, 100.25 is stored as 10025.
using Price = std::int64_t;
using Quantity = std::int64_t;

// Parses a decimal price such as "100.25" into ticks with `decimals` places (2 means cents).
// Throws std::invalid_argument for malformed text or more precision than one tick,
// and std::out_of_range if the value does not fit in 64 bits.
Price parse_price(std::string_view text, int decimals = 2);

}  // namespace aegis
