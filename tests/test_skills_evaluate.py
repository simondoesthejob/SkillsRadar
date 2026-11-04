import pytest

from skillsradar.skills.evaluate import Counts, evaluate, render_report
from skillsradar.skills.vocabulary import Skill, Vocabulary

VOCAB = Vocabulary(
    [
        Skill("Python", "language", ("python3",)),
        Skill("SQL", "language"),
        Skill("dbt", "data_platform"),
    ]
)


def posting(pid, source="reed", title="T"):
    return {"id": pid, "source": source, "title": title}


def label(*skills, status="done"):
    return {"status": status, "skills": list(skills)}


def run(postings, labels, predictions):
    return evaluate(postings, labels, lambda p: predictions[p["id"]], VOCAB)


def test_counts_and_scores():
    c = Counts(tp=6, fp=2, fn=4)
    assert c.precision == 0.75 and c.recall == 0.6
    assert c.f1 == pytest.approx(2 * 0.75 * 0.6 / 1.35)
    assert Counts().precision is None and Counts().f1 is None
    assert Counts(fp=3).f1 is None or Counts(fp=3).recall is None


def test_micro_scores_pool_all_postings():
    ev = run(
        [posting("a"), posting("b")],
        {"a": label("Python", "SQL"), "b": label("dbt")},
        {"a": ["Python", "dbt"], "b": ["dbt"]},
    )
    assert (ev.overall.tp, ev.overall.fp, ev.overall.fn) == (2, 1, 1)
    assert ev.postings == 2


def test_aliases_and_case_are_normalised_on_both_sides():
    ev = run([posting("a")], {"a": label("python3", "sql")}, {"a": ["Python", "SQL"]})
    assert (ev.overall.tp, ev.overall.fp, ev.overall.fn) == (2, 0, 0)


def test_skipped_and_unlabelled_postings_are_ignored():
    ev = run(
        [posting("a"), posting("b"), posting("c")],
        {"a": label(status="skip"), "b": label("Python")},
        {"a": ["Python"], "b": ["Python"], "c": ["Python"]},
    )
    assert ev.postings == 1


def test_a_labelled_posting_with_no_skills_counts_false_positives():
    ev = run([posting("a")], {"a": label()}, {"a": ["Python"]})
    assert (ev.overall.tp, ev.overall.fp, ev.overall.fn) == (0, 1, 0)


def test_vocabulary_gaps_are_separated_from_matching_misses():
    ev = run(
        [posting("a")],
        {"a": label("Python", "SQL", "DuckDB")},
        {"a": ["Python"]},
    )
    # overall recall counts the unknown skill; in-vocabulary recall does not
    assert ev.overall.recall == pytest.approx(1 / 3)
    assert ev.in_vocab.recall == pytest.approx(1 / 2)
    assert dict(ev.vocabulary_gaps) == {"DuckDB": 1}


def test_by_source_and_per_skill_breakdowns():
    ev = run(
        [posting("a", "reed"), posting("b", "hn_hiring")],
        {"a": label("Python"), "b": label("SQL")},
        {"a": ["Python", "dbt"], "b": []},
    )
    assert (ev.by_source["reed"].tp, ev.by_source["reed"].fp) == (1, 1)
    assert ev.by_source["hn_hiring"].fn == 1
    assert (ev.per_skill["dbt"].fp, ev.per_skill["SQL"].fn, ev.per_skill["Python"].tp) == (1, 1, 1)


def test_report_shows_error_detail_only_when_asked():
    ev = run([posting("a", title="Data Engineer")], {"a": label("Python")}, {"a": ["dbt"]})
    full = render_report(ev, "dev")
    assert "Data Engineer" in full and "missed: Python" in full and "extra: dbt" in full
    hidden = render_report(ev, "test", show_errors=False)
    assert "Data Engineer" not in hidden and "hidden for the test split" in hidden
    assert "All skills (micro)" in hidden
