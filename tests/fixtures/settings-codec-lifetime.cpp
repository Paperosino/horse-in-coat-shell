#include "codecs.hpp"
#include <QCoreApplication>
#include <QJsonArray>
#include <thread>
#include <vector>
#include <cstdio>
#include <cstdlib>
using namespace hyprstack::settings;
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    const auto boolean = QMetaType::fromType<bool>();
    const auto text = QMetaType::fromType<QString>();
    const auto list = QMetaType::fromType<QList<qreal>>();
    const auto* expected = ValueCodec::codecFor(boolean);
    const auto* expectedUnion = ValueCodec::unionFor({boolean, text});
    const auto* expectedList = ValueCodec::codecFor(list);
    if (!expected || !expectedUnion || !expectedList) return 2;
    auto check = [&] {
        for (int i = 0; i < 1000; ++i) {
            if (ValueCodec::codecFor(boolean) != expected
                || ValueCodec::unionFor({boolean, text}) != expectedUnion
                || ValueCodec::codecFor(list) != expectedList) std::abort();
            const auto decoded = expectedList->decode(QJsonArray{1.0, 2.5});
            if (decoded.error || decoded.value.value<QList<qreal>>() != QList<qreal>{1.0, 2.5}) std::abort();
            const auto choice = expectedUnion->decode(QStringLiteral("value"));
            if (choice.error || choice.value.toString() != QStringLiteral("value")) std::abort();
        }
    };
    std::vector<std::thread> workers;
    for (int i = 0; i < (argc > 1 ? 1 : 8); ++i) workers.emplace_back(check);
    for (auto& worker : workers) worker.join();
    std::fprintf(stdout, "Codec identities and decode semantics preserved\n");
}
