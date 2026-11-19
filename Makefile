ifeq ($(OS),Windows_NT)
PIO ?= pio
else
PIO ?= $(shell command -v pio 2>/dev/null || printf '%s' 'uv tool run --from platformio==6.1.19 pio')
endif

.PHONY: gateway upload monitor

gateway:
ifeq ($(filter upload monitor,$(MAKECMDGOALS)),)
	$(PIO) run -e gateway
endif

upload:
	$(PIO) run -e gateway -t upload $(if $(PORT),--upload-port "$(PORT)")

monitor:
	$(PIO) device monitor -e gateway $(if $(PORT),--port "$(PORT)")
