cmake_minimum_required(VERSION 3.8)
project(gr-custom_gfsk CXX C)

# Find GNU Radio
find_package(Gnuradio "3.8" REQUIRED)
find_package(Python3 COMPONENTS Interpreter REQUIRED)

# Try to find the correct python dist-packages install path
execute_process(COMMAND ${Python3_EXECUTABLE} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(plat_specific=True, prefix=''))"
                OUTPUT_VARIABLE PYTHON3_INSTDIR
                OUTPUT_STRIP_TRAILING_WHITESPACE)

if (NOT PYTHON3_INSTDIR)
    set(PYTHON3_INSTDIR "lib/python3/dist-packages")
endif()

# Install the Python module folder
install(DIRECTORY python/custom_gfsk
        DESTINATION ${CMAKE_INSTALL_PREFIX}/${PYTHON3_INSTDIR}
)

# Install the GRC blocks
install(FILES 
        grc/custom_gfsk_tx.block.yml
        grc/custom_gfsk_rx.block.yml
        grc/custom_gfsk_custom_file_source.block.yml
        grc/custom_gfsk_custom_file_sink.block.yml
        DESTINATION ${CMAKE_INSTALL_PREFIX}/share/gnuradio/grc/blocks
)

message(STATUS "Configured gr-custom_gfsk. Python install dir: ${PYTHON3_INSTDIR}")
