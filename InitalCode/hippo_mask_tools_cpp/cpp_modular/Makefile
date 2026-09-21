CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra
BUILD := build

COMMON := common/checksums.cpp
XML := xml/xml_reader.cpp xml/xml_writer.cpp
PNG := png/png_reader.cpp png/png_writer.cpp
MASK := mask/mask_model.cpp mask/mask_render.cpp

TOOLS := mask2png svg_export bounds_report xml_roundtrip_check png_roundtrip_check

.PHONY: all clean
all: $(addprefix $(BUILD)/,$(TOOLS))

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/mask2png: tools/mask2png.cpp $(COMMON) $(XML) $(PNG) $(MASK) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/svg_export: tools/svg_export.cpp $(XML) $(MASK) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/bounds_report: tools/bounds_report.cpp $(XML) $(MASK) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/xml_roundtrip_check: tools/xml_roundtrip_check.cpp $(XML) $(MASK) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(BUILD)/png_roundtrip_check: tools/png_roundtrip_check.cpp $(COMMON) $(PNG) | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $^

clean:
	rm -rf $(BUILD)
