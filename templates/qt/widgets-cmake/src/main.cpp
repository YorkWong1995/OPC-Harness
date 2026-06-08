#include <QApplication>

#include "MainWindow.h"

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    {{ class_name }} window;
    window.resize(800, 600);
    window.show();
    return app.exec();
}
