PROBE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ROOT ?= $(CURDIR)
BUILD ?= $(ROOT)/native-build
CC := gcc
CFLAGS := -O0 -g -std=gnu11 -fno-omit-frame-pointer -ffunction-sections -fdata-sections
PCRE_STEMS := byte_order chartables compile config dfa_exec exec fullinfo get globals maketables newline ord2utf8 refcount string_utils study tables ucd valid_utf8 version xclass
PCRE_OBJECTS := $(addprefix $(BUILD)/pcre_,$(addsuffix .o,$(PCRE_STEMS)))
YAML_STEMS := api dumper emitter loader parser reader scanner writer
YAML_OBJECTS := $(addprefix $(BUILD)/yaml_,$(addsuffix .o,$(YAML_STEMS)))

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/pcre_%.o: $(ROOT)/pcre/pcre_%.c | $(BUILD)
	$(CC) $(CFLAGS) -DHAVE_CONFIG_H=1 -I$(ROOT)/pcre -c $< -o $@

$(BUILD)/yaml_%.o: $(ROOT)/libyaml/src/%.c | $(BUILD)
	$(CC) $(CFLAGS) -DYAML_VERSION_MAJOR=0 -DYAML_VERSION_MINOR=2 -DYAML_VERSION_PATCH=5 -DYAML_VERSION_STRING='"0.2.5"' -I$(ROOT)/libyaml/include -I$(ROOT)/libyaml/src -c $< -o $@

$(BUILD)/popt.o: $(ROOT)/rsync/popt/popt.c | $(BUILD)
	$(CC) $(CFLAGS) -DHAVE_STPCPY=1 -DHAVE_STRERROR=1 -I$(ROOT)/rsync/popt -c $< -o $@

$(BUILD)/bipbuffer.o: $(ROOT)/memcached/bipbuffer.c | $(BUILD)
	$(CC) $(CFLAGS) -I$(ROOT)/memcached -c $< -o $@

$(BUILD)/native_origin_probe: $(PCRE_OBJECTS) $(YAML_OBJECTS) $(BUILD)/popt.o $(BUILD)/bipbuffer.o $(PROBE_DIR)/native_origin_probe.c
	$(CC) $(CFLAGS) -I$(ROOT)/pcre -I$(ROOT)/rsync/popt -I$(ROOT)/libyaml/include -I$(ROOT)/memcached \
		$(PROBE_DIR)/native_origin_probe.c $(PCRE_OBJECTS) $(YAML_OBJECTS) $(BUILD)/popt.o $(BUILD)/bipbuffer.o \
		-Wl,--gc-sections -lm -o $@

.PHONY: all
all: $(BUILD)/native_origin_probe
