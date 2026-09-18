// ── أدوات مساعدة عامة ──
function toast(msg, isErr) {
  const t = document.getElementById('toast');
  if (!t) { alert(msg); return; }
  t.textContent = msg;
  t.className = 'toast show' + (isErr ? ' err' : '');
  clearTimeout(t._h);
  t._h = setTimeout(() => t.className = 'toast' + (isErr ? ' err' : ''), 4200);
}

async function api(url, data, method) {
  const opts = { method: method || (data ? 'POST' : 'GET') };
  if (data instanceof FormData) {
    opts.body = data;
  } else if (data) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(data);
  }
  const res = await fetch(url, opts);
  let json = {};
  try { json = await res.json(); } catch (e) { /* ignore */ }
  if (!res.ok || json.ok === false) {
    throw new Error(json.error || ('خطأ ' + res.status));
  }
  return json;
}

function confirmThen(msg, fn) {
  if (confirm(msg)) fn();
}

async function deleteRow(table, id, label) {
  // بوابة كلمة سر التحكم: تُطلب قبل الحذف إذا فُعّلت من «الإعدادات والأمان»
  let body = {};
  const sec = window.SECURITY || {};
  if (sec.protect_delete && sec.password_set) {
    const pw = prompt('🔒 هذا الإجراء محمي — أدخل كلمة سر التحكم:');
    if (pw === null) return;               // أُلغي الطلب
    body = { password: pw };
  }
  confirmThen(`هل تريد حذف ${label || 'هذا العنصر'}؟ لا يمكن التراجع.`, async () => {
    try {
      await api(`/api/${table}/${id}/delete`, body);
      toast('تم الحذف بنجاح');
      setTimeout(() => location.reload(), 400);
    } catch (e) { toast(e.message, true); }
  });
}

// طلب كلمة سر التحكم (تُستخدم للاستعادة/الحذف من النسخ الاحتياطية)
function askControlPassword() {
  const sec = window.SECURITY || {};
  if (!(sec.protect_restore && sec.password_set)) return '';
  const pw = prompt('🔒 هذا الإجراء محمي — أدخل كلمة سر التحكم:');
  if (pw === null) throw new Error('أُلغي الطلب');
  return pw;
}

// إرسال نموذج dialog إلى API ثم تحديث الصفحة
async function submitModal(formEl, url) {
  const btn = formEl.querySelector('button[type=submit]');
  if (btn) btn.disabled = true;
  try {
    await api(url, new FormData(formEl));
    toast('تم الحفظ بنجاح');
    setTimeout(() => location.reload(), 350);
    return true;
  } catch (e) {
    toast(e.message, true);
    if (btn) btn.disabled = false;
    return false;
  }
}

// فتح/إغلاق نوافذ الحوار <dialog> — مع معالجة أخطاء واضحة (لا يتوقف السكربت إن غاب العنصر)
function openDlg(id) {
  const dlg = document.getElementById(id);
  if (!dlg) {
    console.error('openDlg: لم يتم العثور على نافذة الحوار #' + id);
    alert('خطأ: تعذر العثور على نافذة الحوار (#' + id + ')');
    return;
  }
  if (dlg.open) return;                       // مفتوحة مسبقًا
  try {
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else { dlg.setAttribute('open', ''); dlg.style.display = 'block'; }
  } catch (e) {
    console.error('openDlg: تعذر فتح #' + id + ':', e);
    alert('تعذر فتح النافذة: ' + e.message);
  }
}

function closeDlg(id) {
  const dlg = document.getElementById(id);
  if (!dlg) {
    console.error('closeDlg: لم يتم العثور على نافذة الحوار #' + id);
    return;
  }
  try {
    if (typeof dlg.close === 'function' && dlg.open) dlg.close();
    else dlg.removeAttribute('open');
    dlg.style.display = '';
  } catch (e) { console.error('closeDlg: تعذر إغلاق #' + id + ':', e); }
}

// مراقبة عامة: أي خطأ JS أو وعد مرفوض يُطبع في وحدة تحكم المتصفح لتسهيل التشخيص
window.addEventListener('error', e => {
  console.error('[خطأ JS]', e.message, (e.filename || '') + ':' + (e.lineno || ''));
});
window.addEventListener('unhandledrejection', e => {
  console.error('[وعد مرفوض]', e.reason);
});

// ملء نموذج من صف جدول (سمات data-* على الزر)
function fillForm(dlgId, mapping, data) {
  const dlg = document.getElementById(dlgId);
  for (const [field, attr, cast] of mapping) {
    const el = dlg.querySelector(`[name=${field}]`);
    if (!el) continue;
    let v = data[attr] || '';
    if (cast === 'number') v = parseFloat(v) || 0;
    el.value = v;
  }
  openDlg(dlgId);
}
