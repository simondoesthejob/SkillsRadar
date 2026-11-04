from skillsradar.gold.review import review_posting, review_queue
from skillsradar.gold.split import split_of
from skillsradar.gold.store import LabelStore
from skillsradar.skills.extractor import RulesExtractor
from skillsradar.skills.vocabulary import Skill, Vocabulary

VOCAB = Vocabulary(
    [
        Skill("Python", "language", ("python3",)),
        Skill("SQL", "language"),
        Skill("T-SQL", "language"),
        Skill("dbt", "data_platform"),
    ]
)
EXTRACTOR = RulesExtractor(VOCAB)


def item(pid="x:1", title="Data Engineer", description="You know Python, SQL and dbt."):
    return {"id": pid, "source": "reed", "title": title, "description": description}


def review(labelled, rejected=(), **kw):
    return review_posting(item(**kw), list(labelled), list(rejected), EXTRACTOR, VOCAB)


def test_only_disagreements_become_candidates():
    result = review(["Python"])
    assert [c["skill"] for c in result["candidates"]] == ["SQL", "dbt"]
    assert result["agreed"] == ["Python"]


def test_highlights_point_at_the_matched_text_in_the_right_field():
    result = review(["Python"], title="Python Developer")
    description = item()["description"]
    for h in result["highlights"]:
        text = "Python Developer" if h["field"] == "title" else description
        assert text[h["start"] : h["end"]].lower() == h["skill"].lower()
    assert {"title", "description"} == {h["field"] for h in result["highlights"]}
    first = result["candidates"][0]
    assert result["highlights"][first["first"]]["skill"] == first["skill"]


def test_candidate_count_and_rejected_flag():
    result = review(["Python"], rejected=["dbt"], description="SQL, SQL and dbt, plus Python")
    sql = next(c for c in result["candidates"] if c["skill"] == "SQL")
    dbt = next(c for c in result["candidates"] if c["skill"] == "dbt")
    assert sql["count"] == 2 and not sql["rejected"]
    assert dbt["rejected"]


def test_missed_skills_say_whether_the_vocabulary_knows_them():
    result = review(["Python", "DuckDB", "T-SQL"], description="Python and duckdb experience")
    missed = {m["skill"]: m for m in result["missed"]}
    assert set(missed) == {"DuckDB", "T-SQL"}
    assert missed["DuckDB"]["in_vocabulary"] is False and missed["DuckDB"]["occurrences"] == 1
    assert missed["T-SQL"]["in_vocabulary"] is True and missed["T-SQL"]["occurrences"] == 0
    kinds = {h["skill"]: h["kind"] for h in result["highlights"]}
    assert kinds["DuckDB"] == "missed"


def test_aliases_in_labels_count_as_the_same_skill():
    result = review(["python3", "sql", "DBT"])
    assert result["candidates"] == [] and result["missed"] == []


def ids_for(half, n=3):
    out, i = [], 0
    while len(out) < n:
        i += 1
        if split_of(f"x:{i}") == half:
            out.append(f"x:{i}")
    return out


def test_queue_is_dev_only_unreviewed_and_most_disagreement_first(tmp_path):
    dev1, dev2, dev3 = ids_for("dev")
    (test_id,) = ids_for("test", 1)
    items = [
        item(dev1, description="Python SQL dbt"),
        item(dev2, description="Python and SQL"),
        item(dev3, description="Python SQL dbt"),
        item(test_id, description="Python SQL dbt"),
    ]
    store = LabelStore(tmp_path / "labels.jsonl")
    for i in items:
        store.upsert(i["id"], ["Python"])
    store.upsert(dev3, ["Python"], reviewed=True)
    queue = review_queue(items, store.all(), EXTRACTOR, VOCAB)
    assert [q["id"] for q in queue] == [dev1, dev2]
    assert [q["candidates"] for q in queue] == [2, 1]


def test_queue_skips_unlabelled_and_skipped_postings(tmp_path):
    (dev1, dev2) = ids_for("dev", 2)
    items = [item(dev1), item(dev2)]
    store = LabelStore(tmp_path / "labels.jsonl")
    store.upsert(dev2, [], status="skip")
    assert review_queue(items, store.all(), EXTRACTOR, VOCAB) == []
