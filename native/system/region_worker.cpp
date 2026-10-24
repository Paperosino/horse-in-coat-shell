#include "backend.hpp"
#include <QCoreApplication>
#include <QTextStream>
#include <unistd.h>
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  try {
    const auto args = app.arguments();
    if (geteuid() != 0 || args.size() != 3 ||
        (args[2] != "all" && args[2] != "language"))
      throw System::Failure("denied", "A privileged locale worker is required");
    System::generateRegion(
        "locale", {{"locale", args[1]}, {"allFormats", args[2] == "all"}});
    return 0;
  } catch (const std::exception &error) {
    QTextStream(stderr) << error.what() << Qt::endl;
    return 1;
  }
}
