// จำลอง google.script.run ให้ index.html เดิมใช้งานได้โดยเรียก /api/* แทน
(function () {
  const YEAR = 2026;
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const ym = name => `${YEAR}-${String(MONTHS.indexOf(name) + 1).padStart(2, '0')}`;

  async function call(path, opt = {}) {
    let pw = localStorage.getItem('app_password') || '';
    for (let attempt = 0; attempt < 2; attempt++) {
      const res = await fetch(path, {
        ...opt,
        headers: { 'Content-Type': 'application/json', 'x-app-password': pw }
      });
      if (res.status === 401) {
        pw = prompt('กรอกรหัสผ่านเข้าใช้งาน') || '';
        localStorage.setItem('app_password', pw);
        continue;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }
    throw new Error('รหัสผ่านไม่ถูกต้อง');
  }

  async function getSheetData(sheetName) {
    const [data, dropdowns] = await Promise.all([
      call('/api/records?month=' + ym(sheetName)),
      call('/api/types')
    ]);
    return { data, currentSheet: sheetName, dropdowns };
  }

  const methods = {
    getMonthSheets: async () => MONTHS,
    getSheetData,
    saveRecord: async p => {
      await call('/api/records', { method: p.isEdit ? 'PUT' : 'POST', body: JSON.stringify(p) });
      return getSheetData(p.targetSheet);
    },
    deleteRecord: async (id, sheet) => {
      await call('/api/records?id=' + encodeURIComponent(id), { method: 'DELETE' });
      return getSheetData(sheet);
    },
    getAllSummary: () => call('/api/summary?year=' + YEAR)
  };

  function runner(ok = () => {}, fail = e => console.error(e)) {
    const r = {
      withSuccessHandler: f => runner(f, fail),
      withFailureHandler: f => runner(ok, f)
    };
    Object.keys(methods).forEach(k => {
      r[k] = (...args) => methods[k](...args).then(ok).catch(fail);
    });
    return r;
  }
  window.google = { script: { run: runner() } };
})();
