
const THEME = null;
function openTheme() {
  for (const k of Object.keys(THEME)) {
    const el = document.getElementById('themeform').querySelector(`[name=${k}]`);
    if (!el) continue;
    if (el.type === 'checkbox') el.checked = !!THEME[k];
    else el.value = THEME[k] ?? '';
  }
  openDlg('themedlg');
}
document.getElementById('themeform').addEventListener('submit', async () => {
  const f = document.getElementById('themeform');
  const d = Object.fromEntries(new FormData(f).entries());
  d.alert_banner_enabled = f.querySelector('#abe').checked;
  d.show_watermark = f.querySelector('#sw').checked;
  try {
    await api('/api/theme', d);
    toast('✅ تم حفظ المظهر — سيُطبق على كل المستندات');
    setTimeout(() => location.reload(), 700);
  } catch (e) { toast(e.message, true); }
});
function openAdd() {
  const f = document.getElementById('frm');
  f.reset();
  document.getElementById('dlg-title').textContent = 'قالب جديد';
  openDlg('dlg');
}
function openEdit(tr) {
  const id = tr.dataset.id;
  fetch('/api/templates/' + id + '/get').catch(() => {});
  // نجلب المحتوى من السيرفر عبر نقطة المعاينة? بدل ذلك نستخدم قيمة مخزنة:
  fetchContent(id, tr);
}
async function fetchContent(id, tr) {
  try {
    // نقطة بسيطة: نستخدم معاينة القالب لاستخراج المحتوى غير ممكنة؛ لذا نطلب من API
    const res = await fetch('/api/templates/' + id + '/get');
    const j = await res.json();
    if (!j.ok) throw new Error(j.error || 'خطأ');
    fillForm('dlg', [['id','id','number'],['name','name'],['type','type'],['html_content','html_content']], j.row);
    document.getElementById('dlg-title').textContent = 'تحرير قالب';
  } catch (e) { toast(e.message, true); }
}
async function resetTpl(id) {
  confirmThen('استعادة المحتوى الافتراضي لهذا القالب؟', async () => {
    try { await api('/api/templates/' + id + '/reset', {}); toast('تمت الاستعادة'); setTimeout(() => location.reload(), 350); }
    catch (e) { toast(e.message, true); }
  });
}
document.getElementById('frm').addEventListener('submit', () => submitModal(document.getElementById('frm'), '/api/templates'));

// ══════════ المحرر المرئي المتقدم (Visual Template Builder) ══════════
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
let bTid = null, bTimer = null, bLastHtml = '';

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

function openBuilder(tr) {
  try {
    bTid = tr.dataset.id;
    const titleEl = document.getElementById('builder-title');
    if (titleEl) titleEl.textContent = '🎨 المحرر المرئي المتقدم — ' + (tr.dataset.name || 'قالب');
    // نفتح النافذة أولًا: أي خطأ في تعبئة الحقول لا يمنع ظهور المحرر
    openDlg('builderdlg');
    setTimeout(bFit, 60);
    builderResetFields();
    api('/api/templates/' + bTid + '/style').then(j => {
      if (!j.ok) throw new Error(j.error || 'خطأ في قراءة الإعدادات');
      builderApply(j.style || {});
      builderRefresh();
    }).catch(e => { toast(e.message, true); builderRefresh(); });
  } catch (e) {
    console.error('تعذر فتح المحرر المرئي:', e);
    toast('تعذر فتح المحرر: ' + e.message, true);
  }
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
  for (const row of document.querySelectorAll('#builderdlg .b-crow')) {
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
  for (const row of document.querySelectorAll('#builderdlg .b-crow')) {
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
  for (const row of document.querySelectorAll('#builderdlg .b-crow')) {
    const { use, color } = bRowInputs(row);
    if (!use || !color) continue;
    s[row.dataset.k] = use.checked ? color.value : '';
  }
  return s;
}

async function builderRefresh() {
  if (!bTid) return;
  const box = document.getElementById('b-prev-box');
  const frame = document.getElementById('b-frame');
  if (!box || !frame) { console.warn('المحرر المرئي: صندوق المعاينة غير موجود'); return; }
  box.style.opacity = '.55';
  try {
    const j = await api('/api/templates/' + bTid + '/live-preview', { style: builderStyle() });
    if (!j.ok) throw new Error(j.error || 'خطأ في المعاينة');
    bLastHtml = j.html;
    frame.srcdoc = j.html;
  } catch (e) { toast(e.message, true); }
  finally { box.style.opacity = ''; }
}

function builderQueue() { clearTimeout(bTimer); bTimer = setTimeout(builderRefresh, 400); }

async function builderSave() {
  try {
    const j = await api('/api/templates/' + bTid + '/style', { style: builderStyle() });
    if (!j.ok) throw new Error(j.error || 'خطأ في الحفظ');
    toast('✅ تم حفظ تخصيصات القالب — تُطبق على كل الفواتير المطبوعة به');
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

// عناصر تحكم المحرر: أي تغيير ⇒ تحديث فوري (مؤجَّل 400ms) للمعاينة
const bDlgEl = document.getElementById('builderdlg');
if (bDlgEl) {
  bDlgEl.addEventListener('input', e => {
    if (e.target.id === 'b-qr_size') {
      const qsv = document.getElementById('b-qr_size_val');
      if (qsv) qsv.textContent = e.target.value;
    }
    builderQueue();
  });
  bDlgEl.addEventListener('change', () => builderQueue());
} else {
  console.error('المحرر المرئي: عنصر #builderdlg غير موجود — لن يعمل زر المحرر');
}

// التبويبات
document.querySelectorAll('#builderdlg .b-tabs button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#builderdlg .b-tabs button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#builderdlg .b-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const pane = document.getElementById('bpane-' + btn.dataset.pane);
    if (pane) pane.classList.add('active');
  });
});

// ملاءمة ورقة A4 (794×1123px عند 96dpi) داخل صندوق المعاينة
function bFit() {
  const box = document.getElementById('b-prev-box'), hold = document.getElementById('b-holder');
  if (!box || !hold) return;
  const s = Math.min(1, (box.clientWidth - 24) / 794);
  hold.style.transform = 'scale(' + s + ')';
  hold.style.width = (794 * s) + 'px';
  hold.style.height = (1123 * s) + 'px';
}
window.addEventListener('resize', () => { if (bDlgEl && bDlgEl.open) bFit(); });
const bFrameEl = document.getElementById('b-frame');
if (bFrameEl) bFrameEl.addEventListener('load', bFit);
