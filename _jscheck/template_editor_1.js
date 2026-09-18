
// ══════════ بيانات الصفحة ══════════
const B_TID = 1;
const ED_MODE = "visual";
let edMode = ED_MODE;

const B_COLORS = ['th_bg', 'th_color', 'alt_bg', 'border_color', 'header_color', 'body_color', 'total_color',
  'header_bg', 'company_color', 'meta_color', 'title_color', 'cust_card_bg', 'cust_color', 'row_color',
  'total_bg', 'total_label_bg', 'footer_bg', 'footer_color'];
const B_NUMS = ['th_size', 'border_width', 'cell_padding', 'header_size', 'body_size', 'total_size',
  'logo_size', 'company_size', 'meta_size', 'title_size', 'footer_size'];
const B_FLAGS = ['th_bold', 'header_bold', 'total_bold',
  'show_logo', 'show_company_tax', 'show_company_cr', 'show_company_addr',
  'show_cust_tax', 'show_cust_cr', 'show_cust_addr', 'show_cust_phone', 'show_footer'];
const B_SELECTS = ['logo_align'];
const B_TEXTS = ['footer_text', 'terms_text'];
let bTimer = null, bLastHtml = '', htmlDirty = false;

// ── مساعدات آمنة: تتحقق من وجود الحقل قبل التعيين فلا يتوقف السكربت أبدًا ──
function bEl(k) { return document.getElementById('b-' + k); }
function bSet(k, v) {
  const el = bEl(k);
  if (!el) { console.warn('المحرر المرئي: الحقل #b-' + k + ' غير موجود في الصفحة — تم تجاهله'); return; }
  el.value = v;
}
function bCheck(k, v) {
  const el = bEl(k);
  if (!el) { console.warn('المحرر المرئي: الحقل #b-' + k + ' غير موجود في الصفحة — تم تجاهله'); return; }
  el.checked = !!v;
}
function bRowInputs(row) {
  return { use: row.querySelector('.b-use'), color: row.querySelector('.b-color') };
}
function builderAuto() {
  const c = document.getElementById('b-auto');
  return !c || c.checked;   // التحديث التلقائي مفعّل افتراضيًا
}

function builderResetFields() {
  bSet('qr_position', 'below_totals');
  bSet('qr_size', 54);
  const qsv = document.getElementById('b-qr_size_val');
  if (qsv) qsv.textContent = '54';
  for (const k of B_NUMS) bSet(k, '');
  for (const k of B_FLAGS) bCheck(k, false);
  bSet('border_style', 'solid');
  for (const k of B_SELECTS) bSet(k, '');
  for (const k of B_TEXTS) bSet(k, '');
  for (const row of document.querySelectorAll('#tpleditor .b-crow')) {
    const { use, color } = bRowInputs(row);
    if (use) use.checked = false;
    if (color) color.value = '#0e7490';
  }
}

function builderApply(s) {
  s = s || {};
  const gp = bEl('qr_position');
  if (gp) {
    gp.value = s.qr_position || 'below_totals';
    if (gp.selectedIndex < 0) gp.value = 'below_totals';
  }
  bSet('qr_size', s.qr_size || 54);
  const qsv = document.getElementById('b-qr_size_val');
  const qs = bEl('qr_size');
  if (qsv && qs) qsv.textContent = qs.value;
  for (const k of B_NUMS) bSet(k, s[k] || '');
  for (const k of B_FLAGS) bCheck(k, s[k] === '1');
  const bs = bEl('border_style');
  if (bs) {
    bs.value = s.border_style || 'solid';
    if (bs.selectedIndex < 0) bs.value = 'solid';
  }
  for (const k of B_SELECTS) {
    const el = bEl(k);
    if (!el) continue;
    el.value = s[k] || '';
    if (el.selectedIndex < 0) el.value = '';
  }
  for (const k of B_TEXTS) bSet(k, s[k] || '');
  for (const row of document.querySelectorAll('#tpleditor .b-crow')) {
    const { use, color } = bRowInputs(row);
    if (!use || !color) continue;
    const k = row.dataset.k, v = (s[k] || '').trim();
    use.checked = !!v;
    if (v) color.value = v;
  }
}

