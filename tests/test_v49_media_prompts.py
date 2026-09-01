from pathlib import Path
from zipfile import ZipFile

from app.exporters import write_final_package
from app.media_prompts import build_media_prompt_packet, media_prompts_markdown


def test_media_prompt_packet_has_bilingual_prompts_for_three_sections():
    packet = build_media_prompt_packet(
        "## 서론\n불안한 현실을 봅니다.\n\n## 본론\n하나님이 함께하십니다.\n\n## 결론\n믿음으로 응답합시다.",
        [{"reference": "사 41:10", "translation": "WEB", "text": "두려워하지 말라"}],
    )
    assert packet["version"] == "media-prompts-v1"
    assert [item["key"] for item in packet["sections"]] == ["introduction", "body", "conclusion"]
    for section in packet["sections"]:
        assert section["biblical_references"] == "사 41:10 (WEB)"
        assert section["prompts"]["image"]["ko"]
        assert section["prompts"]["image"]["en"]


def test_final_package_contains_media_prompt_file(tmp_path: Path):
    packet = build_media_prompt_packet("## 서론\n본문을 소개합니다.", [{"reference": "요 3:16", "text": "사랑"}])
    output = tmp_path / "final.zip"
    manifest = write_final_package(output, sermon="## 서론\n본문을 소개합니다.", meta={"topic": "사랑", "media_prompts": packet}, sources=[], project={})
    assert "media_prompts.md" in manifest["files"]
    with ZipFile(output) as archive:
        content = archive.read("media_prompts.md").decode("utf-8")
    assert "참고 이미지" in content
    assert "English" in content
    assert media_prompts_markdown(packet).replace("\n", "\r\n") in content
