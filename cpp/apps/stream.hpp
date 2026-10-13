#pragma once

#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "aegis/order_book.hpp"

namespace aegis::apps {

enum class OpType { Limit, Market, Cancel };

struct Op {
    OpType type;
    OrderId id;
    Side side;
    Price price;
    Quantity quantity;
};

inline std::vector<std::string> split(const std::string& line) {
    std::vector<std::string> parts;
    std::size_t start = 0;
    while (true) {
        const auto comma = line.find(',', start);
        parts.push_back(line.substr(start, comma - start));
        if (comma == std::string::npos) {
            break;
        }
        start = comma + 1;
    }
    return parts;
}

// Parses the whole stream up front so benchmarks time only the order book, never file reading.
inline std::vector<Op> load_stream(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("cannot open " + path);
    }
    std::vector<Op> ops;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) {
            continue;
        }
        const auto f = split(line);
        Op op{};
        op.id = std::stoull(f.at(1));
        const char type = f.at(0).at(0);
        if (type == 'C') {
            op.type = OpType::Cancel;
        } else {
            op.side = f.at(2).at(0) == 'B' ? Side::Buy : Side::Sell;
            if (type == 'L') {
                op.type = OpType::Limit;
                op.price = std::stoll(f.at(3));
                op.quantity = std::stoll(f.at(4));
            } else if (type == 'M') {
                op.type = OpType::Market;
                op.quantity = std::stoll(f.at(3));
            } else {
                throw std::runtime_error("unknown operation: " + line);
            }
        }
        ops.push_back(op);
    }
    return ops;
}

inline std::vector<Trade> apply(OrderBook& book, const Op& op) {
    switch (op.type) {
        case OpType::Limit:
            return book.submit_limit(op.id, op.side, op.price, op.quantity);
        case OpType::Market:
            return book.submit_market(op.id, op.side, op.quantity);
        case OpType::Cancel:
            book.cancel(op.id);
            return {};
    }
    return {};
}

}  // namespace aegis::apps
