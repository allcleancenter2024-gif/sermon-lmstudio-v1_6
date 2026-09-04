"""Versioned profile contracts for doctrine, audience, and sermon format.

Profiles are intentionally pure application data in this phase.  Existing
Doctrine tables remain the source for denomination identity and documents;
this module does not create a second denomination registry or database table.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class DenominationProfile:
    code: str
    label: str
    version: int
    effective_date: date
    primary_authorities: tuple[str, ...] = ()
    emphases: tuple[str, ...] = ()
    disputed_topics: tuple[str, ...] = ()
    validation_rules: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class AudienceProfile:
    code: str
    label: str
    version: int
    effective_date: date
    language_level: str
    application_domains: tuple[str, ...] = ()
    sensitive_topics: tuple[str, ...] = ()
    target_minutes: tuple[int, ...] = ()


@dataclass(frozen=True)
class SermonFormatProfile:
    code: str
    label: str
    version: int
    effective_date: date
    required_sections: tuple[str, ...] = ()
    optional_sections: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileSelection:
    denomination: DenominationProfile
    audience: AudienceProfile
    sermon_format: SermonFormatProfile
    warnings: tuple[str, ...] = field(default_factory=tuple)


def select_profiles(
    denomination: DenominationProfile,
    audience: AudienceProfile,
    sermon_format: SermonFormatProfile,
) -> ProfileSelection:
    """Validate and combine independent profiles without persisting them."""
    profiles = (denomination, audience, sermon_format)
    for profile in profiles:
        if not profile.code.strip() or not profile.label.strip():
            raise ValueError("프로필 code와 label은 비워 둘 수 없습니다.")
        if profile.version < 1:
            raise ValueError("프로필 version은 1 이상이어야 합니다.")
        if profile.effective_date > date.today():
            raise ValueError("프로필 적용일은 미래 날짜일 수 없습니다.")

    warnings: list[str] = []
    if audience.target_minutes and not set(audience.target_minutes).intersection({15, 20, 25, 30}):
        warnings.append("현재 지원되는 설교 시간(15·20·25·30분)과 일치하는 대상 시간이 없습니다.")
    return ProfileSelection(denomination, audience, sermon_format, tuple(warnings))
