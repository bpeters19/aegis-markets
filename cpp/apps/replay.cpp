// Replays an order stream through the C++ book and writes every trade plus a final summary line,
// in the same format as tools/reference_book.py, for the differential test.
#include <exception>
#include <fstream>
#include <iostream>
#include <optional>
#include <string>

#include "stream.hpp"

namespace {
std::string show(const std::optional<aegis::Price>& price) {
    return price ? std::to_string(*price) : "-";
}
}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: aegis_replay <stream.csv> <trades.csv>\n";
        return 2;
    }
    try {
        const auto ops = aegis::apps::load_stream(argv[1]);
        aegis::OrderBook book;
        std::ofstream out(argv[2], std::ios::binary);
        for (const auto& op : ops) {
            for (const auto& t : aegis::apps::apply(book, op)) {
                out << t.maker_id << ',' << t.taker_id << ',' << (t.taker_side == aegis::Side::Buy ? 'B' : 'S') << ','
                    << t.price << ',' << t.quantity << '\n';
            }
        }
        out << "#summary," << book.order_count() << ',' << show(book.best_bid()) << ',' << show(book.best_ask())
            << '\n';
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
    return 0;
}
