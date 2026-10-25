#include <atomic>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <thread>
int main() {
    std::atomic<unsigned long long> value{0};
    std::thread worker([&] { for (int i=1; i<=100; ++i) value.fetch_add(i); });
    worker.join();
    if (value.load()!=5050 || !std::filesystem::exists("/proc/self/status")) return 1;
    auto stamp=std::chrono::steady_clock::now().time_since_epoch().count();
    if (stamp<=0) return 2;
    std::cout << "C++17 static musl: thread, 64-bit atomics, filesystem and clock OK; sum=" << value.load() << "\n";
}
