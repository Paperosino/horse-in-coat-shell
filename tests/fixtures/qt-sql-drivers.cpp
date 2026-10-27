// Load every bundled SQL plugin without connecting to external databases.
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSqlDatabase>
#include <QSqlError>
#include <QSqlQuery>
#include <QTextStream>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (argc != 2) return 2;
    QCoreApplication::setLibraryPaths({QString::fromLocal8Bit(argv[1])});
    const QStringList expected{"QIBASE", "QMYSQL", "QODBC", "QPSQL", "QSQLITE"};
    QJsonArray loaded;
    for (const auto &name : expected) {
        bool valid = false;
        {
            auto db = QSqlDatabase::addDatabase(name, name);
            valid = db.isValid();
            if (valid && name == "QSQLITE") {
                db.setDatabaseName(":memory:");
                if (!db.open()) return 3;
                QSqlQuery query(db);
                if (!query.exec("CREATE VIRTUAL TABLE documents USING fts5(content)") ||
                    !query.exec("INSERT INTO documents VALUES ('hics runtime')") ||
                    !query.exec("SELECT content FROM documents WHERE documents MATCH 'runtime'") ||
                    !query.next() || query.value(0).toString() != "hics runtime") return 4;
            }
        }
        QSqlDatabase::removeDatabase(name);
        if (!valid) return 5;
        loaded.append(name);
    }
    QTextStream(stdout) << QJsonDocument(QJsonObject{{"loaded", loaded}, {"sqliteFts5", true},
        {"externalConnections", false}}).toJson(QJsonDocument::Compact) << Qt::endl;
}
