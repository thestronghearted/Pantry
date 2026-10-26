# Thin wrappers for Linux/macOS/CI. On Windows use `py scripts/dev.py <command>` directly.
PY ?= python3

up:
	$(PY) scripts/dev.py up

down:
	$(PY) scripts/dev.py down

test:
	$(PY) scripts/dev.py test

simulate-incident:
	$(PY) scripts/dev.py simulate-incident

.PHONY: up down test simulate-incident