function builderStyle() {
  const s = {
    qr_position: (bEl('qr_position') || {}).value || 'below_totals',
    qr_size: (bEl('qr_size') || {}).value || '54',
    border_style: (bEl('border_style') || {}).value || 'solid',
  };
  for (const k of B_NUMS) {
    const el = bEl(k);
    if (el) s[k] = el.value;
  }
  for (const k of B_FLAGS) {
    const el = bEl(k);
    if (el) s[k] = el.checked ? '1' : '';
  }
  for (const k of B_SELECTS) {
    const el = bEl(k);
    if (el) s[k] = el.value;
  }
  for (const k of B_TEXTS) {
    const el = bEl(k);
    if (el) s[k] = el.value.trim();
  }
  for (const row of document.querySelectorAll('#tpleditor .b-crow')) {
    const { use, color } = bRowInputs(row);
    if (!use || !color) continue;
    s[row.dataset.k] = use.checked ? color.value : '';
  }
  return s;
}

// ── المعاينة الحية (بنفس محرك الطباعة الفعلي) ──
async function builderRefresh() {
  const box = document.getElementById('b-prev-box');
  const frame = document.getElementById('b-frame');
  if (!box || !frame) { console.warn('المحرر المرئي: صندوق المعاينة غير موجود'); return; }
  box.style.opacity = '.55';
  try {
    const j = await api('/api/templates/' + B_TID + '/live-preview', { style: builderStyle() });
    if (!j.ok) throw new Error(j.error || 'خطأ في المعاينة');
    bLastHtml = j.html;
    frame.srcdoc = j.html;
  } catch (e) { toast(e.message, true); }
  finally { box.style.opacity = ''; }
}

function builderQueue() {
  if (!builderAuto()) return;                 // التحديث التلقائي متوقف — استخدم زر «تحديث المعاينة»
  clearTimeout(bTimer);
  bTimer = setTimeout(builderRefresh, 400);
}

async function builderSave() {
  try {
    const j = await api('/api/templates/' + B_TID + '/style', { style: builderStyle() });
    if (!j.ok) throw new Error(j.error || 'خطأ في الحفظ');
    toast('✅ تم حفظ تخصيصات القالب — تُطبق على كل الفواتير المطبوعة به');
    builderRefresh();
  } catch (e) { toast(e.message, true); }
}

function builderResetAll() {
  confirmThen('إرجاع كل التخصيصات إلى الوضع الافتراضي؟ (التغيير لا يُحفظ حتى تضغط «حفظ التخصيصات»)', () => {
    builderResetFields();
    builderQueue();
  });
}

function builderPrint() {
  if (!bLastHtml) { toast('لا توجد معاينة للطباعة بعد', true); return; }
  const w = window.open('', '_blank');
  if (!w) { toast('منع المتصفح فتح نافذة الطباعة', true); return; }
  w.document.open(); w.document.write(bLastHtml); w.document.close();
  w.addEventListener('load', () => setTimeout(() => w.print(), 400));
}

// ملاءمة ورقة A4 (794×1123px عند 96dpi) داخل صندوق المعاينة
function bFit() {
  const box = document.getElementById('b-prev-box'), hold = document.getElementById('b-holder');
  if (!box || !hold) return;
  const s = Math.min(1, (box.clientWidth - 24) / 794);
  hold.style.transform = 'scale(' + s + ')';
  hold.style.width = (794 * s) + 'px';
  hold.style.height = (1123 * s) + 'px';
}

// ── تهيئة المحرر المرئي: قراءة إعدادات القالب من السيرفر ثم معاينة ──
async function builderInit() {
  builderResetFields();
  bFit();
  try {
    const j = await api('/api/templates/' + B_TID + '/style');
    if (!j.ok) throw new Error(j.error || 'خطأ في قراءة الإعدادات');
    builderApply(j.style || {});
  } catch (e) { toast(e.message, true); }
  builderRefresh();
}

// ══════════ التبديل بين المحرر المرئي وتحرير HTML ══════════
function syncUrl(m) {
  // نُبقي تبويب HTML في العنوان حتى لا يُفقد بعد إعادة التحميل عند الحفظ
  const url = location.pathname + (m === 'html' ? '?tab=html' : '');
  try { history.replaceState(null, '', url); } catch (e) { /* ignore */ }
}

