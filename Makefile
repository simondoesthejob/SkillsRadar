.PHONY: install lint test fmt tf-fmt gold-sample label evaluate

install:
	python -m pip install -e ".[dev]"

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

gold-sample:
	python scripts/gold_sample.py

label:
	python scripts/label_server.py

evaluate:
	python scripts/evaluate_extractor.py
