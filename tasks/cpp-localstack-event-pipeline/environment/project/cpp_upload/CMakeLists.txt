cmake_minimum_required(VERSION 3.16)
project(s3_put LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(CURL REQUIRED)

add_executable(s3_put src/main.cpp)
target_link_libraries(s3_put PRIVATE CURL::libcurl)
