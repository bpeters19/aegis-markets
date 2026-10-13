#include "aegis/price.hpp"

#include <limits>
#include <stdexcept>
#include <string>

namespace aegis {

namespace {
constexpr Price kMax = std::numeric_limits<Price>::max();

[[noreturn]] void reject(std::string_view text, const char* why) {
    throw std::invalid_argument(std::string(why) + ": \"" + std::string(text) + "\"");
}
}  // namespace

Price parse_price(std::string_view text, int decimals) {
    if (decimals < 0 || decimals > 9) {
        throw std::invalid_argument("decimals must be between 0 and 9");
    }
    if (text.empty()) {
        reject(text, "empty price");
    }

    Price whole = 0;
    Price fraction = 0;
    int fraction_digits = 0;
    bool seen_dot = false;
    bool seen_digit = false;

    for (const char c : text) {
        if (c == '.') {
            if (seen_dot) {
                reject(text, "more than one decimal point");
            }
            seen_dot = true;
            continue;
        }
        if (c < '0' || c > '9') {
            reject(text, "invalid character in price");
        }
        seen_digit = true;
        const Price digit = c - '0';
        if (seen_dot) {
            if (++fraction_digits > decimals) {
                reject(text, "more precision than one tick");
            }
            fraction = fraction * 10 + digit;
        } else {
            if (whole > (kMax - digit) / 10) {
                throw std::out_of_range("price does not fit in 64 bits");
            }
            whole = whole * 10 + digit;
        }
    }
    if (!seen_digit) {
        reject(text, "no digits in price");
    }

    Price scale = 1;
    for (int i = 0; i < decimals; ++i) {
        scale *= 10;
    }
    for (int i = fraction_digits; i < decimals; ++i) {
        fraction *= 10;
    }
    if (whole > (kMax - fraction) / scale) {
        throw std::out_of_range("price does not fit in 64 bits");
    }
    return whole * scale + fraction;
}

}  // namespace aegis
