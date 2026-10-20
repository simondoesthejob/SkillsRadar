import pytest

from skillsradar.curate.hn import parse_header


@pytest.mark.parametrize(
    ("header", "location", "remote"),
    [
        ("Acme Ltd | Senior Python Engineer | London, UK | REMOTE | Visa", "London, UK", True),
        ("Acme | London | Hybrid | Full-time", "London", None),
        ("Acme | Remote (UK) | Data Scientist", "UK", True),
        ("Acme | Onsite | Berlin, Germany", "Berlin, Germany", False),
        ("Acme | Staff ML Engineer | Remote", None, True),
        ("Acme | £70k-£90k | Cambridge, UK", "Cambridge, UK", None),
        ("Acme | https://acme.example/jobs | Manchester", "Manchester", None),
        ("Just a sentence with no separators", None, None),
        ("", None, None),
    ],
)
def test_parse_header(header, location, remote):
    assert parse_header(header) == (location, remote)


def test_first_matching_place_wins():
    assert parse_header("Acme | London | Paris")[0] == "London"
