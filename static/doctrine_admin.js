(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[<>"'&]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  async function loadDoctrineAdminDashboard() {
    const summary = $('doctrineAdminSummary'), status = $('doctrineAdminStatus');
    if (!summary || !status) return;
    try {
      const response = await fetch('/api/admin/doctrine/indexable', { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '관리자 상태 조회 실패');
      const items = data.items || [], documents = new Set(items.map((item) => item.document_id));
      summary.innerHTML = [['관리자', '권한 확인'], [items.length.toLocaleString(), '색인 대기 청크'], [documents.size.toLocaleString(), '승인 문서'], ['V2 격리', '기존 RAG 보존']]
        .map(([value, label]) => `<div><b>${esc(value)}</b><small>${esc(label)}</small></div>`).join('');
      status.className = 'import-status ' + (items.length ? 'warn' : 'ok');
      status.textContent = items.length ? `승인 후 색인 대기 · ${items.length.toLocaleString()}청크` : '승인되어 색인 대기 중인 교리 자료가 없습니다.';
    } catch (error) {
      summary.innerHTML = '<div><b>확인 불가</b><small>관리자 로그인 필요</small></div>';
      status.className = 'import-status warn'; status.textContent = error.message;
    }
  }

  async function reindexApprovedDoctrine() {
    const model = $('doctrineIndexModel').value.trim(), status = $('doctrineAdminStatus'), button = $('reindexApprovedDoctrine');
    if (!model) { status.className = 'import-status warn'; status.textContent = '재색인할 LM Studio 임베딩 모델명을 입력하세요.'; return; }
    button.disabled = true; status.className = 'import-status'; status.textContent = '승인된 교리 청크만 임베딩·색인하고 있습니다…';
    try {
      const response = await fetch('/api/admin/doctrine/reindex', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ model }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '교리 재색인 실패');
      status.className = 'import-status ok'; status.textContent = `교리 V2 재색인 완료 · ${Number(data.indexed || 0).toLocaleString()}청크 · ${Number(data.documents || 0)}문서`;
      await loadDoctrineAdminDashboard();
    } catch (error) { status.className = 'import-status bad'; status.textContent = '재색인 중단 · ' + error.message; }
    finally { button.disabled = false; }
  }

  async function reviewDoctrineLicense() {
    const sourceId = $('doctrineLicenseSourceId').value.trim(), reviewer = prompt('관리자 로그인 계정명을 입력하세요.');
    const status = $('doctrineAdminStatus');
    if (!sourceId || !reviewer) { status.className = 'import-status warn'; status.textContent = '자료원 ID와 관리자 검토자 계정이 필요합니다.'; return; }
    try {
      const response = await fetch(`/api/admin/doctrine/sources/${encodeURIComponent(sourceId)}/license-review`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({license_status:$('doctrineLicenseStatus').value, reviewer, permission_ref:$('doctrinePermissionRef').value.trim(), note:'관리자 대시보드에서 라이선스 검토 상태 기록'}) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || '라이선스 검토 저장 실패');
      status.className = 'import-status ok'; status.textContent = `라이선스 검토 저장 · ${data.license_status} · 자료원 ${data.source_id} · 활성 ${data.active ? '예' : '아니오'}`;
      await loadDoctrineAdminDashboard();
    } catch (error) { status.className = 'import-status bad'; status.textContent = '라이선스 검토 중단 · ' + error.message; }
  }

  // Existing request builders remain unchanged; add the optional code at the transport boundary.
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = String(input && input.url ? input.url : input || '');
    if (/\/api\/(sermons|research\/packet|preflight)$/.test(url) && init.body && $('denominationCode')) {
      try { const body = JSON.parse(init.body); body.denomination_code = $('denominationCode').value.trim(); init = {...init, body: JSON.stringify(body)}; } catch (_) { /* non-JSON request */ }
    }
    return originalFetch(input, init);
  };

  document.addEventListener('DOMContentLoaded', () => {
    if ($('refreshDoctrineAdmin')) $('refreshDoctrineAdmin').onclick = loadDoctrineAdminDashboard;
    if ($('reindexApprovedDoctrine')) $('reindexApprovedDoctrine').onclick = reindexApprovedDoctrine;
    if ($('reviewDoctrineLicense')) $('reviewDoctrineLicense').onclick = reviewDoctrineLicense;
    loadDoctrineAdminDashboard();
  });
})();
