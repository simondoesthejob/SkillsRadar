import pytest

from skillsradar.skills.extractor import RulesExtractor

X = RulesExtractor()


def skills(text):
    return set(X.extract(text))


def test_names_and_aliases_are_found_whatever_the_case():
    assert skills("We use PYTHON, sql and Sklearn daily") == {"Python", "SQL", "scikit-learn"}
    assert skills("k8s and docker on aws") == {"Kubernetes", "Docker", "AWS"}


def test_order_of_first_appearance_and_no_repeats():
    assert X.extract("Terraform, then Python. More Python, and Terraform.") == [
        "Terraform",
        "Python",
    ]


def test_whole_words_only():
    assert skills("JavaScript developer") == {"JavaScript"}  # not Java
    assert skills("NoSQL stores") == set()  # not SQL
    assert skills("Pythonic style") == set()


def test_longest_match_wins():
    assert skills("T-SQL and PL/SQL") == {"T-SQL", "PL/SQL"}
    assert skills("Apache Spark on Databricks") == {"Apache Spark", "Databricks"}
    assert skills("AWS Lambda functions") == {"AWS Lambda"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("C++ and C# experience", {"C++", "C#"}),
        (".NET and Node.js", {".NET", "Node.js"}),
        ("CI/CD pipelines", {"CI/CD"}),
        ("A/B testing and experimentation", {"A/B testing"}),
        ("scikit-learn and scikit learn", {"scikit-learn"}),
        ("time-series forecasting", {"time series"}),
        ("Power  BI", {"Power BI"}),
    ],
)
def test_names_with_punctuation(text, expected):
    assert skills(text) == expected


def test_plurals():
    assert skills("large language models and microservice designs") == {"LLMs", "microservices"}
    assert "pandas" in skills("pandas")


def test_ambiguous_words_need_capitals_and_context():
    # a technical sentence: accepted
    assert "R" in skills("Experience with Python and R is essential")
    assert "Go" in skills("Backend development in Go or Rust")
    assert "Excel" in skills("Advanced Excel skills required")
    assert "Spark" not in skills("Apache Spark")  # the full name wins
    # ordinary English: rejected
    assert skills("We want you to go further and excel in a spring role") == set()
    assert skills("Spark curiosity and take the rest of the day off") == set()
    assert skills("R&D team") == set()
    assert skills("Grade C candidates") == set()


def test_ambiguous_word_in_lower_case_is_rejected_even_with_context():
    assert "R" not in skills("python and r programming")


def test_single_letters_work_at_the_start_and_end_of_the_text():
    assert X.extract("R programming") == ["R"]
    assert X.extract("Programming in R") == ["R"]
    assert X.extract("C++ programming") == ["C++"]


def test_context_word_alone_is_enough():
    assert X.extract("Proficiency in R") == ["R"]
    assert X.extract("R") == []  # no context at all


def test_matches_carry_positions_for_error_analysis():
    text = "Use Python daily"
    (match,) = X.find(text)
    assert (match.skill, match.start, match.end, match.text) == ("Python", 4, 10, "Python")


def test_empty_input():
    assert X.extract("") == [] and X.extract(None) == []


def test_every_vocabulary_name_finds_itself():
    """A safety net: a skill the extractor can never match is a vocabulary or rule bug."""
    missed = []
    for skill in X.vocab.skills:
        sentence = f"Experience with {skill.name} and Python is needed."
        if skill.name not in X.extract(sentence):
            missed.append(skill.name)
    assert not missed, missed
