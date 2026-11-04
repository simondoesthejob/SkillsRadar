import json

import pytest

from skillsradar.skills import vocabulary
from skillsradar.skills.vocabulary import CATEGORIES, Skill, Vocabulary


def test_shipped_vocabulary_is_valid():
    vocab = vocabulary.load()  # raises if a name or alias is used twice
    assert len(vocab) > 150
    raw = json.loads(vocabulary.DEFAULT_PATH.read_text())
    assert {entry["category"] for entry in raw.values()} <= CATEGORIES


def test_names_and_aliases_resolve_case_insensitively():
    vocab = vocabulary.default()
    assert vocab.canonical("python") == "Python"
    assert vocab.canonical("  SKLEARN ") == "scikit-learn"
    assert vocab.canonical("k8s") == "Kubernetes"
    assert vocab.canonical("Power  BI") == "Power BI"
    assert vocab.canonical("not a real skill") is None
    assert "terraform" in vocab and "cobol" not in vocab


def test_a_name_used_twice_is_an_error():
    with pytest.raises(ValueError, match="both"):
        Vocabulary(
            [Skill("Spark", "data_platform", ("pyspark",)), Skill("PySpark", "data_platform")]
        )


def test_records_for_the_labelling_tool():
    vocab = Vocabulary([Skill("Go", "language", ("golang",))])
    assert vocab.to_records() == [{"name": "Go", "category": "language", "aliases": ["golang"]}]
