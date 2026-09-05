from datetime import date, timedelta

import pytest

from app.application.profiles import AudienceProfile, DenominationProfile, SermonFormatProfile, select_profiles, select_request_profiles


def _profiles():
    return (
        DenominationProfile("presbyterian_reformed_kr", "장로교·개혁", 1, date.today(), source_refs=("doctrine:denominations",)),
        AudienceProfile("adult", "중년장년", 1, date.today(), "standard", target_minutes=(20, 30)),
        SermonFormatProfile("expository", "강해설교", 1, date.today(), required_sections=("본문", "적용")),
    )


def test_profiles_are_independent_and_combinable():
    selected = select_profiles(*_profiles())
    assert selected.denomination.code != selected.audience.code
    assert selected.sermon_format.code == "expository"
    assert selected.warnings == ()


def test_profile_contract_rejects_future_effective_date():
    denomination, audience, sermon_format = _profiles()
    future = DenominationProfile(denomination.code, denomination.label, 1, date.today() + timedelta(days=1))
    with pytest.raises(ValueError, match="미래"):
        select_profiles(future, audience, sermon_format)


def test_profile_contract_does_not_require_a_new_denominations_table():
    denomination, _, _ = _profiles()
    assert denomination.source_refs == ("doctrine:denominations",)


def test_request_profile_adapter_reuses_existing_request_fields_without_persistence():
    class Request:
        tradition = "초교파 복음주의"
        denomination_code = ""
        audience = "청년"
        minutes = 20

    selected = select_request_profiles(Request())
    assert selected.denomination.code == "초교파 복음주의"
    assert selected.audience.code == "청년"
    assert selected.sermon_format.code == "expository"


def test_profile_versions_are_stable_and_snapshot_is_reproducible():
    selected = select_profiles(*_profiles())
    assert selected.profile_version_id == {
        "denomination": "denomination:presbyterian_reformed_kr:v1",
        "audience": "audience:adult:v1",
        "sermon_format": "format:expository:v1",
    }
    snapshot = selected.snapshot()
    assert snapshot["profile_version_id"] == selected.profile_version_id
    assert snapshot["denomination"]["source_refs"] == ["doctrine:denominations"]
    assert snapshot["audience"]["target_minutes"] == [20, 30]
