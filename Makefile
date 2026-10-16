.PHONY: install lint test fmt tf-fmt

install:
	python3 -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff check --fix .
	ruff format .

test:
	pytest

tf-fmt:
	terraform fmt -recursive terraform
