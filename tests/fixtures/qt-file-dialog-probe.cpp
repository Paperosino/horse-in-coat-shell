#include <QApplication>
#include <QFileDialog>
#include <QFileInfo>
#include <QTimer>
#include <QPalette>
#include <QStyleHints>
#include <QProcess>
#include <cstdio>
#include <gtk/gtk.h>

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    const QString path = QString::fromLocal8Bit(argv[1]);
    const QString operation = QString::fromLocal8Bit(argv[2]);
    QFileDialog dialog(nullptr, QStringLiteral("HICS file chooser"), QFileInfo(path).absolutePath());
    if (operation == "save") dialog.setAcceptMode(QFileDialog::AcceptSave);
    if (operation == "directory") dialog.setFileMode(QFileDialog::Directory);
    else dialog.setFileMode(operation == "save" ? QFileDialog::AnyFile : QFileDialog::ExistingFile);
    dialog.setNameFilters({QStringLiteral("Text files (*.txt)"), QStringLiteral("All files (*)")});
    dialog.selectFile(path);
    int attempts = 0;
    QTimer timer;
    QObject::connect(&timer, &QTimer::timeout, [&] {
        if (++attempts > 60) { std::fprintf(stderr, "No working native GTK chooser\n"); app.exit(2); return; }
        GList *windows = gtk_window_list_toplevels();
        for (GList *item = windows; item; item = item->next) {
            if (!GTK_IS_FILE_CHOOSER(item->data) || !gtk_widget_get_visible(GTK_WIDGET(item->data))) continue;
            if (attempts == 3 && !qEnvironmentVariableIsEmpty("HICS_TEST_CHOOSER_SCREENSHOT"))
                QProcess::execute(QStringLiteral("grim"), {qEnvironmentVariable("HICS_TEST_CHOOSER_SCREENSHOT")});
            auto *chooser = GTK_FILE_CHOOSER(item->data);
            if (operation == "cancel") gtk_dialog_response(GTK_DIALOG(item->data), GTK_RESPONSE_CANCEL);
            else {
                if (operation == "directory") gtk_file_chooser_set_current_folder(chooser, path.toUtf8().constData());
                else if (operation == "save") gtk_file_chooser_set_current_name(chooser, QFileInfo(path).fileName().toUtf8().constData());
                else gtk_file_chooser_set_filename(chooser, path.toUtf8().constData());
                // Allow GTK's asynchronous folder/file model to settle.
                if (attempts < 4) continue;
                char *selected = gtk_file_chooser_get_filename(chooser);
                const bool ready = selected && QString::fromUtf8(selected) == path;
                g_free(selected);
                if (ready) gtk_dialog_response(GTK_DIALOG(item->data), GTK_RESPONSE_OK);
            }
        }
        g_list_free(windows);
    });
    QObject::connect(&dialog, &QFileDialog::finished, [&](int result) {
        timer.stop();
        const bool correct = operation == "cancel" ? result == QDialog::Rejected :
            result == QDialog::Accepted && dialog.selectedFiles() == QStringList{path};
        std::printf("NATIVE=%d WINDOW=%s RESULT=%d\n", correct,
            app.palette().color(QPalette::Window).name().toUtf8().constData(), result);
        app.exit(correct ? 0 : 3);
    });
    QTimer::singleShot(0, [&] { dialog.open(); timer.start(100); });
    return app.exec();
}
