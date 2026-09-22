# PNG -> Hippotizer mask. Plain C++17, no external dependencies.
#   make          build build/png2mask
#   make test     run the checks
#   make gui      open the window (needs no build -- it converts in Python)
CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra

.PHONY: all test gui clean
all: build/png2mask

build/png2mask: tools/png2mask.cpp src/common/checksums.cpp src/png/png_reader.cpp \
                src/mask/mask_model.cpp src/mask/mask_trace.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -o $@ $^

test: all
	./tests/run_tests.sh

# The window needs no build at all -- it converts in pure Python. This target
# is only here so `make gui` does what you would expect.
gui:
	python3 gui/mask_gui.py

clean:
	rm -rf build
