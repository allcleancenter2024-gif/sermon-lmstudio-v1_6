"""Bible-grounded prompts for optional sermon media assets.

The generator is deterministic and does not invent a new biblical claim. It
packages the verified sermon sections and registered evidence for a human or
an external media-generation tool to review.
"""

from __future__ import annotations

import re


SECTIONS = (
    ("introduction", "서론", "Introduction", "관심을 열고 본문의 질문과 현실의 문제를 연결"),
    ("body", "본론", "Main Point", "본문의 문맥과 핵심 복음 메시지를 설명하고 삶에 적용"),
    ("conclusion", "결론", "Conclusion", "본문의 핵심 진리를 요약하고 믿음의 응답과 실천으로 초대"),
)


def _clean(value: object, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _section_text(sermon: str, key: str) -> str:
    headings = {
        "introduction": r"(?:서론|도입|intro(?:duction)?)",
        "body": r"(?:본론|본문|main(?:\s+point)?|body)",
        "conclusion": r"(?:결론|맺음말|적용과 결론|conclusion|closing)",
    }
    pattern = re.compile(rf"(?:^|\n)\s*(?:#+\s*)?{headings[key]}\s*[:：]?\s*\n?", re.IGNORECASE)
    matches = list(pattern.finditer(sermon or ""))
    if matches:
        start = matches[0].end()
        next_match = re.search(r"\n\s*(?:#+\s*)?(?:서론|도입|본론|본문|결론|맺음말|적용과 결론|intro(?:duction)?|main(?:\s+point)?|body|conclusion|closing)\s*[:：]?", (sermon or "")[start:], re.IGNORECASE)
        end = start + next_match.start() if next_match else len(sermon or "")
        return _clean((sermon or "")[start:end])
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", sermon or "") if chunk.strip()]
    if not chunks:
        return ""
    index = {"introduction": 0, "body": len(chunks) // 2, "conclusion": max(0, len(chunks) - 1)}[key]
    return _clean(chunks[index])


def _evidence(passages: list[dict], word_notes: list[dict], doctrine_notes: list[dict]) -> tuple[str, str]:
    references = []
    excerpts = []
    for item in passages[:12]:
        reference = _clean(item.get("reference"), 120)
        translation = _clean(item.get("translation"), 80)
        text = _clean(item.get("text"), 260)
        if reference:
            references.append(f"{reference} ({translation})")
            if text:
                excerpts.append(f"{reference}: {text}")
    for item in word_notes[:6]:
        lemma = _clean(item.get("lemma"), 80)
        gloss = _clean(item.get("gloss"), 120)
        if lemma or gloss:
            excerpts.append(f"원어 {lemma}: {gloss}")
    for item in doctrine_notes[:6]:
        note = _clean(item.get("text") or item.get("content") or item.get("title"), 180)
        if note:
            excerpts.append(f"교리 참고: {note}")
    return "; ".join(references) or "등록된 성경 참조 없음", " | ".join(excerpts) or "등록된 근거 요약 없음"


def build_media_prompt_packet(
    sermon: str,
    passages: list[dict] | None = None,
    word_notes: list[dict] | None = None,
    doctrine_notes: list[dict] | None = None,
) -> dict:
    """Build reusable Korean/English anecdote, image, and video prompts."""
    references, evidence = _evidence(list(passages or []), list(word_notes or []), list(doctrine_notes or []))
    items = []
    for key, title, english_title, purpose in SECTIONS:
        section = _section_text(sermon, key) or "해당 부분의 설교문이 아직 확인되지 않음"
        korean_context = f"성경 근거: {references}\n근거 요약: {evidence}\n{title} 내용: {section}"
        english_context = f"Biblical references: {references}\nEvidence summary: {evidence}\n{english_title} content: {section}"
        items.append({
            "key": key,
            "title": title,
            "english_title": english_title,
            "section_text": section,
            "biblical_references": references,
            "evidence_summary": evidence,
            "purpose": purpose,
            "prompts": {
                "anecdote": {
                    "label": "예화",
                    "ko": f"다음 성경 근거와 {title}의 메시지를 정확히 반영하는 60~90초 예화를 제안하라.\n{korean_context}\n조건: 본문에 없는 사건·인물·직접 인용을 사실처럼 만들지 말고, 실화가 아니면 창작 예화라고 명시하라. 특정 집단을 희화화하지 말며 마지막에 본문의 핵심 진리와 자연스럽게 연결하라.",
                    "en": f"Propose a 60–90 second illustration that faithfully reflects the biblical evidence and the message of the {english_title}.\n{english_context}\nRequirements: Do not present an invented event, person, or quotation as factual. Label it as a fictional illustration when it is not verified. Avoid stereotyping any group, and end by connecting naturally to the central truth of the passage.",
                },
                "image": {
                    "label": "참고 이미지",
                    "ko": f"{title}의 성경적 메시지를 시각적으로 표현하는 참고 이미지 생성 프롬프트를 작성하라.\n{korean_context}\n스타일: 실제적인 다큐멘터리 사진 또는 절제된 시네마틱 장면, 따뜻하고 존엄한 인물 표현, 본문 시대·장소와 현대 적용을 혼동하지 않는 구도. 이미지 안에 글자·성경 구절·로고를 넣지 말고, 성경에 명시되지 않은 세부사항은 상징적으로 처리하라. 출력에는 장면 설명, 인물·행동, 조명·색감, 카메라 구도, 금지 요소를 포함하라.",
                    "en": f"Write a reference-image generation prompt that visually expresses the biblical message of the {english_title}.\n{english_context}\nStyle: a realistic documentary photograph or restrained cinematic scene, warm and dignified portrayal of people, and a composition that does not confuse the historical biblical setting with modern application. No text, Bible quotations, or logos in the image. Treat details not stated in Scripture symbolically. Include scene, subjects and action, lighting and color, camera composition, and exclusions.",
                },
                "video": {
                    "label": "참고 영상",
                    "ko": f"{title}의 성경 근거와 설교 메시지를 설명하는 30~60초 참고 영상 제작 프롬프트를 작성하라.\n{korean_context}\n구성: 0~5초 주의 환기, 5~20초 본문 맥락, 20~45초 핵심 메시지와 오늘의 적용, 마지막 5~10초 설교의 다음 문장으로 연결. 검증되지 않은 역사·고고학·간증을 사실처럼 말하지 말고, 화면 자막은 본문에 등록된 참조와 검토된 요약만 사용하라. 내레이션·장면 전환·음향·접근성 자막 지침을 포함하라.",
                    "en": f"Write a 30–60 second reference-video production prompt explaining the biblical evidence and sermon message of the {english_title}.\n{english_context}\nStructure: 0–5 seconds for attention, 5–20 seconds for textual context, 20–45 seconds for the central message and present-day application, and the final 5–10 seconds to bridge into the next sermon sentence. Do not state unverified history, archaeology, or testimony as fact. Use only registered references and reviewed summaries for on-screen text. Include narration, transitions, sound, and accessible-caption guidance.",
                },
            },
        })
    return {
        "version": "media-prompts-v1",
        "notice": "미디어 프롬프트는 등록된 성경 근거를 바탕으로 한 검토용 초안이며, 실제 제작 전 저작권·사실성·목회자 검토가 필요합니다.",
        "sections": items,
    }


def media_prompts_markdown(packet: dict | None) -> str:
    if not isinstance(packet, dict):
        return ""
    lines = ["## 성경 근거 미디어 프롬프트", "", packet.get("notice", ""), ""]
    for section in packet.get("sections", []):
        lines.extend([f"### {section.get('title')} / {section.get('english_title')}", "", f"근거 참조: {section.get('biblical_references', '')}", "", f"설교 부분: {section.get('section_text', '')}", ""])
        for kind in ("anecdote", "image", "video"):
            prompt = section.get("prompts", {}).get(kind, {})
            lines.extend([f"#### [{prompt.get('label', kind)}] 한국어", "", prompt.get("ko", ""), "", f"#### [{prompt.get('label', kind)}] English", "", prompt.get("en", ""), ""])
    return "\n".join(lines).strip() + "\n"
