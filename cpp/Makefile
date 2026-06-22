# Makefile for the C++ Island-GA TSP solver (OpenMPI, C++17).
#
#   make          # build the MPI solver + sequential baseline
#   make test     # build and run the unit tests (no MPI needed)
#   make clean
#
# If mpicxx is not on PATH (e.g. a source build in /opt), point CXX at it:
#   make CXX=/opt/openmpi-5.0.9/bin/mpicxx
CXX      ?= mpicxx
CXXFLAGS ?= -O2 -std=c++17 -Wall

BINARIES := tsp_island tsp_sequential
TESTS    := test_ga_core test_local_search

all: $(BINARIES)

tsp_island: tsp_island.cpp ga_core.hpp local_search.hpp
	$(CXX) $(CXXFLAGS) -o $@ tsp_island.cpp

tsp_sequential: tsp_sequential.cpp ga_core.hpp
	$(CXX) $(CXXFLAGS) -o $@ tsp_sequential.cpp

# The unit tests do not use MPI, but mpicxx is just a g++ wrapper so it builds them fine.
test: $(TESTS)
	./test_ga_core && ./test_local_search

test_ga_core: test_ga_core.cpp ga_core.hpp
	$(CXX) $(CXXFLAGS) -o $@ test_ga_core.cpp

test_local_search: test_local_search.cpp ga_core.hpp local_search.hpp
	$(CXX) $(CXXFLAGS) -o $@ test_local_search.cpp

clean:
	rm -f $(BINARIES) $(TESTS)

.PHONY: all test clean
