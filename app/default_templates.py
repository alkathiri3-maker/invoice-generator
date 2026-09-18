# -*- coding: utf-8 -*-
"""
القوالس الافتراضية الاحترافية للفواتير والسندات
Professional Invoice Templates in Arabic

يحتوي على 4 قوالس احترافية جاهزة للاستخدام:
- قالب الشركات (Corporate-Minimal)
- قالب حديث (Modern Card)
- قالب تقليدي (Classic-Formal)
- قالب صغير (Compact-Thermal)
"""

# قالب الشركات الاحترافي - Corporate Minimal
TEMPLATE_CORPORATE_MINIMAL = {
    'name': 'قالب الشركات الاحترافي',
    'type': 'invoice',
    'description': 'تصميم احترافي وبسيط مع رأس عصري وبيانات بنكية',
}

# قالب حديث - Modern Card
TEMPLATE_MODERN_CARD = {
    'name': 'قالب حديث',
    'type': 'invoice',
    'description': 'تصميم عصري مع رأس متدرج وبطاقات ورمز QR',
}

# قالب تقليدي - Classic Formal
TEMPLATE_CLASSIC_FORMAL = {
    'name': 'قالب تقليدي رسمي',
    'type': 'invoice',
    'description': 'تصميم تقليدي مع خطوط توقيع وشروط وأحكام',
}

# قالب صغير - Compact Thermal
TEMPLATE_COMPACT_THERMAL = {
    'name': 'قالب الإيصالات',
    'type': 'receipt',
    'description': 'تصميم مضغوط لطابعات الإيصالات الحرارية (80 ملم)',
}

# قائمة بجميع القوالس الافتراضية
DEFAULT_TEMPLATES = [
    TEMPLATE_CORPORATE_MINIMAL,
    TEMPLATE_MODERN_CARD,
    TEMPLATE_CLASSIC_FORMAL,
    TEMPLATE_COMPACT_THERMAL,
]

def get_template_by_name(name):
    """الحصول على قالب حسب الاسم"""
    for template in DEFAULT_TEMPLATES:
        if template['name'] == name:
            return template
    return None

def get_all_templates():
    """الحصول على جميع القوالس الافتراضية"""
    return DEFAULT_TEMPLATES

def get_invoice_templates():
    """الحصول على قوالس الفواتير فقط"""
    return [t for t in DEFAULT_TEMPLATES if t['type'] == 'invoice']

def get_receipt_templates():
    """الحصول على قوالس الإيصالات فقط"""
    return [t for t in DEFAULT_TEMPLATES if t['type'] == 'receipt']
