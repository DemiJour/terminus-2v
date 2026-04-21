add_library(plugin OBJECT plugin.cpp)
target_include_directories(plugin PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
