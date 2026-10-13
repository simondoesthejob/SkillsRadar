import pytest

from skillsradar import handler
from skillsradar.config import DEFAULT_QUERIES, Settings
from skillsradar.handler import UnavailableSource, build_sources
from skillsradar.sources.adzuna import AdzunaSource
from skillsradar.sources.hn_hiring import HnWhoIsHiring
from skillsradar.sources.reed import ReedSource


def settings() -> Settings:
    return Settings(raw_bucket="b", adzuna_secret_arn="arn:adzuna", reed_secret_arn="arn:reed")


def fake_secrets(arn: str) -> dict:
    return {"arn:adzuna": {"app_id": "i", "app_key": "k"}, "arn:reed": {"api_key": "r"}}[arn]


def test_default_sources_are_built_in_order():
    built = list(build_sources(settings(), handler.ALL_SOURCES, fake_secrets))
    assert [type(s) for s in built] == [AdzunaSource, ReedSource, HnWhoIsHiring]


def test_only_requested_sources_are_built():
    built = list(build_sources(settings(), ["reed"], fake_secrets))
    assert [s.name for s in built] == ["reed"]


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="linkedin"):
        list(build_sources(settings(), ["linkedin"], fake_secrets))


def test_missing_secret_isolated_to_that_source():
    def secrets(arn: str) -> dict:
        if arn == "arn:reed":
            raise KeyError("secret not set")
        return fake_secrets(arn)

    built = list(build_sources(settings(), handler.ALL_SOURCES, secrets))
    assert [type(s) for s in built] == [AdzunaSource, UnavailableSource, HnWhoIsHiring]

    written = []
    summary = handler.run([built[1]], "bucket", lambda *a: written.append(a))
    assert "reed" in summary["errors"] and written == []


def test_reed_settings_from_env():
    s = Settings.from_env(
        {
            "RAW_BUCKET": "b",
            "REED_SECRET_ARN": "arn:reed",
            "REED_QUERIES": "mlops, data engineer",
            "REED_LOCATION": "Reading",
        }
    )
    assert s.reed_queries == ("mlops", "data engineer")
    assert s.reed_location == "Reading"
    assert Settings.from_env({"RAW_BUCKET": "b"}).reed_queries == DEFAULT_QUERIES
