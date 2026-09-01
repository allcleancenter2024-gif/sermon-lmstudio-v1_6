from __future__ import annotations

from dataclasses import dataclass
import html
import re

@dataclass
class GroundingReportData:
    title: str; reference: str; audience: str; target_minutes: object; created_at: str; model: str; audit: dict; validator_summary: dict; evidence: list[dict]

def build_grounding_report_data(data: dict) -> GroundingReportData:
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else data
    audit = meta.get("grounding_audit") if isinstance(meta.get("grounding_audit"), dict) else {}
    evidence = data.get("sources") if isinstance(data.get("sources"), list) else meta.get("sources", [])
    return GroundingReportData(str(meta.get("topic") or "설교문"), str(meta.get("main_reference") or ""), str(meta.get("audience") or ""), meta.get("target_minutes", meta.get("minutes", "")), str(meta.get("created_at") or meta.get("generated_at") or ""), str(meta.get("model") or ""), audit, meta.get("grounding_summary") if isinstance(meta.get("grounding_summary"), dict) else {}, [dict(x) for x in evidence if isinstance(x, dict)])

def _label(status: str) -> str:
    return {"grounded":"✓ 근거 확인", "partially_grounded":"△ 부분 확인", "ungrounded":"! 확인 필요", "not_applicable":"검증 대상 아님"}.get(status, "확인 필요")

def render_grounding_markdown(r: GroundingReportData) -> str:
    a=r.audit; lines=["# Grounding 검토 보고서","","## 1. 설교 정보","",f"- 제목: {r.title}",f"- 중심본문: {r.reference or '기록 없음'}",f"- 대상: {r.audience or '기록 없음'}",f"- 목표 시간: {r.target_minutes or '기록 없음'}",f"- 생성일: {r.created_at or '기록 없음'}",f"- 모델: {r.model or '기록 없음'}","","## 2. 근거 검증 요약",""]
    lines += (["- 설교문 근거 검증: 사용 안 함 또는 기록 없음"] if not a else [f"- 근거 연결률: {round(float(a.get('grounding_coverage',0))*100)}%",f"- 근거 확인: {int(a.get('grounded',0))}",f"- 부분 확인: {int(a.get('partially_grounded',0))}",f"- 확인 필요: {int(a.get('ungrounded',0))}"])
    lines += ["","## 3. 검토가 필요한 주장",""]+[f"- **{_label(x.get('status',''))}** {x.get('reason','근거 확인 필요')}" for x in a.get('results',[]) if x.get('status') in {'ungrounded','partially_grounded'}]
    lines += ["","## 4. 전체 Claim 검증",""]+[f"- {_label(x.get('status',''))} · {x.get('reason','')}" for x in a.get('results',[])]
    lines += ["","## 5. Evidence Sources",""]+[f"- {x.get('source_type','unknown')} · {x.get('source_name') or x.get('translation') or '출처 미기록'} · {x.get('reference') or 'reference 없음'} · {re.sub(r'\s+',' ',str(x.get('text') or ''))[:180]}" for x in r.evidence[:30]]
    lines += ["","## 6. 목회자 검토 메모","","(검토자가 직접 기록)","","## 검토 안내","","이 보고서는 설교문과 등록 근거의 연결 상태를 검토하기 위한 보조자료이며, 최종 성경 해석이나 신학적 판단을 대신하지 않습니다."]
    return "\n".join(lines)+"\n"

def render_grounding_html(r: GroundingReportData) -> str:
    a=r.audit; summary="설교문 근거 검증: 사용 안 함 또는 기록 없음" if not a else f"근거 연결률: {round(float(a.get('grounding_coverage',0))*100)}% · ✓ 근거 확인 {int(a.get('grounded',0))} · △ 부분 확인 {int(a.get('partially_grounded',0))} · ! 확인 필요 {int(a.get('ungrounded',0))}"
    rows="".join(f"<tr><td>{html.escape(_label(x.get('status','')))}</td><td>{html.escape(str(x.get('reason','')))}</td></tr>" for x in a.get('results',[])[:50]) or "<tr><td colspan='2'>검증 기록 없음</td></tr>"
    ev="".join(f"<li>{html.escape(str(x.get('source_type','unknown')))} · {html.escape(str(x.get('source_name') or x.get('translation') or '출처 미기록'))} · {html.escape(str(x.get('reference') or 'reference 없음'))}<br><small>{html.escape(re.sub(r'\s+',' ',str(x.get('text') or ''))[:180])}</small></li>" for x in r.evidence[:30]) or "<li>Evidence 기록 없음</li>"
    return f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(r.title)} · Grounding 검토 보고서</title><style>body{{font-family:Arial,sans-serif;max-width:900px;margin:32px auto;padding:0 20px;color:#19241f;line-height:1.6}}h1,h2{{color:#245d50}}.summary{{padding:16px;background:#eef5f1;border-radius:10px}}table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #d9e2de;padding:8px;text-align:left}}@media print{{body{{margin:0}}}}</style></head><body><h1>Grounding 검토 보고서</h1><h2>1. 설교 기본정보</h2><p>제목: {html.escape(r.title)}<br>중심본문: {html.escape(r.reference or '기록 없음')}<br>대상: {html.escape(r.audience or '기록 없음')}<br>목표 시간: {html.escape(str(r.target_minutes or '기록 없음'))}<br>생성일: {html.escape(r.created_at or '기록 없음')}<br>모델: {html.escape(r.model or '기록 없음')}</p><h2>2. 근거 검증 요약</h2><div class='summary'>{html.escape(summary)}</div><h2>3. 검토가 필요한 주장 / 전체 Claim 검증</h2><table><tr><th>상태</th><th>판정 이유</th></tr>{rows}</table><h2>4. Evidence Sources</h2><ul>{ev}</ul><h2>5. 목회자 검토 메모</h2><p>(검토자가 직접 기록)</p><hr><p>이 보고서는 설교문과 등록 근거의 연결 상태를 검토하기 위한 보조자료이며, 최종 성경 해석이나 신학적 판단을 대신하지 않습니다.</p></body></html>"

def safe_report_stem(title: str, stamp: str) -> str:
    clean=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',title or '설교문').strip(' .')[:80] or '설교문'
    return f"grounding_report_{clean}_{stamp}"
