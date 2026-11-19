ifeq ($(OS),Windows_NT)
PIO ?= pio
else
PIO ?= $(shell command -v pio 2>/dev/null || printf '%s' 'uv tool run --from platformio==6.1.19 pio')
endif

.PHONY: gateway upload monitor

gateway:
ifeq ($(filter upload monitor,$(MAKECMDGOALS)),)
	$(PIO) run -d firmware -e gateway
endif

upload:
	$(PIO) run -d firmware -e gateway -t upload $(if $(PORT),--upload-port "$(PORT)")

monitor:
	$(PIO) device monitor -d firmware -e gateway $(if $(PORT),--port "$(PORT)")
