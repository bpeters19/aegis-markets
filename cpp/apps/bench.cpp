// Benchmarks the C++ book: one pass for throughput (no per-operation timers),
// a second pass on a fresh book for per-operation latency percentiles.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <vector>

#include "stream.hpp"

using Clock = std::chrono::steady_clock;

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: aegis_bench <stream.csv>\n";
        return 2;
    }
    try {
        const auto ops = aegis::apps::load_stream(argv[1]);

        std::size_t trades = 0;
        double seconds = 0.0;
        {
            aegis::OrderBook book;
            const auto start = Clock::now();
            for (const auto& op : ops) {
                trades += aegis::apps::apply(book, op).size();
            }
            seconds = std::chrono::duration<double>(Clock::now() - start).count();
        }

        std::vector<std::int64_t> latencies;
        latencies.reserve(ops.size());
        {
            aegis::OrderBook book;
            for (const auto& op : ops) {
                const auto t0 = Clock::now();
                const auto result = aegis::apps::apply(book, op);
                const auto t1 = Clock::now();
                latencies.push_back(std::chrono::duration_cast<std::chrono::nanoseconds>(t1 - t0).count());
                static_cast<void>(result);
            }
        }
        std::sort(latencies.begin(), latencies.end());
        const auto pct = [&](double p) {
            const auto i = static_cast<std::size_t>(p * static_cast<double>(latencies.size()));
            return latencies[std::min(latencies.size() - 1, i)];
        };

        const double count = static_cast<double>(ops.size());
        std::cout << std::fixed << std::setprecision(3) << "c++ order book: " << ops.size() << " ops in " << seconds
                  << " s = " << std::setprecision(2) << count / seconds / 1e6 << " M ops/s | latency ns p50 "
                  << pct(0.50) << " p99 " << pct(0.99) << " p99.9 " << pct(0.999) << " max " << latencies.back()
                  << " | trades " << trades << '\n';
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
    return 0;
}
