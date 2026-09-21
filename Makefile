# Hippotizer mask tools -- plain C++17, no external dependencies.
#   make            build every tool into build/
#   make test       build, then run the self-checks
#   make testset    regenerate testset/ (9 PNGs + Masks.xml)
#   make gui        launch the operator GUI (needs python3 with tkinter)
CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra
BUILD := build

COMMON := src/common/checksums.cpp
XML    := src/xml/xml_reader.cpp src/xml/xml_writer.cpp
PNG    := src/png/png_reader.cpp src/png/png_writer.cpp src/png/deflate.cpp
MODEL  := src/mask/mask_model.cpp src/mask/mask_space.cpp
RENDER := src/mask/mask_render.cpp
TRACE  := src/mask/mask_trace.cpp

TOOLS := png2mask mask2png mask_diff gen_testset bounds_report svg_export \
         xml_roundtrip_check png_roundtrip_check

.PHONY: all clean test testset gui
all: $(addprefix $(BUILD)/,$(TOOLS))

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/png2mask: tools/png2mask.cpp $(COMMON) $(XML) $(PNG) $(MODEL) $(TRACE) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/mask2png: tools/mask2png.cpp $(COMMON) $(XML) $(PNG) $(MODEL) $(RENDER) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/mask_diff: tools/mask_diff.cpp $(COMMON) $(PNG) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/gen_testset: tools/gen_testset.cpp $(COMMON) $(XML) $(PNG) $(MODEL) $(RENDER) $(TRACE) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/bounds_report: tools/bounds_report.cpp $(XML) $(MODEL) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/svg_export: tools/svg_export.cpp $(XML) $(MODEL) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/xml_roundtrip_check: tools/xml_roundtrip_check.cpp $(XML) $(MODEL) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/png_roundtrip_check: tools/png_roundtrip_check.cpp $(COMMON) $(PNG) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

test: all
	./tests/run_tests.sh

testset: $(BUILD)/gen_testset
	mkdir -p testset && ./$(BUILD)/gen_testset testset

gui:
	python3 gui/mask_gui.py

# The Python checks alone -- handy while working on the GUI, since they need
# no display and no tkinter.
.PHONY: test-gui
test-gui: all
	python3 tests/test_backend.py
	python3 tests/test_gui.py

clean:
	rm -rf $(BUILD)
