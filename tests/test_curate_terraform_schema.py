"""The Glue table in Terraform must describe exactly the columns the curation code writes."""

import re
from pathlib import Path

from skillsradar.curate.schema import COLUMNS

MAIN = Path(__file__).parent.parent / "terraform" / "modules" / "analytics" / "main.tf"


def _terraform_columns() -> list[tuple[str, str]]:
    text = MAIN.read_text()
    block = text.split("curated_columns = [", 1)[1].split("\n  ]", 1)[0]
    return re.findall(r'name = "([^"]+)", type = "([^"]+)"', block)


def test_curated_columns_match_python_schema():
    assert _terraform_columns() == list(COLUMNS)