function setMode(m) {
  edMode = (m === 'html') ? 'html' : 'visual';
  document.querySelectorAll('#tpleditor .ed-mode').forEach(
    b => b.classList.toggle('active', b.dataset.mode === edMode));
  document.querySelectorAll('#tpleditor .ed-sec').forEach(s => s.classList.remove('active'));
  const sec = document.getElementById('ed-' + edMode);
  if (sec) sec.classList.add('active');
  const sb = document.getElementById('ed-save-btn');
  if (sb) sb.textContent = (edMode === 'html') ? '💾 حفظ المحتوى' : '💾 حفظ التخصيصات';
  syncUrl(edMode);
  if (edMode === 'visual') setTimeout(bFit, 60);
  else htmlLoad(false);
}

// زر الحفظ العلوي: يحفظ حسب التبويب المفتوح
function saveCurrent() {
  if (edMode === 'html') htmlSave();
  else builderSave();
}

// ── تحرير HTML: الجلب من السيرفر (لا يُفقد ما كتبته غير المحفوظ) ──
async function htmlLoad(force) {
  if (htmlDirty && !force) return;
  const f = document.getElementById('htmlform');
  if (!f) return;
  try {
    const j = await api('/api/templates/' + B_TID + '/get');
    if (!j.ok) throw new Error(j.error || 'خطأ في قراءة القالب');
    f.querySelector('[name=name]').value = j.row.name;
    f.querySelector('[name=type]').value = j.row.type;
    f.querySelector('[name=html_content]').value = j.row.html_content;
    htmlDirty = false;
  } catch (e) { toast(e.message, true); }
}

function htmlSave() {
  const f = document.getElementById('htmlform');
  if (!f) return;
  syncUrl('html');   // نبقى على تبويب HTML بعد إعادة تحميل الصفحة
  submitModal(f, '/api/templates');   // يحفظ ثم يُحدّث الصفحة (submitModal من app.js)
}

function resetTpl() {
  confirmThen('استعادة المحتوى الافتراضي لهذا القالب؟ (يُفقد المحتوى الحالي مع تخصيصات المحرر المرئي)', async () => {
    try {
      await api('/api/templates/' + B_TID + '/reset', {});
      toast('تمت الاستعادة');
      setTimeout(() => location.reload(), 350);
    } catch (e) { toast(e.message, true); }
  });
}

// ══════════ ربط عناصر التحكم ══════════
const edRoot = document.getElementById('tpleditor');
if (edRoot) {
  // أي تغيير في المحرر المرئي ⇒ تحديث فوري (مؤجَّل 400ms) للمعاينة
  edRoot.addEventListener('input', e => {
    if (e.target.closest('#ed-visual')) {
      if (e.target.id === 'b-qr_size') {
        const qsv = document.getElementById('b-qr_size_val');
        if (qsv) qsv.textContent = e.target.value;
      }
      builderQueue();
    } else if (e.target.name === 'html_content') {
      htmlDirty = true;   // تعديل غير محفوظ في تبويب HTML
    }
  });
  edRoot.addEventListener('change', e => {
    if (e.target.closest('#ed-visual') && e.target.id !== 'b-auto') builderQueue();
  });
} else {
  console.error('محرر القالب: الحاوية #tpleditor غير موجودة');
}

// تبويبات لوحة التحكم (الباركود/الهيدر/…)
document.querySelectorAll('#tpleditor .b-tabs button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#tpleditor .b-tabs button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#tpleditor .b-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const pane = document.getElementById('bpane-' + btn.dataset.pane);
    if (pane) pane.classList.add('active');
  });
});

const bFrameEl = document.getElementById('b-frame');
if (bFrameEl) bFrameEl.addEventListener('load', bFit);
window.addEventListener('resize', () => {
  const vis = document.getElementById('ed-visual');
  if (vis && vis.classList.contains('active')) bFit();
});

// ── بدء التشغيل ──
setMode(ED_MODE);
if (edMode === 'visual') builderInit();
