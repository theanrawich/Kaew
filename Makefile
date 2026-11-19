ifeq ($(OS),Windows_NT)
PIO ?= pio
else
PIO ?= $(shell command -v pio 2>/dev/null || printf '%s' 'uv tool run --from platformio==6.1.19 pio')
endif

FIRMWARE_ENV := $(if $(filter node,$(MAKECMDGOALS)),sensor_node,gateway)

ifneq ($(filter gateway,$(MAKECMDGOALS)),)
ifneq ($(filter node,$(MAKECMDGOALS)),)
$(error Choose either gateway or node)
endif
endif

.PHONY: gateway node upload monitor

gateway:
ifeq ($(filter upload monitor,$(MAKECMDGOALS)),)
	$(PIO) run -d firmware -e gateway
endif

node:
ifeq ($(filter upload monitor,$(MAKECMDGOALS)),)
	$(PIO) run -d firmware -e sensor_node
endif

upload:
	$(PIO) run -d firmware -e $(FIRMWARE_ENV) -t upload $(if $(PORT),--upload-port "$(PORT)")

monitor:
	$(PIO) device monitor -d firmware -e $(FIRMWARE_ENV) $(if $(PORT),--port "$(PORT)")
