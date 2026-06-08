cmake_minimum_required(VERSION 3.5)

project({{ project_name }} VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt{{ qt_major_version }} 5.14 REQUIRED COMPONENTS Widgets)

add_executable({{ executable_name }}
    src/main.cpp
    src/MainWindow.cpp
    src/MainWindow.h
)

target_link_libraries({{ executable_name }} PRIVATE Qt{{ qt_major_version }}::Widgets)
