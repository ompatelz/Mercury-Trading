cmake_minimum_required(VERSION 3.18)

project(mercury_native LANGUAGES CXX)

include(CTest)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_compile_options(-Wall -Wextra -Wpedantic)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

execute_process(
    COMMAND ${Python3_EXECUTABLE} -m pybind11 --cmakedir
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    COMMAND_ERROR_IS_FATAL ANY
)

list(APPEND CMAKE_PREFIX_PATH ${PYBIND11_CMAKE_DIR})
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_engine app/backtesting/native/engine.cpp)
set_target_properties(
    _engine
    PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/app/backtesting/native
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/app/backtesting/native
)

if(BUILD_TESTING)
    add_test(
        NAME native_execution_unit
        COMMAND ${Python3_EXECUTABLE} -m pytest tests/unit/test_native_backtesting.py
    )
    set_tests_properties(native_execution_unit PROPERTIES WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})
endif()
