from app.application.section_registry import CANARY_SECTION_IDS, SectionRegistry, SectionSpec


class _Builder:
    def __init__(self, value, *, failure=None, validation=()):
        self.value = value
        self.failure = failure
        self.validation = tuple(validation)

    def build(self, context, evidence):
        assert context["reference"]
        assert evidence["source_ids"]
        if self.failure:
            raise self.failure
        return self.value

    def validate(self, result):
        return list(self.validation)

    def to_render_data(self, result):
        return {"value": result}


def test_canary_registry_has_deterministic_five_section_order():
    registry = SectionRegistry()
    assert tuple(spec.id for spec in registry.specs()) == CANARY_SECTION_IDS


def test_section_failure_isolated_from_other_builders():
    registry = SectionRegistry(
        specs=(SectionSpec("a", "A", 20), SectionSpec("b", "B", 30), SectionSpec("c", "C", 40)),
        builders={
            "a": _Builder("ready"),
            "b": _Builder(None, failure=RuntimeError("provider unavailable")),
            "c": _Builder("also ready"),
        },
    )

    results = registry.build({"reference": "요한복음 3:16"}, {"source_ids": ["s1"]})
    assert [(item.section_id, item.status) for item in results] == [("a", "ready"), ("b", "failed"), ("c", "ready")]
    assert "provider unavailable" in results[1].errors[0]


def test_unregistered_and_invalid_sections_are_explicit():
    registry = SectionRegistry(
        specs=(SectionSpec("missing", "누락", 20), SectionSpec("invalid", "검증실패", 30)),
        builders={"invalid": _Builder("payload", validation=("source coverage missing",))},
    )

    results = registry.build({"reference": "마태복음 5:3"}, {"source_ids": ["s1"]})
    assert results[0].status == "unregistered"
    assert results[1].status == "invalid"
    assert results[1].errors == ("source coverage missing",)
