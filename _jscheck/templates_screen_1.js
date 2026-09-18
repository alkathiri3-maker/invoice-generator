
const THEME = {"alert_banner_bg": "#fee2e2", "alert_banner_color": "#e81111", "alert_banner_enabled": false, "alert_banner_text": "\u062a\u0646\u0628\u064a\u0647 \u0631\u0642\u0627\u0628\u064a: \u0647\u0630\u0647 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629 \u062a\u062f\u0631\u064a\u0628\u064a\u0629 \u0644\u062a\u0637\u0648\u064a\u0631 \u0645\u0647\u0627\u0631\u0627\u062a \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629 \u0648\u0641\u0643 \u0627\u0644\u062a\u0634\u0641\u064a\u0631 \u0641\u0642\u0637 \u2014 \u0644\u064a\u0633\u062a \u0635\u0627\u062f\u0631\u0629 \u0639\u0646 \u062c\u0647\u0629 \u0631\u0633\u0645\u064a\u0629 \u0648\u0644\u0627 \u062a\u0635\u0644\u062d \u0644\u0623\u064a \u0625\u062c\u0631\u0627\u0621 \u0636\u0631\u064a\u0628\u064a \u0623\u0648 \u0642\u0627\u0646\u0648\u0646\u064a.", "font_family": "Cairo", "font_size": "13", "footer_notice": "\u0646\u0633\u062e\u0629 \u062a\u062f\u0631\u064a\u0628\u064a\u0629 - \u063a\u064a\u0631 \u0635\u0627\u0644\u062d\u0629 \u0644\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0627\u0644\u0631\u0633\u0645\u064a", "generated_note": "", "header_text_color": "#ffffff", "primary_color": "#353131", "seller_name_color": "#0d0d0d", "show_watermark": false, "title_color": "#121212", "watermark_text": "\u0646\u0633\u062e\u0629 \u062a\u062f\u0631\u064a\u0628\u064a\u0629"};
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
async function resetTpl(id) {
  confirmThen('استعادة المحتوى الافتراضي لهذا القالب؟', async () => {
    try { await api('/api/templates/' + id + '/reset', {}); toast('تمت الاستعادة'); setTimeout(() => location.reload(), 350); }
    catch (e) { toast(e.message, true); }
  });
}
document.getElementById('frm').addEventListener('submit', () => submitModal(document.getElementById('frm'), '/api/templates'));
