"""Generate FluidTrust Customer Portal demo PPT."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import copy

# ── Brand colours ────────────────────────────────────────────────────────────
DARK_BLUE   = RGBColor(0x22, 0x4A, 0xBE)   # primary
MID_BLUE    = RGBColor(0x4E, 0x73, 0xDF)   # accent
LIGHT_BLUE  = RGBColor(0xD6, 0xE4, 0xFF)   # bg tint
WHITE       = RGBColor(0xFF, 0xFF, 0xFF)
DARK_GRAY   = RGBColor(0x2D, 0x3A, 0x4A)
MID_GRAY    = RGBColor(0x6C, 0x75, 0x7D)
LIGHT_GRAY  = RGBColor(0xF4, 0xF6, 0xFB)
GREEN       = RGBColor(0x28, 0xA7, 0x45)
ORANGE      = RGBColor(0xFD, 0x7E, 0x14)
RED         = RGBColor(0xDC, 0x35, 0x45)
TEAL        = RGBColor(0x20, 0xC9, 0x97)

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)

BLANK = prs.slide_layouts[6]   # completely blank


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def add_rect(slide, l, t, w, h, fill=None, line_color=None, line_width=None):
    shape = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
    shape.line.fill.background()
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    else:
        shape.fill.background()
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(line_width or 1)
    else:
        shape.line.fill.background()
    return shape

def add_text(slide, text, l, t, w, h, size=18, bold=False, color=DARK_GRAY,
             align=PP_ALIGN.LEFT, italic=False, wrap=True):
    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    txb.word_wrap = wrap
    tf = txb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txb

def add_para(tf, text, size=14, bold=False, color=DARK_GRAY,
             align=PP_ALIGN.LEFT, space_before=6):
    p = tf.add_paragraph()
    p.alignment = align
    p.space_before = Pt(space_before)
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return p

def header_bar(slide, title, subtitle=None):
    """Dark blue top bar with title."""
    add_rect(slide, 0, 0, 13.33, 1.3, fill=DARK_BLUE)
    add_rect(slide, 0, 1.3, 13.33, 0.08, fill=MID_BLUE)
    add_text(slide, title, 0.4, 0.12, 11, 0.7,
             size=30, bold=True, color=WHITE, align=PP_ALIGN.LEFT)
    if subtitle:
        add_text(slide, subtitle, 0.4, 0.78, 11, 0.42,
                 size=14, color=RGBColor(0xB0, 0xC8, 0xFF), align=PP_ALIGN.LEFT)
    # Slide number area (top-right)
    add_text(slide, 'FluidTrust Portal', 10.8, 0.18, 2.3, 0.4,
             size=10, color=RGBColor(0x90, 0xAF, 0xFF), align=PP_ALIGN.RIGHT)

def footer_bar(slide, page_no, total=10):
    add_rect(slide, 0, 7.1, 13.33, 0.4, fill=DARK_BLUE)
    add_text(slide, 'FluidTrust IT Management Portal  |  Confidential',
             0.3, 7.13, 9, 0.3, size=9, color=RGBColor(0xAA, 0xBB, 0xFF))
    add_text(slide, f'{page_no} / {total}', 12.5, 7.13, 0.7, 0.3,
             size=9, color=WHITE, align=PP_ALIGN.RIGHT)

def card(slide, l, t, w, h, title, lines, icon='', title_color=DARK_BLUE,
         bg=WHITE, border_color=MID_BLUE):
    """Rounded-corner card with title + bullet lines."""
    add_rect(slide, l, t, w, h, fill=bg, line_color=border_color, line_width=1.2)
    # Left accent bar
    add_rect(slide, l, t, 0.05, h, fill=border_color)
    add_text(slide, f'{icon}  {title}' if icon else title,
             l+0.15, t+0.1, w-0.25, 0.35,
             size=13, bold=True, color=title_color)
    txb = slide.shapes.add_textbox(
        Inches(l+0.18), Inches(t+0.48), Inches(w-0.3), Inches(h-0.6))
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    first = True
    for line in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_before = Pt(3)
        run = p.add_run()
        run.text = line
        run.font.size = Pt(11)
        run.font.color.rgb = DARK_GRAY


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 1 — TITLE
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)

# Full-bleed gradient background (two rects)
add_rect(s, 0, 0, 13.33, 7.5, fill=DARK_BLUE)
add_rect(s, 0, 0, 13.33, 7.5, fill=RGBColor(0x1A, 0x38, 0x9A))

# Decorative diagonal accent
for i in range(6):
    add_rect(s, 9.5 + i*0.6, 0, 0.4, 7.5,
             fill=RGBColor(0x2A, 0x55, 0xD5))

# White card overlay
add_rect(s, 0.6, 1.5, 8.5, 4.8, fill=WHITE, line_color=MID_BLUE, line_width=0.5)
add_rect(s, 0.6, 1.5, 0.12, 4.8, fill=MID_BLUE)

add_text(s, 'FluidTrust', 0.9, 1.75, 8, 0.8,
         size=42, bold=True, color=DARK_BLUE, align=PP_ALIGN.LEFT)
add_text(s, 'IT Management Customer Portal', 0.9, 2.45, 8, 0.6,
         size=24, bold=False, color=MID_BLUE, align=PP_ALIGN.LEFT)
add_text(s, '─' * 55, 0.9, 3.0, 8, 0.3, size=11, color=LIGHT_BLUE)

bullets = [
    '🖥  Remote Monitoring & Management (Pulseway)',
    '🎫  IT Helpdesk & Ticketing (ManageEngine)',
    '📱  Mobile Device Management (MDM)',
    '☁  Cloud Backup Management (Datto)',
]
y = 3.25
for b in bullets:
    add_text(s, b, 0.9, y, 7.8, 0.38, size=13, color=DARK_GRAY)
    y += 0.38

add_text(s, 'Demo Presentation  |  2026', 0.9, 5.9, 8, 0.4,
         size=11, italic=True, color=MID_GRAY)
add_text(s, 'Confidential', 11.5, 7.1, 1.6, 0.3, size=9,
         color=RGBColor(0x88, 0xAA, 0xFF), align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 2 — AGENDA
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'Agenda', 'What we will cover today')
footer_bar(s, 2)

items = [
    ('01', 'Project Overview',         'Purpose, goals and key stakeholders'),
    ('02', 'System Architecture',      'Technology stack and integration map'),
    ('03', 'Role-Based Access Control','Admin, Technician and Customer roles'),
    ('04', 'ManageEngine Integration', 'Helpdesk ticketing and reports'),
    ('05', 'Pulseway — RMM',           'Device monitoring, online/offline status'),
    ('06', 'Mobile Device Management', 'MDM device inventory and reports'),
    ('07', 'Datto Backup',             'Backup status and storage pool'),
    ('08', 'Reports Dashboard',        'Multi-module company-wise reports'),
    ('09', 'Key Features Summary',     'Security, sync, notifications'),
    ('10', 'Live Demo & Q&A',          'Walk-through and questions'),
]

cols = [0.4, 6.9]
for idx, (num, title, sub) in enumerate(items):
    col = idx % 2
    row = idx // 2
    l = cols[col]
    t = 1.55 + row * 1.12
    w = 6.2

    add_rect(s, l, t, w, 0.98, fill=WHITE,
             line_color=MID_BLUE if col == 0 else DARK_BLUE, line_width=0.8)
    add_rect(s, l, t, 0.55, 0.98, fill=MID_BLUE if col == 0 else DARK_BLUE)
    add_text(s, num, l+0.02, t+0.22, 0.52, 0.45,
             size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(s, title, l+0.65, t+0.08, w-0.75, 0.4,
             size=13, bold=True, color=DARK_BLUE)
    add_text(s, sub, l+0.65, t+0.52, w-0.75, 0.38,
             size=10, color=MID_GRAY)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 3 — PROJECT OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'Project Overview', 'Unified IT management platform for Wepsol and its clients')
footer_bar(s, 3)

# Left column — What is it?
add_rect(s, 0.3, 1.55, 5.8, 5.3, fill=WHITE, line_color=MID_BLUE, line_width=0.8)
add_rect(s, 0.3, 1.55, 0.08, 5.3, fill=MID_BLUE)
add_text(s, '📋  What Is FluidTrust Portal?', 0.55, 1.65, 5.4, 0.45,
         size=14, bold=True, color=DARK_BLUE)
txb = slide_text = s.shapes.add_textbox(Inches(0.55), Inches(2.2), Inches(5.4), Inches(4.4))
slide_text.word_wrap = True
tf = slide_text.text_frame
tf.word_wrap = True
paras = [
    ('A single web portal that gives Wepsol\'s managed service clients a '
     'real-time view of all their IT assets and support activity.', False),
    '', ('Key Goals:', True),
    '✔  Single pane of glass for all IT services',
    '✔  Role-based access — customers see only their data',
    '✔  Live sync with ManageEngine, Pulseway, MDM & Datto',
    '✔  Package-based module access control',
    '✔  Professional reporting per company',
    '✔  Automated background data sync with fault tolerance',
]
first = True
for p_text in paras:
    bold = False
    if isinstance(p_text, tuple):
        p_text, bold = p_text
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    first = False
    p.space_before = Pt(5)
    run = p.add_run()
    run.text = p_text
    run.font.size = Pt(12)
    run.font.bold = bold
    run.font.color.rgb = DARK_GRAY if not bold else DARK_BLUE

# Right column — Stats
add_rect(s, 6.5, 1.55, 6.5, 5.3, fill=WHITE, line_color=DARK_BLUE, line_width=0.8)
add_rect(s, 6.5, 1.55, 0.08, 5.3, fill=DARK_BLUE)
add_text(s, '📊  At a Glance', 6.75, 1.65, 6, 0.45,
         size=14, bold=True, color=DARK_BLUE)

stats = [
    ('490+', 'Monitored Devices',        GREEN),
    ('6,779', 'Tickets Synced',           MID_BLUE),
    ('7',    'Companies Managed',        ORANGE),
    ('4',    'Integrated Modules',       TEAL),
    ('3',    'User Roles',               DARK_BLUE),
    ('30 min','Pulseway Sync Interval',  MID_GRAY),
]
sy = 2.2
for val, label, col in stats:
    add_rect(s, 6.75, sy, 5.9, 0.68, fill=LIGHT_GRAY,
             line_color=col, line_width=0.6)
    add_text(s, val, 6.9, sy+0.1, 1.5, 0.48,
             size=22, bold=True, color=col)
    add_text(s, label, 8.5, sy+0.18, 4, 0.35,
             size=12, color=DARK_GRAY)
    sy += 0.78


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 4 — ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'System Architecture', 'Django-based portal with background sync and live API integration')
footer_bar(s, 4)

# Central Django box
add_rect(s, 4.9, 2.8, 3.5, 1.6, fill=DARK_BLUE, line_color=MID_BLUE, line_width=1.5)
add_text(s, '🌐  FluidTrust Portal', 5.0, 2.95, 3.3, 0.45,
         size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
add_text(s, 'Django 4.2  |  SQLite  |  Bootstrap 5', 5.0, 3.42, 3.3, 0.35,
         size=9, color=LIGHT_BLUE, align=PP_ALIGN.CENTER)
add_text(s, 'RBAC  |  Scheduler  |  REST APIs', 5.0, 3.75, 3.3, 0.35,
         size=9, color=LIGHT_BLUE, align=PP_ALIGN.CENTER)

# External service boxes
ext_services = [
    (0.4,  2.0, 2.8, 1.2, 'ManageEngine',   'Helpdesk\nTicketing API',    MID_BLUE),
    (0.4,  4.2, 2.8, 1.2, 'Pulseway RMM',   'Device Detail\nAPI v3',      GREEN),
    (10.1, 2.0, 2.8, 1.2, 'MDM Platform',   'Device\nEnrollment',         ORANGE),
    (10.1, 4.2, 2.8, 1.2, 'Datto Backup',   'BCDR / DTC\nStorage API',    RED),
]
for lx, ty, w, h, title, sub, col in ext_services:
    add_rect(s, lx, ty, w, h, fill=WHITE, line_color=col, line_width=1.5)
    add_rect(s, lx, ty, 0.1, h, fill=col)
    add_text(s, title, lx+0.2, ty+0.08, w-0.25, 0.4, size=12, bold=True, color=col)
    add_text(s, sub,   lx+0.2, ty+0.5,  w-0.25, 0.55, size=10, color=DARK_GRAY)

# User types (bottom)
user_types = [
    (1.5,  6.1, 2.2, 0.75, '👨‍💼  Admin',     'Full system access', DARK_BLUE),
    (5.55, 6.1, 2.2, 0.75, '🔧  Technician', 'Manage all companies', MID_BLUE),
    (9.6,  6.1, 2.2, 0.75, '🏢  Customer',   'Own company only', GREEN),
]
for lx, ty, w, h, title, sub, col in user_types:
    add_rect(s, lx, ty, w, h, fill=col, line_color=col)
    add_text(s, title, lx+0.1, ty+0.05, w-0.15, 0.38, size=11, bold=True, color=WHITE)
    add_text(s, sub,   lx+0.1, ty+0.4,  w-0.15, 0.3,  size=9,  color=LIGHT_BLUE)

# Arrows (simple text lines as connectors)
arrows = [
    (3.2, 2.55, '↔'),  # ManageEngine
    (3.2, 4.65, '↔'),  # Pulseway
    (10.1, 2.55, '↔'), # MDM
    (10.1, 4.65, '↔'), # Datto
]
for lx, ty, sym in arrows:
    add_text(s, sym, lx, ty, 0.6, 0.4, size=18, bold=True,
             color=MID_BLUE, align=PP_ALIGN.CENTER)

add_text(s, 'Sync Threads', 5.15, 1.6, 3, 0.35, size=10,
         color=MID_GRAY, align=PP_ALIGN.CENTER)
add_text(s, '↑ Background Schedulers ↑', 5.15, 1.95, 3, 0.35,
         size=9, italic=True, color=MID_GRAY, align=PP_ALIGN.CENTER)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 5 — RBAC / ROLES
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'Role-Based Access Control', 'Three roles — each sees exactly what they need')
footer_bar(s, 5)

roles = [
    ('👨‍💼', 'Administrator', DARK_BLUE,
     ['Full portal access — all companies',
      'Manage users, companies and packages',
      'Assign module access (ManageEngine, Pulseway, MDM, Datto)',
      'View sync control panel and API diagnostics',
      'Access all reports and export data',
      'Manage Pulseway devices, policies and automation']),
    ('🔧', 'Technician', MID_BLUE,
     ['Access all assigned companies',
      'View and manage tickets across companies',
      'Monitor device status in Pulseway',
      'View MDM device inventory',
      'Generate cross-company reports',
      'Cannot manage user accounts or packages']),
    ('🏢', 'Customer', GREEN,
     ['Sees ONLY their own company\'s data',
      'Raise and track support tickets',
      'View their device monitoring status',
      'Access reports for their packages only',
      'Mobile device inventory (if MDM package)',
      'No access to other companies\' data']),
]

lx = 0.3
for icon, title, col, points in roles:
    add_rect(s, lx, 1.55, 4.1, 5.5, fill=WHITE, line_color=col, line_width=1.2)
    add_rect(s, lx, 1.55, 4.1, 0.9, fill=col)
    add_text(s, icon, lx+0.2, 1.6, 0.7, 0.7, size=28, color=WHITE)
    add_text(s, title, lx+0.9, 1.7, 3.0, 0.65,
             size=18, bold=True, color=WHITE, align=PP_ALIGN.LEFT)
    y = 2.6
    for pt in points:
        add_text(s, f'✦  {pt}', lx+0.2, y, 3.7, 0.42, size=11, color=DARK_GRAY)
        y += 0.72
    lx += 4.45

# Package access note
add_rect(s, 0.3, 7.0, 12.7, 0.0, fill=MID_BLUE)
add_text(s, '💡  Customers see report tabs only for modules included in their package '
         '(ManageEngine / Pulseway / MDM — per-company configuration)',
         0.5, 6.95, 12.3, 0.35, size=10, italic=True, color=MID_GRAY)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 6 — MANAGEENGINE
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'ManageEngine — IT Helpdesk', 'Live ticket sync, reporting and ticket creation from the portal')
footer_bar(s, 6)

features = [
    ('🎫', 'Ticket Management',   MID_BLUE,
     ['Raise new tickets directly from the portal',
      'File attachment support',
      'Auto-assign requester email from ManageEngine users',
      'View ticket status, priority, technician']),
    ('🔄', 'Auto Sync',          GREEN,
     ['Incremental sync every 5 minutes',
      '6,779+ tickets cached in local DB',
      'Daily reconciliation removes ghost tickets',
      'Smart sync: only fetches changes since last run']),
    ('📊', 'Reports',            ORANGE,
     ['Daily / Weekly / Monthly ticket trends',
      'Status breakdown (Open/Pending/Resolved/Closed)',
      'Priority distribution with charts',
      'Per-company filtering for customers']),
    ('🏢', 'Company Filtering',  DARK_BLUE,
     ['Customers see only their own tickets',
      'Fuzzy company name matching',
      'Technician view shows all companies',
      'Export to CSV for any date range']),
]

positions = [(0.3, 1.55), (6.8, 1.55), (0.3, 4.35), (6.8, 4.35)]
for (lx, ty), (icon, title, col, points) in zip(positions, features):
    w, h = 6.1, 2.6
    add_rect(s, lx, ty, w, h, fill=WHITE, line_color=col, line_width=1.0)
    add_rect(s, lx, ty, w, 0.55, fill=col)
    add_text(s, f'{icon}  {title}', lx+0.15, ty+0.1, w-0.2, 0.4,
             size=14, bold=True, color=WHITE)
    y = ty + 0.7
    for pt in points:
        add_text(s, f'• {pt}', lx+0.2, y, w-0.35, 0.38, size=11, color=DARK_GRAY)
        y += 0.44


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 7 — PULSEWAY
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'Pulseway — Remote Monitoring & Management',
           'Real-time device status, uptime and patch compliance across all companies')
footer_bar(s, 7)

# Stats row
stats_row = [
    ('490+', 'Total Devices',    DARK_BLUE),
    ('294',  'Online Now',       GREEN),
    ('196',  'Offline',          RED),
    ('7',    'Companies',        MID_BLUE),
    ('30 min','Sync Interval',   ORANGE),
]
sx = 0.3
for val, label, col in stats_row:
    add_rect(s, sx, 1.55, 2.45, 1.1, fill=col)
    add_text(s, val, sx+0.1, 1.62, 2.25, 0.65,
             size=28, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(s, label, sx+0.1, 2.2, 2.25, 0.38,
             size=10, color=LIGHT_BLUE, align=PP_ALIGN.CENTER)
    sx += 2.56

# Feature cards
feats = [
    ('🟢', 'Online/Offline Status',
     'Per-device detail API — Uptime string ("Online 3d 5h") '
     'is the only reliable status indicator. Synced every 30 min.'),
    ('🛡', 'Patch Compliance',
     'Pending patch count per device. Dashboard shows '
     'devices needing updates. Filter by company.'),
    ('🔍', 'Device Inventory',
     'Full device list: IP address, OS, site, organisation. '
     'Searchable and paginated per company.'),
    ('⚡', 'Rate-Limit Handling',
     '1.5s delay between API calls (~40 req/min). '
     'Preserves last-known status on 429 errors. 3-retry backoff.'),
    ('📈', 'Sync Control Panel',
     'Admin panel shows last sync time per org. '
     'Manual trigger button. API diagnostic tool.'),
    ('🏢', 'Company Isolation',
     'Customer login shows only their company\'s devices. '
     'Fuzzy name matching handles spelling variants.'),
]

fx, fy = 0.3, 2.85
for i, (icon, title, desc) in enumerate(feats):
    col = i % 3
    row = i // 3
    lx = fx + col * 4.35
    ty = fy + row * 2.0
    add_rect(s, lx, ty, 4.1, 1.82, fill=WHITE,
             line_color=MID_BLUE if row == 0 else DARK_BLUE, line_width=0.8)
    add_rect(s, lx, ty, 0.07, 1.82, fill=MID_BLUE if row == 0 else DARK_BLUE)
    add_text(s, f'{icon}  {title}', lx+0.18, ty+0.1, 3.8, 0.38,
             size=12, bold=True, color=DARK_BLUE)
    add_text(s, desc, lx+0.18, ty+0.52, 3.8, 1.2,
             size=10, color=DARK_GRAY, wrap=True)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 8 — MDM
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'Mobile Device Management', 'Full visibility of enrolled mobile devices per company')
footer_bar(s, 8)

# Left — features
add_rect(s, 0.3, 1.55, 6.0, 5.5, fill=WHITE, line_color=ORANGE, line_width=1.0)
add_rect(s, 0.3, 1.55, 0.08, 5.5, fill=ORANGE)
add_text(s, '📱  MDM Dashboard Features', 0.55, 1.65, 5.6, 0.45,
         size=14, bold=True, color=DARK_BLUE)

mdm_features = [
    ('Device Inventory', 'Full list: name, type (Android/iOS/Windows/Mac), model, OS version'),
    ('Enrollment Status', 'Active, Managed, Staged, Retired — with colour badges'),
    ('Security',          'Encryption status per device — Yes / No badges'),
    ('Battery Level',     'Battery % shown, red highlight if below 20%'),
    ('Last Contact',      'When the device last checked in to MDM'),
    ('Company Filter',    'Customer sees only their enrolled devices'),
    ('Pagination',        'Search + paginate large device lists'),
    ('Reports Tab',       'Device type donut, managed vs unmanaged, encryption chart'),
]
y = 2.2
for title, desc in mdm_features:
    add_rect(s, 0.55, y, 5.5, 0.55, fill=LIGHT_GRAY,
             line_color=ORANGE, line_width=0.3)
    add_text(s, title, 0.7,  y+0.08, 1.6, 0.38, size=11, bold=True, color=DARK_BLUE)
    add_text(s, desc,  2.35, y+0.08, 3.6, 0.38, size=10, color=DARK_GRAY)
    y += 0.62

# Right — device type breakdown (visual)
add_rect(s, 6.7, 1.55, 6.3, 5.5, fill=WHITE, line_color=DARK_BLUE, line_width=1.0)
add_rect(s, 6.7, 1.55, 0.08, 5.5, fill=DARK_BLUE)
add_text(s, '📊  Device Type Breakdown', 6.95, 1.65, 5.9, 0.45,
         size=14, bold=True, color=DARK_BLUE)

device_types = [
    ('Android',  '45%', GREEN,     5.5),
    ('iOS/iPhone','30%', MID_BLUE,  3.6),
    ('Windows',  '20%', TEAL,      2.4),
    ('macOS',    '5%',  ORANGE,    0.6),
]
bar_y = 2.35
for dtype, pct, col, bar_w_rel in device_types:
    add_text(s, dtype, 6.95, bar_y, 2.0, 0.32, size=11, bold=True, color=DARK_GRAY)
    add_text(s, pct,   11.5, bar_y, 1.0, 0.32, size=11, bold=True, color=col,
             align=PP_ALIGN.RIGHT)
    # bar background
    add_rect(s, 8.9, bar_y+0.04, 4.8, 0.26, fill=LIGHT_GRAY)
    # bar fill (proportional)
    add_rect(s, 8.9, bar_y+0.04, bar_w_rel, 0.26, fill=col)
    bar_y += 0.62

add_rect(s, 6.95, 5.55, 5.8, 1.3, fill=LIGHT_BLUE,
         line_color=MID_BLUE, line_width=0.5)
add_text(s, '💡  Key Point', 7.1, 5.62, 5.5, 0.32, size=11, bold=True, color=DARK_BLUE)
add_text(s,
    'Device types (iOS, Android, macOS, Windows) are normalised '
    'from raw MDM API values. Charts update automatically as new '
    'devices enrol.',
    7.1, 5.95, 5.5, 0.8, size=10, color=DARK_GRAY)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 9 — REPORTS
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'Reports Dashboard', 'Package-aware multi-module reporting — company data only')
footer_bar(s, 9)

# Top description
add_rect(s, 0.3, 1.55, 12.7, 0.8, fill=MID_BLUE)
add_text(s,
    'Customers see report tabs only for the modules in their package. '
    'All data is filtered to their company. Tabs appear dynamically based on access.',
    0.5, 1.65, 12.3, 0.6, size=12, color=WHITE)

# Three module report cards
modules = [
    ('🎫', 'ManageEngine\nTicket Reports', MID_BLUE,
     ['Daily / Weekly / Monthly trends',
      'Status pie: Open, Pending, Resolved, Closed',
      'Priority bar chart',
      'Daily ticket trend (area chart)',
      'Full ticket table with search & pagination',
      'Export to CSV']),
    ('🖥', 'Pulseway\nDevice Reports', GREEN,
     ['Total / Online / Offline summary cards',
      'Online vs Offline donut chart',
      'OS distribution bar chart',
      'Patch compliance donut',
      'Device table: IP, OS, uptime, patches',
      'Search + 20/50/100 rows per page']),
    ('📱', 'MDM\nDevice Reports', ORANGE,
     ['Total / Active / Inactive / Retired cards',
      'Device type donut (Android, iOS, Win, Mac)',
      'Managed vs Unmanaged donut',
      'Encryption status donut',
      'Device table: model, OS, battery, user',
      'Search + paginated']),
]

lx = 0.3
for icon, title, col, points in modules:
    add_rect(s, lx, 2.55, 4.2, 4.6, fill=WHITE, line_color=col, line_width=1.2)
    add_rect(s, lx, 2.55, 4.2, 0.85, fill=col)
    add_text(s, icon, lx+0.15, 2.6, 0.7, 0.7, size=26, color=WHITE)
    add_text(s, title, lx+0.85, 2.65, 3.2, 0.7,
             size=14, bold=True, color=WHITE)
    y = 3.55
    for pt in points:
        add_text(s, f'✓  {pt}', lx+0.2, y, 3.8, 0.42, size=10.5, color=DARK_GRAY)
        y += 0.52
    lx += 4.5


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 10 — KEY FEATURES SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'Key Features & Technology', 'Built for reliability, security and real-time accuracy')
footer_bar(s, 10)

tech_left = [
    ('🔐', 'Authentication', WHITE,
     ['Django auth — session-based login',
      'Role + package permission middleware',
      'Password reset via secure token (24h expiry)',
      'Self-registration with email verification']),
    ('🔄', 'Background Sync', WHITE,
     ['ManageEngine: incremental every 5 min',
      'Pulseway: full detail sync every 30 min',
      'SQLite WAL mode + batch writes (no lock conflicts)',
      'Rate-limit resilience — preserves last known status']),
    ('📧', 'Email & Notifications', WHITE,
     ['Microsoft Graph API (Wepsol Office 365)',
      'Professional HTML emails for registration & reset',
      'Correct IP (192.168.5.150:8000) in all links',
      'Fallback plain-text for email clients']),
]
tech_right = [
    ('🛠', 'Technology Stack', WHITE,
     ['Backend: Django 4.2 + Python 3.x',
      'DB: SQLite (WAL mode, 30s busy timeout)',
      'Frontend: Bootstrap 5 + ApexCharts',
      'APIs: REST (requests lib) + slumber (Pulseway)']),
    ('🏗', 'Integrations', WHITE,
     ['ManageEngine ServiceDesk Plus v3',
      'Pulseway RMM API v3 (fluidpulse.wepsol.com)',
      'Datto Partner API v1 (BCDR + DTC)',
      'ManageEngine MDM API']),
    ('📋', 'Data Accuracy', WHITE,
     ['Live API comparison on demand',
      '429 rate-limit: preserve-last-status logic',
      'Stale device cleanup (404 = decommissioned)',
      'Batch DB writes prevent SQLite lock conflicts']),
]

lx = 0.3
for rows in [tech_left, tech_right]:
    ty = 1.6
    for icon, title, bg, points in rows:
        col = DARK_BLUE if lx < 5 else MID_BLUE
        add_rect(s, lx, ty, 5.8, 1.72, fill=WHITE, line_color=col, line_width=0.8)
        add_rect(s, lx, ty, 0.07, 1.72, fill=col)
        add_text(s, f'{icon}  {title}', lx+0.18, ty+0.08, 5.4, 0.38,
                 size=12, bold=True, color=col)
        y2 = ty + 0.52
        for pt in points:
            add_text(s, f'• {pt}', lx+0.22, y2, 5.4, 0.3, size=9.5, color=DARK_GRAY)
            y2 += 0.29
        ty += 1.85
    lx += 6.75


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 11 — DATTO
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=LIGHT_GRAY)
header_bar(s, 'Datto — Backup Management',
           'BCDR and Direct-to-Cloud storage monitoring via Datto Partner API')
footer_bar(s, 10)

add_rect(s, 0.3, 1.55, 12.7, 1.0, fill=WHITE, line_color=RED, line_width=1.0)
add_rect(s, 0.3, 1.55, 0.08, 1.0, fill=RED)
add_text(s, '☁  Storage Pool: backupEssentials — 1,922 GB used of 5,672 GB (33.9%)',
         0.55, 1.72, 12.2, 0.4, size=13, bold=True, color=DARK_BLUE)
add_rect(s, 0.55, 2.1, 12.0, 0.22, fill=LIGHT_GRAY)
add_rect(s, 0.55, 2.1, 4.07, 0.22, fill=RED)
add_text(s, '33.9%', 0.65, 2.12, 1.5, 0.18, size=9, color=WHITE)

datto_cards = [
    ('📦', 'BCDR Devices',    RED,
     ['Physical BCDR appliances (SIRIS/ALTO)',
      'Online/Offline status per device',
      'Model, serial number, IP address',
      'Export device list to CSV']),
    ('☁', 'DTC Assets',       ORANGE,
     ['Direct-to-Cloud (Backup Essentials)',
      '4 devices actively backing up',
      'API diagnostic tool shows endpoint health',
      'Auto-retry on Datto API 500 errors']),
    ('📊', 'Storage Usage',   MID_BLUE,
     ['Pool name, total / used / available GB',
      'Usage % progress bar',
      'Colour-coded: green <60%, warning >80%',
      'Export storage report to CSV']),
    ('🔍', 'API Diagnostics', DARK_BLUE,
     ['One-click "API Status" button',
      'Tests all 4 endpoints live',
      'Shows HTTP status + response time',
      'Identifies Datto server-side issues']),
]

lx = 0.3
for icon, title, col, points in datto_cards:
    add_rect(s, lx, 2.55, 3.1, 4.3, fill=WHITE, line_color=col, line_width=1.0)
    add_rect(s, lx, 2.55, 3.1, 0.65, fill=col)
    add_text(s, f'{icon}  {title}', lx+0.12, 2.62, 2.86, 0.45,
             size=13, bold=True, color=WHITE)
    y = 3.35
    for pt in points:
        add_text(s, f'• {pt}', lx+0.15, y, 2.8, 0.42, size=10.5, color=DARK_GRAY)
        y += 0.52
    lx += 3.26


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 12 — CLOSING / Q&A
# ═══════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
add_rect(s, 0, 0, 13.33, 7.5, fill=DARK_BLUE)
for i in range(8):
    add_rect(s, 9.5 + i*0.5, 0, 0.3, 7.5, fill=RGBColor(0x2A, 0x55, 0xD5))

add_rect(s, 0.6, 1.4, 8.8, 5.2, fill=WHITE, line_color=MID_BLUE, line_width=0.5)
add_rect(s, 0.6, 1.4, 0.12, 5.2, fill=MID_BLUE)

add_text(s, 'Thank You!', 0.9, 1.6, 8.4, 1.0,
         size=48, bold=True, color=DARK_BLUE, align=PP_ALIGN.LEFT)
add_text(s, 'FluidTrust IT Management Portal', 0.9, 2.55, 8.4, 0.5,
         size=20, color=MID_BLUE, align=PP_ALIGN.LEFT)
add_text(s, '─' * 55, 0.9, 3.0, 8.4, 0.3, size=11, color=LIGHT_BLUE)

summary = [
    '✅  490+ devices monitored across 7 companies',
    '✅  6,779 tickets synced from ManageEngine',
    '✅  Package-based multi-module access control',
    '✅  Rate-limit resilient sync with status preservation',
    '✅  Professional reports per company',
]
y = 3.3
for item in summary:
    add_text(s, item, 0.9, y, 8.2, 0.4, size=13, color=DARK_GRAY)
    y += 0.5

add_text(s, '❓  Questions & Live Demo', 0.9, 5.9, 8.2, 0.55,
         size=18, bold=True, color=DARK_BLUE)

add_text(s, 'Powered by Django 4.2  |  Bootstrap 5  |  ManageEngine  |  Pulseway  |  MDM  |  Datto',
         0.9, 6.4, 8.2, 0.3, size=9, italic=True, color=MID_GRAY)


# ── Save ─────────────────────────────────────────────────────────────────
out = 'FluidTrust_Portal_Demo.pptx'
prs.save(out)
print(f'Saved: {out}  ({prs.slides.__len__()} slides)')
