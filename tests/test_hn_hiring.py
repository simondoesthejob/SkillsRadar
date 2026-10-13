from skillsradar.sources.hn_hiring import HnWhoIsHiring, html_to_text


def test_html_to_text_handles_paragraphs_entities_and_links():
    raw = 'Acme | Data Engineer | London<p>We use Python &amp; SQL. <a href="x">Apply</a>'
    assert html_to_text(raw) == "Acme | Data Engineer | London\nWe use Python & SQL. Apply"


def test_parse_extracts_company_and_skips_empty():
    comment = {
        "id": 42,
        "created_at_i": 1759300000,
        "text": "Acme | Data Engineer | London | REMOTE<p>Python, Terraform",
    }
    posting = HnWhoIsHiring.parse(comment)
    assert posting is not None
    assert posting.company == "Acme"
    assert posting.url.endswith("item?id=42")
    assert "Terraform" in posting.description
    assert HnWhoIsHiring.parse({"id": 43, "text": None}) is None


def test_fetch_only_uses_hiring_threads_and_limit():
    def fake_fetch(url, params=None):
        if url.endswith("/search_by_date"):
            return {
                "hits": [
                    {"objectID": "1", "title": "Ask HN: Who wants to be hired? (October 2026)"},
                    {"objectID": "2", "title": "Ask HN: Who is hiring? (October 2026)"},
                    {"objectID": "3", "title": "Ask HN: Who is hiring? (September 2026)"},
                ]
            }
        assert url.endswith("/items/2")  # newest hiring thread only
        return {"children": [{"id": 10, "text": "Beta | MLE | Remote"}, {"id": 11, "text": None}]}

    postings = list(HnWhoIsHiring(threads=1, fetch_json=fake_fetch).fetch())
    assert [p.source_id for p in postings] == ["10"]
