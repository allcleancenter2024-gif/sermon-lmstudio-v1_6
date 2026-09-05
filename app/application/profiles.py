"""Versioned profile contracts for doctrine, audience, and sermon format.

Profiles are intentionally pure application data in this phase.  Existing
Doctrine tables remain the source for denomination identity and documents;
this module does not create a second denomination registry or database table.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any


def _version_id(kind: str, code: str, version: int) -> str:
    return f"{kind}:{code}:v{version}"


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

    @property
    def version_id(self) -> str:
        return _version_id("denomination", self.code, self.version)


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

    @property
    def version_id(self) -> str:
        return _version_id("audience", self.code, self.version)


@dataclass(frozen=True)
class SermonFormatProfile:
    code: str
    label: str
    version: int
    effective_date: date
    required_sections: tuple[str, ...] = ()
    optional_sections: tuple[str, ...] = ()

    @property
    def version_id(self) -> str:
        return _version_id("format", self.code, self.version)


@dataclass(frozen=True)
class ProfileSelection:
    denomination: DenominationProfile
    audience: AudienceProfile
    sermon_format: SermonFormatProfile
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def profile_version_id(self) -> dict[str, str]:
        """Stable identifiers persisted with a sermon version.

        A profile edit must increment its version to produce a new identifier;
        this keeps old approved sermons reproducible without a new DB table.
        """
        return {
            "denomination": self.denomination.version_id,
            "audience": self.audience.version_id,
            "sermon_format": self.sermon_format.version_id,
        }

    def snapshot(self) -> dict[str, object]:
        """Return an immutable-at-save-time copy for historical reproduction."""
        return {
            "profile_version_id": dict(self.profile_version_id),
            "denomination": {
                "code": self.denomination.code,
                "label": self.denomination.label,
                "version": self.denomination.version,
                "effective_date": self.denomination.effective_date.isoformat(),
                "primary_authorities": list(self.denomination.primary_authorities),
                "emphases": list(self.denomination.emphases),
                "disputed_topics": list(self.denomination.disputed_topics),
                "validation_rules": list(self.denomination.validation_rules),
                "source_refs": list(self.denomination.source_refs),
            },
            "audience": {
                "code": self.audience.code,
                "label": self.audience.label,
                "version": self.audience.version,
                "effective_date": self.audience.effective_date.isoformat(),
                "language_level": self.audience.language_level,
                "application_domains": list(self.audience.application_domains),
                "sensitive_topics": list(self.audience.sensitive_topics),
                "target_minutes": list(self.audience.target_minutes),
            },
            "sermon_format": {
                "code": self.sermon_format.code,
                "label": self.sermon_format.label,
                "version": self.sermon_format.version,
                "effective_date": self.sermon_format.effective_date.isoformat(),
                "required_sections": list(self.sermon_format.required_sections),
                "optional_sections": list(self.sermon_format.optional_sections),
            },
        }


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
    if audience.target_minutes and not set(audience.target_minutes).intersection({15, 20, 25, 30, 40}):
        warnings.append("현재 지원되는 설교 시간(15·20·25·30·40분)과 일치하는 대상 시간이 없습니다.")
    return ProfileSelection(denomination, audience, sermon_format, tuple(warnings))


def select_request_profiles(data: Any) -> ProfileSelection:
    """Build the non-persistent profile selection for an existing sermon request.

    The HTTP request already owns these values, so this adapter deliberately
    does not introduce a second request model or a database registry.  Empty
    denomination codes continue to mean the existing tradition-only flow.
    """
    denomination_code = str(getattr(data, "denomination_code", "") or "").strip()
    tradition = str(getattr(data, "tradition", "초교파 복음주의") or "초교파 복음주의").strip()
    audience = str(getattr(data, "audience", "전 연령") or "전 연령").strip()
    sermon_format = str(getattr(data, "sermon_format", "expository") or "expository").strip()
    return select_profiles(
        DenominationProfile(
            code=denomination_code or tradition,
            label=tradition,
            version=1,
            effective_date=date.today(),
            source_refs=("doctrine:denominations",) if denomination_code else (),
        ),
        AudienceProfile(
            code=audience or "all",
            label=audience or "전 연령",
            version=1,
            effective_date=date.today(),
            language_level="standard",
            target_minutes=(int(getattr(data, "minutes", 15) or 15),),
        ),
        SermonFormatProfile(
            code=sermon_format or "expository",
            label="강해설교" if sermon_format == "expository" else sermon_format,
            version=1,
            effective_date=date.today(),
        ),
    )
