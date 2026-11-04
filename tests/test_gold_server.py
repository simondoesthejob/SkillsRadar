import http.client
import json
import threading

import pytest

from skillsradar.gold.server import make_server
from skillsradar.gold.store import read_jsonl, write_jsonl
from skillsradar.skills.vocabulary import Skill, Vocabulary

ITEMS = [
    {"id": "reed:1", "source": "reed", "title": "Data Engineer", "description": "Python and dbt"},
    {"id": "reed:2", "source": "reed", "title": "Analyst", "description": "Excel"},
]
VOCAB = Vocabulary([Skill("Python", "language", ("python3",)), Skill("dbt", "data_platform")])


@pytest.fixture
def server(tmp_path):
    sample, labels = tmp_path / "sample.jsonl", tmp_path / "labels.jsonl"
    write_jsonl(sample, ITEMS)
    srv = make_server(sample, labels, VOCAB, port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv, labels
    srv.shutdown()
    srv.server_close()


def request(srv, method, path, body=None, headers=None):
    port = srv.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    payload = json.dumps(body) if body is not None else None
    conn.request(method, path, body=payload, headers=headers or {})
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, data


def test_page_and_state_are_served(server):
    srv, _ = server
    status, page = request(srv, "GET", "/")
    assert status == 200 and b"Skills Radar labeller" in page
    status, data = request(srv, "GET", "/api/state")
    state = json.loads(data)
    assert status == 200
    assert [i["id"] for i in state["items"]] == ["reed:1", "reed:2"]
    assert state["labels"] == {}
    assert state["vocabulary"][0] == {
        "name": "Python",
        "category": "language",
        "aliases": ["python3"],
    }


def test_saving_canonicalises_aliases_and_keeps_new_skills(server):
    srv, labels = server
    status, data = request(
        srv, "POST", "/api/label", {"id": "reed:1", "skills": ["python3", "Rustacean", "dbt"]}
    )
    saved = json.loads(data)
    assert status == 200
    assert saved["skills"] == ["Python", "Rustacean", "dbt"]
    assert read_jsonl(labels)[0]["skills"] == ["Python", "Rustacean", "dbt"]
    assert json.loads(request(srv, "GET", "/api/state")[1])["labels"]["reed:1"]["status"] == "done"


@pytest.mark.parametrize(
    "body",
    [
        {"id": "nope", "skills": []},
        {"id": "reed:1", "skills": "Python"},
        {"id": "reed:1", "skills": [1, 2]},
        {"id": "reed:1", "skills": [], "status": "maybe"},
        ["not", "an", "object"],
    ],
)
def test_bad_labels_are_rejected(server, body):
    srv, labels = server
    status, _ = request(srv, "POST", "/api/label", body)
    assert status == 400
    assert not labels.exists()


def test_requests_from_other_hosts_or_origins_are_refused(server):
    srv, labels = server
    assert request(srv, "GET", "/api/state", headers={"Host": "evil.example"})[0] == 403
    status, _ = request(
        srv, "POST", "/api/label", {"id": "reed:1", "skills": ["Python"]},
        headers={"Origin": "https://evil.example"},
    )  # fmt: skip
    assert status == 403
    assert not labels.exists()


def test_unknown_paths_and_a_missing_sample(server, tmp_path):
    srv, _ = server
    assert request(srv, "GET", "/nothing")[0] == 404
    with pytest.raises(FileNotFoundError, match="gold_sample"):
        make_server(tmp_path / "missing.jsonl", tmp_path / "l.jsonl", VOCAB, port=0)


def test_review_endpoints_respect_the_blind_test_split(tmp_path):
    from skillsradar.gold.split import split_of

    dev_id = next(f"r:{i}" for i in range(500) if split_of(f"r:{i}") == "dev")
    test_id = next(f"r:{i}" for i in range(500) if split_of(f"r:{i}") == "test")
    items = [
        {"id": dev_id, "source": "reed", "title": "T", "description": "Python and dbt"},
        {"id": test_id, "source": "reed", "title": "T", "description": "Python and dbt"},
    ]
    sample, labels = tmp_path / "s.jsonl", tmp_path / "l.jsonl"
    write_jsonl(sample, items)
    srv = make_server(sample, labels, VOCAB, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        status, data = request(srv, "GET", f"/api/review?id={dev_id}")
        assert json.loads(data)["available"] is False  # not labelled yet
        for pid in (dev_id, test_id):
            request(srv, "POST", "/api/label", {"id": pid, "skills": ["Python"]})
        status, data = request(srv, "GET", f"/api/review?id={dev_id}")
        review = json.loads(data)
        assert status == 200 and review["available"]
        assert [c["skill"] for c in review["candidates"]] == ["dbt"]
        blocked = json.loads(request(srv, "GET", f"/api/review?id={test_id}")[1])
        assert blocked["available"] is False and "blind" in blocked["reason"]
        assert [q["id"] for q in json.loads(request(srv, "GET", "/api/review_queue")[1])] == [
            dev_id
        ]
        status, data = request(
            srv,
            "POST",
            "/api/label",
            {
                "id": dev_id,
                "skills": ["Python", "dbt"],
                "rejected": [],
                "review_added": ["DBT"],
                "reviewed": True,
            },
        )
        saved = json.loads(data)
        assert status == 200 and saved["review_added"] == ["dbt"] and saved["reviewed"]
        assert json.loads(request(srv, "GET", "/api/review_queue")[1]) == []
        status, _ = request(
            srv, "POST", "/api/label", {"id": dev_id, "skills": [], "reviewed": "yes"}
        )
        assert status == 400
        assert request(srv, "GET", "/api/review?id=nope")[0] == 400
    finally:
        srv.shutdown()
        srv.server_close()
