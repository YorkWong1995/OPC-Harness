#include "MainWindow.h"

#include <QLabel>
#include <QVBoxLayout>
#include <QWidget>

{{ class_name }}::{{ class_name }}(QWidget *parent)
    : QMainWindow(parent)
{
    auto *central = new QWidget(this);
    auto *layout = new QVBoxLayout(central);
    auto *label = new QLabel("{{ project_name }}", central);
    label->setAlignment(Qt::AlignCenter);
    layout->addWidget(label);
    setCentralWidget(central);
    setWindowTitle("{{ project_name }}");
}
