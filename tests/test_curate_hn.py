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
        ("Acme | Multiple Roles | Remote", None, True),
        ("Acme | multiple roles", None, None),
        ("Acme | Remote (listed here https://perfectwiki.page/p/iOeyfUha_9)", None, True),
        ("Acme | Engineer | U.S. Eastern/Central Time | Remote", None, True),
        ("Acme | GenAI Tooling & DevEx | London", "London", None),
        ("Acme | GMT+2 | Remote", None, True),
        ("Acme | Remote (US) | ML Engineer", "US", True),
        ("Acme | Hybrid | London", "London", None),
        ("Acme | HYBRID", None, None),
        ("Acme | bracehealth.com | Remote", None, True),
        ("Acme | U.S. citizenship required | Boston, MA", "Boston, MA", None),
        ("Acme | U.S. Citizenship Required", None, None),
        ("Just a sentence with no separators", None, None),
        ("", None, None),
    ],
)
def test_parse_header(header, location, remote):
    assert parse_header(header) == (location, remote)


def test_first_matching_place_wins():
    assert parse_header("Acme | London | Paris")[0] == "London"
