import pdfplumber
import os
import json

# ── 1. 分類與優先級定義 ──────────────────────────────────────────────
DEPARTMENTS = {
    "風險監控": {
        "icon": "⚠️",
        "label": "Risk Monitor",
        "keywords": ["美伊", "伊朗", "戰爭", "川普", "選情", "槍響", "Fed", "利率", "衝突", "地緣", "供應鏈"]
    },
    "總體數據": {
        "icon": "📊",
        "label": "Macro Data",
        "keywords": ["出口", "進口", "物價", "通膨", "匯率", "GDP", "主計", "景氣", "成長", "外銷"]
    },
    "產業動能": {
        "icon": "⚙️",
        "label": "Industry",
        "keywords": ["AI", "資本支出", "台積電", "半導體", "伺服器", "CoWoS", "設備", "製程", "先進封裝"]
    },
    "政策規畫": {
        "icon": "🏢",
        "label": "Policy",
        "keywords": ["國發會", "政策", "計畫", "電力", "預算", "離岸風電", "算力", "淨零", "綠能"]
    }
}

MUST_READ = [
    "Fed", "FOMC", "主計", "主計處", "GDP", "升息", "降息",
    "央行理監事", "利率決議", "通膨數據", "外銷訂單", "貿易統計",
    "戰爭", "地緣", "衝突", "制裁", "供應鏈斷鏈"
]
WATCH = [
    "出口", "進口", "資本支出", "AI", "台積電", "半導體",
    "景氣", "匯率", "油價", "通膨", "物價", "川普",
    "美伊", "離岸風電", "淨零", "算力"
]

def get_priority(title):
    if any(k in title for k in MUST_READ): return "must"
    if any(k in title for k in WATCH): return "watch"
    return "normal"

def get_lead(title, cat):
    """卡片一行導語：說明對總經的意義"""
    if any(k in title for k in ["資本支出", "AI", "設備", "伺服器"]):
        return "民間投資（I）上行動能，支撐 GDP 成長"
    if any(k in title for k in ["出口", "訂單", "外銷"]):
        return "外需動能指標，影響淨出口（X-M）貢獻度"
    if any(k in title for k in ["通膨", "油價", "物價", "CPI"]):
        return "供給端成本壓力，制約民間消費（C）空間"
    if any(k in title for k in ["川普", "戰爭", "地緣", "衝突", "制裁"]):
        return "系統性風險訊號，需調高不確定性溢價"
    if any(k in title for k in ["Fed", "利率", "央行", "升息", "降息"]):
        return "貨幣政策路徑，影響台美利差與資金流向"
    if any(k in title for k in ["政策", "計畫", "預算", "國發會"]):
        return "政府支出（G）結構調整，牽動公共投資預期"
    if any(k in title for k in ["台積電", "半導體", "CoWoS", "封裝"]):
        return "供應鏈核心動向，影響出口與民間投資預測"
    if any(k in title for k in ["景氣", "GDP", "成長"]):
        return "總體景氣指標，影響整體成長預測校準"
    return "一般經濟資訊，建議持續觀察後續數據"


# ── 2. 文字處理 ──────────────────────────────────────────────

# 雜訊行的特徵，過濾掉這些不是新聞內容的行
NOISE_PREFIXES = ["來源", "作者", "版面", "日期", "出處", "記者", "編輯", "回到目錄", "本報訊", "【本報"]
NOISE_SHORT = 10   # 短於此字數的行視為標題/頁碼雜訊

def clean_lines(text):
    """清洗 PDF 擷取文字：移除雜訊行，回傳有效行清單"""
    if not text:
        return []
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if len(line) < NOISE_SHORT:
            continue
        if any(line.startswith(prefix) for prefix in NOISE_PREFIXES):
            continue
        # 純數字行（頁碼）
        if line.replace(" ", "").isdigit():
            continue
        lines.append(line)
    return lines

def extract_summary(full_text, limit=280):
    """
    從全文擷取新聞重點（前 1~2 段有意義的內文）。
    策略：取第一行長度夠、不是 metadata 的正文句子。
    """
    if not full_text:
        return ""
    lines = clean_lines(full_text)
    if not lines:
        return ""

    # 嘗試找到第一個看起來像「正文」的句子（包含句號或逗號，且夠長）
    for line in lines:
        if len(line) >= 20 and ("，" in line or "。" in line or "、" in line):
            return line[:limit]

    # fallback：直接取第一行
    return lines[0][:limit]

def extract_full_text(all_page_texts, title, max_chars=1500):
    """
    從所有頁面文字中定位與標題最相關的段落，回傳完整擷取內容。
    用標題前 6 個字當搜尋 key（比 4~5 字更精準），
    找到後往後取 max_chars 字並清洗。
    """
    search_key = title[:6]
    best_snippet = ""
    for page_text in all_page_texts:
        if search_key not in page_text:
            continue
        idx = page_text.find(search_key)
        # 往前 30 字（可能有段落開頭），往後 max_chars
        raw = page_text[max(0, idx - 30): idx + max_chars]
        cleaned_lines = clean_lines(raw)
        if cleaned_lines:
            candidate = "\n".join(cleaned_lines)
            if len(candidate) > len(best_snippet):
                best_snippet = candidate
    return best_snippet


# ── 3. 主程式 ──────────────────────────────────────────────

def run_dashboard():
    if not os.path.exists("data"):
        os.makedirs("data")
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("data 資料夾內找不到 PDF")
        return

    # 取最新（依修改時間）
    pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join("data", x)))
    latest_pdf = os.path.join("data", pdf_files[-1])
    print(f"正在分析: {latest_pdf}")

    organized_data = {cat: {} for cat in DEPARTMENTS.keys()}
    organized_data["其他資訊"] = {}

    with pdfplumber.open(latest_pdf) as pdf:
        print("緩存全文中...")
        all_page_texts = [p.extract_text() or "" for p in pdf.pages]

        for page in pdf.pages[:10]:   # 目錄通常在前幾頁
            table = page.extract_table()
            if not table:
                continue

            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]:
                    continue
                title = str(row[1]).replace("\n", "").strip()
                source = str(row[2]).replace("\n", " ").strip() if len(row) > 2 else "未知"

                if len(title) < 5 or "新聞議題" in title:
                    continue

                # 分類
                found_cat = "其他資訊"
                for cat, info in DEPARTMENTS.items():
                    if any(k in title for k in info["keywords"]):
                        found_cat = cat
                        break

                # 全文擷取（用改進後的 6 字 key + 清洗）
                full_text = extract_full_text(all_page_texts, title)
                summary = extract_summary(full_text)

                priority = get_priority(title)
                lead = get_lead(title, found_cat)
                theme_key = title[:8]

                if theme_key not in organized_data[found_cat]:
                    organized_data[found_cat][theme_key] = {
                        "main_title": title,
                        "related_titles": [],
                        "sources": [source],
                        "full_text": full_text,      # 完整擷取（全文 tab 用）
                        "summary": summary,           # 第一段（展開後第一眼）
                        "priority": priority,
                        "lead": lead,
                    }
                else:
                    # 優先級取較高者
                    p_rank = {"must": 0, "watch": 1, "normal": 2}
                    existing = organized_data[found_cat][theme_key]
                    if p_rank[priority] < p_rank[existing["priority"]]:
                        existing["priority"] = priority
                    if title != existing["main_title"]:
                        existing["related_titles"].append({"title": title, "source": source})
                    if source not in existing["sources"]:
                        existing["sources"].append(source)

    generate_html(organized_data)
    print("✅ 已產生 index.html")


# ── 4. HTML 產生 ──────────────────────────────────────────────

def generate_html(data):
    js_data = {}
    p_rank = {"must": 0, "watch": 1, "normal": 2}
    for cat, items in data.items():
        if cat == "其他資訊":
            continue
        dept = DEPARTMENTS[cat]
        item_list = sorted(items.values(), key=lambda x: p_rank[x["priority"]])
        # full_text 可能很長，JSON 只傳必要欄位給前端
        for item in item_list:
            item["related_count"] = len(item["related_titles"])
        js_data[cat] = {
            "icon": dept["icon"],
            "label": dept["label"],
            "items": item_list
        }

    data_json = json.dumps(js_data, ensure_ascii=False).replace("</", "<\\/")

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>國發會經濟規劃科 · 每日新聞重點</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;600;700&family=Noto+Sans+TC:wght@300;400;500&display=swap" rel="stylesheet">
<style>
/* ── Reset & Root ── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg: #f7f6f3;
  --white: #ffffff;
  --border: #e5e3de;
  --border-hover: #cbc8c1;
  --text-p: #18171a;
  --text-s: #5c5a57;
  --text-m: #9e9c98;
  --accent: #1d4ed8;
  --accent-light: #eef2ff;

  --must-border: #f87171;
  --must-bg: #fef2f2;
  --must-tag: #b91c1c;
  --must-tag-bg: #fee2e2;

  --watch-border: #fbbf24;
  --watch-bg: #fffbeb;
  --watch-tag: #92400e;
  --watch-tag-bg: #fef3c7;

  --shadow-sm: 0 1px 4px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
  --radius: 8px;
}}
body {{
  background: var(--bg);
  color: var(--text-p);
  font-family: 'Noto Sans TC', sans-serif;
  min-height: 100vh;
  line-height: 1.65;
}}

/* ── Header ── */
.header {{
  background: var(--white);
  border-bottom: 1px solid var(--border);
  padding: 16px 40px;
  display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 100;
  box-shadow: var(--shadow-sm);
}}
.header-brand {{ display: flex; flex-direction: column; gap: 2px; }}
.header-title {{
  font-family: 'Noto Serif TC', serif;
  font-size: 17px; font-weight: 600; letter-spacing: 0.04em;
}}
.header-sub {{ font-size: 11px; color: var(--text-m); letter-spacing: 0.05em; }}
.header-actions {{ display: flex; align-items: center; gap: 10px; }}
.header-date {{ font-size: 13px; color: var(--text-s); font-weight: 500; margin-right: 4px; }}

.btn {{
  display: flex; align-items: center; gap: 5px;
  padding: 8px 15px; border-radius: 6px;
  font-size: 12px; font-family: inherit; font-weight: 500;
  cursor: pointer; border: 1px solid var(--border);
  transition: all 0.15s; white-space: nowrap;
}}
.btn-primary {{ background: var(--text-p); color: white; border-color: var(--text-p); }}
.btn-primary:hover {{ opacity: 0.85; }}
.btn-primary.success {{ background: #16a34a; border-color: #16a34a; }}
.btn-ghost {{ background: transparent; color: var(--text-s); }}
.btn-ghost:hover {{ border-color: var(--border-hover); color: var(--text-p); }}

/* ── Main layout ── */
.main {{ padding: 24px 40px; max-width: 960px; margin: 0 auto; }}

/* 優先級說明 */
.legend {{
  display: flex; align-items: center; gap: 14px;
  margin-bottom: 18px; font-size: 12px; color: var(--text-m);
}}
.leg {{ display: flex; align-items: center; gap: 4px; }}
.leg-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
.leg-dot.must {{ background: #ef4444; }}
.leg-dot.watch {{ background: #f59e0b; }}
.leg-dot.normal {{ background: #d1d5db; }}

/* ── Tabs ── */
.tabs {{
  display: flex; gap: 0;
  border-bottom: 2px solid var(--border);
  margin-bottom: 22px;
}}
.tab-btn {{
  padding: 9px 20px; border: none; background: transparent;
  font-size: 13px; font-family: inherit; color: var(--text-m);
  cursor: pointer; border-bottom: 2px solid transparent;
  margin-bottom: -2px; transition: all 0.15s; font-weight: 500;
  white-space: nowrap;
}}
.tab-btn:hover {{ color: var(--text-p); }}
.tab-btn.active {{ color: var(--accent); border-bottom-color: var(--accent); }}

/* ── Card ── */
.news-list {{ display: flex; flex-direction: column; gap: 8px; }}

.news-card {{
  background: var(--white);
  border: 1px solid var(--border);
  border-left: 4px solid #d1d5db;
  border-radius: var(--radius);
  overflow: hidden;
  transition: box-shadow 0.2s;
}}
.news-card:hover {{ box-shadow: var(--shadow-md); }}
.news-card.priority-must {{ border-left-color: var(--must-border); background: var(--must-bg); }}
.news-card.priority-watch {{ border-left-color: var(--watch-border); background: var(--watch-bg); }}

/* 卡片頂部（永遠可見）*/
.card-top {{
  padding: 14px 18px;
  display: flex; align-items: flex-start; gap: 12px;
  cursor: pointer;
}}
.card-top:hover .card-title {{ color: var(--accent); }}

.prio-col {{ flex-shrink: 0; padding-top: 2px; }}
.prio-badge {{
  font-size: 10px; font-weight: 600; letter-spacing: 0.04em;
  padding: 2px 8px; border-radius: 3px; white-space: nowrap;
}}
.prio-badge.must {{ background: var(--must-tag-bg); color: var(--must-tag); }}
.prio-badge.watch {{ background: var(--watch-tag-bg); color: var(--watch-tag); }}
.prio-badge.normal {{ background: var(--bg); color: var(--text-m); border: 1px solid var(--border); }}

.card-info {{ flex: 1; min-width: 0; }}
.card-title {{
  font-family: 'Noto Serif TC', serif;
  font-size: 15px; font-weight: 600; line-height: 1.55;
  color: var(--text-p); margin-bottom: 4px;
  transition: color 0.15s;
}}
.card-lead {{
  font-size: 12px; color: var(--text-s); margin-bottom: 7px;
}}
.card-meta {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
.src-tag {{
  font-size: 11px; color: var(--text-m);
  background: var(--bg); padding: 1px 7px;
  border-radius: 3px; border: 1px solid var(--border);
}}
.related-badge {{ font-size: 11px; color: var(--text-m); }}

.toggle-icon {{
  font-size: 18px; color: var(--text-m); flex-shrink: 0;
  transition: transform 0.25s, color 0.15s;
  align-self: flex-start; padding-top: 1px; line-height: 1;
}}
.news-card.open .toggle-icon {{ transform: rotate(90deg); color: var(--accent); }}

/* ── 展開區 ── */
.card-expand {{
  display: none;
  border-top: 1px solid var(--border);
}}
.news-card.open .card-expand {{ display: block; }}

/* 內部 tab bar */
.inner-tabs {{
  display: flex;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  padding: 0 18px;
}}
.inner-tab {{
  padding: 8px 14px; border: none; background: transparent;
  font-size: 12px; font-family: inherit; color: var(--text-m);
  cursor: pointer; border-bottom: 2px solid transparent;
  margin-bottom: -1px; transition: all 0.15s; font-weight: 500;
}}
.inner-tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
.inner-tab:hover:not(.active) {{ color: var(--text-p); }}

.inner-panel {{ display: none; padding: 18px 20px; }}
.inner-panel.active {{ display: block; animation: fadeIn 0.18s ease; }}
@keyframes fadeIn {{ from {{ opacity:0; transform:translateY(-3px); }} to {{ opacity:1; transform:translateY(0); }} }}

/* 新聞重點（summary）*/
.summary-block {{
  font-size: 14px; color: var(--text-s); line-height: 1.9;
  font-family: 'Noto Serif TC', serif;
  border-left: 3px solid var(--accent);
  padding-left: 14px;
  outline: none; white-space: pre-wrap;
}}
.summary-block:focus {{ background: #fffef9; border-radius: 0 4px 4px 0; }}
.summary-empty {{
  font-size: 13px; color: var(--text-m); font-style: italic;
  padding: 12px 14px; background: var(--bg);
  border-radius: 6px; border: 1px dashed var(--border);
}}

/* 全文區 */
.fulltext-body {{
  font-size: 13.5px; color: var(--text-s); line-height: 1.95;
  font-family: 'Noto Serif TC', serif; white-space: pre-wrap;
  outline: none;
}}
.fulltext-body:focus {{ background: #fffef9; padding: 4px; margin: -4px; border-radius: 4px; }}
.fulltext-paste {{
  width: 100%; min-height: 100px; padding: 12px;
  border: 1px dashed var(--border); border-radius: 6px;
  font-family: 'Noto Serif TC', serif; font-size: 13.5px;
  color: var(--text-s); background: var(--bg);
  resize: vertical; outline: none; line-height: 1.9;
}}
.fulltext-paste:focus {{ border-color: var(--accent); background: white; }}
.fulltext-hint {{
  font-size: 12px; color: var(--text-m); margin-bottom: 10px;
  font-style: italic;
}}

/* 相關報導 */
.related-row {{
  display: flex; align-items: flex-start; gap: 8px;
  padding: 8px 0; border-bottom: 1px dashed var(--border);
  font-size: 13px; color: var(--text-s);
}}
.related-row:last-child {{ border-bottom: none; }}
.related-bullet {{ color: var(--text-m); flex-shrink: 0; margin-top: 1px; }}
.related-src {{ font-size: 11px; color: var(--text-m); flex-shrink: 0; }}

.empty-state {{
  text-align: center; padding: 50px; color: var(--text-m); font-size: 14px;
}}

/* ── Print ── */
@media print {{
  .header {{ position: static; box-shadow: none; }}
  .btn, .tabs, .inner-tabs, .fulltext-paste, .fulltext-hint {{ display: none !important; }}
  .news-card {{ break-inside: avoid; }}
  .card-expand {{ display: block !important; }}
  .inner-panel {{ display: block !important; padding: 12px 18px; }}
  .inner-panel + .inner-panel {{ border-top: 1px solid var(--border); }}
}}
@media (max-width: 640px) {{
  .header {{ padding: 12px 16px; }}
  .main {{ padding: 14px 16px; }}
  .header-date {{ display: none; }}
}}
</style>
</head>
<body>

<header class="header">
  <div class="header-brand">
    <span class="header-title">國家發展委員會 · 經濟規劃科</span>
    <span class="header-sub">每日新聞重點整理 · INTERNAL USE ONLY</span>
  </div>
  <div class="header-actions">
    <span class="header-date" id="date-label"></span>
    <button class="btn btn-ghost" onclick="window.print()">🖨 列印／PDF</button>
    <button class="btn btn-primary" id="btn-copy">📋 複製今日摘要</button>
  </div>
</header>

<main class="main">
  <div class="legend">
    <span>優先級：</span>
    <div class="leg"><span class="leg-dot must"></span>必看</div>
    <div class="leg"><span class="leg-dot watch"></span>關注</div>
    <div class="leg"><span class="leg-dot normal"></span>一般</div>
  </div>
  <div class="tabs" id="tabs"></div>
  <div class="news-list" id="news-list"></div>
</main>

<script>
const DATA = {data_json};
const CATS = Object.keys(DATA);
let currentTab = 'all';
const pasteStore = {{}};  // 暫存使用者手動貼入的全文

const PRIO_LABEL = {{ must: '必看', watch: '關注', normal: '一般' }};

// ── Tabs ──
function renderTabs() {{
  const el = document.getElementById('tabs');
  el.innerHTML = '';
  el.appendChild(mkTab('全部', 'all', true));
  CATS.forEach(cat => {{
    const d = DATA[cat];
    const mustN = d.items.filter(i => i.priority === 'must').length;
    const label = d.icon + ' ' + cat + (mustN ? ' ⚑' + mustN : '');
    el.appendChild(mkTab(label, cat, false));
  }});
}}
function mkTab(label, id, active) {{
  const b = document.createElement('button');
  b.className = 'tab-btn' + (active ? ' active' : '');
  b.dataset.id = id;
  b.textContent = label;
  b.onclick = () => switchTab(id);
  return b;
}}
function switchTab(id) {{
  currentTab = id;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.id === id));
  renderList();
}}

// ── List ──
function renderList() {{
  const list = document.getElementById('news-list');
  list.innerHTML = '';
  const targets = currentTab === 'all' ? CATS : [currentTab];
  let n = 0;
  targets.forEach(cat => {{
    DATA[cat].items.forEach(item => {{
      list.appendChild(makeCard(item, cat));
      n++;
    }});
  }});
  if (!n) {{
    const e = document.createElement('div');
    e.className = 'empty-state';
    e.textContent = '目前無相關新聞資料';
    list.appendChild(e);
  }}
}}

// ── Card ──
function makeCard(item, cat) {{
  const card = document.createElement('div');
  card.className = 'news-card priority-' + item.priority;

  const srcHtml = item.sources.map(s => `<span class="src-tag">${{s}}</span>`).join('');
  const relN = item.related_count || 0;

  card.innerHTML = `
    <div class="card-top">
      <div class="prio-col">
        <span class="prio-badge ${{item.priority}}">${{PRIO_LABEL[item.priority]}}</span>
      </div>
      <div class="card-info">
        <div class="card-title">${{item.main_title}}</div>
        <div class="card-lead">→ ${{item.lead}}</div>
        <div class="card-meta">
          ${{srcHtml}}
          ${{relN ? `<span class="related-badge">＋${{relN}} 則相關</span>` : ''}}
        </div>
      </div>
      <span class="toggle-icon">›</span>
    </div>
    <div class="card-expand"></div>`;

  card.querySelector('.card-top').addEventListener('click', () => {{
    const isOpen = card.classList.contains('open');
    if (!isOpen) buildExpand(card, item);
    card.classList.toggle('open');
  }});

  return card;
}}

// ── 展開區（首次展開時才建立）──
function buildExpand(card, item) {{
  const expand = card.querySelector('.card-expand');
  if (expand.dataset.ready) return;
  expand.dataset.ready = '1';

  const tabBar = document.createElement('div');
  tabBar.className = 'inner-tabs';
  expand.appendChild(tabBar);

  const panels = [];

  function addInnerTab(label, active) {{
    const t = document.createElement('button');
    t.className = 'inner-tab' + (active ? ' active' : '');
    t.textContent = label;
    const idx = panels.length;
    t.onclick = () => {{
      tabBar.querySelectorAll('.inner-tab').forEach((x, i) => x.classList.toggle('active', i === idx));
      panels.forEach((p, i) => p.classList.toggle('active', i === idx));
    }};
    tabBar.appendChild(t);
    const p = document.createElement('div');
    p.className = 'inner-panel' + (active ? ' active' : '');
    expand.appendChild(p);
    panels.push(p);
    return p;
  }}

  // ① 新聞重點（summary）
  const p1 = addInnerTab('新聞重點', true);
  if (item.summary) {{
    const div = document.createElement('div');
    div.className = 'summary-block';
    div.contentEditable = 'true';
    div.textContent = item.summary;
    p1.appendChild(div);
  }} else {{
    p1.innerHTML = `<div class="summary-empty">⚠️ 自動抓取失敗，請切換至「新聞全文」手動貼入內容</div>`;
  }}

  // ② 新聞全文
  const p2 = addInnerTab('新聞全文', false);
  const storeKey = item.main_title;
  if (item.full_text) {{
    const div = document.createElement('div');
    div.className = 'fulltext-body';
    div.contentEditable = 'true';
    div.textContent = item.full_text;
    div.addEventListener('input', e => {{ pasteStore[storeKey] = e.target.innerText; }});
    p2.appendChild(div);
  }} else {{
    const saved = pasteStore[storeKey] || '';
    p2.innerHTML = `<div class="fulltext-hint">📋 未能自動擷取全文，請手動貼入：</div>
      <textarea class="fulltext-paste" placeholder="在此貼入《${{item.main_title}}》全文...">${{saved}}</textarea>`;
    p2.querySelector('textarea').addEventListener('input', e => {{ pasteStore[storeKey] = e.target.value; }});
  }}

  // ③ 相關報導（有才顯示）
  if (item.related_titles && item.related_titles.length > 0) {{
    const p3 = addInnerTab(`相關報導 (${{item.related_titles.length}})`, false);
    item.related_titles.forEach(r => {{
      const row = document.createElement('div');
      row.className = 'related-row';
      const title = typeof r === 'object' ? r.title : r;
      const src = typeof r === 'object' ? r.source : '';
      row.innerHTML = `<span class="related-bullet">▸</span>
        <span style="flex:1">${{title}}</span>
        ${{src ? `<span class="related-src">${{src}}</span>` : ''}}`;
      p3.appendChild(row);
    }});
  }}
}}

// ── 複製今日摘要 ──
document.getElementById('btn-copy').addEventListener('click', () => {{
  const now = new Date();
  const roc = now.getFullYear() - 1911;
  const mm = String(now.getMonth()+1).padStart(2,'0');
  const dd = String(now.getDate()).padStart(2,'0');
  const dateStr = roc + '.' + mm + '.' + dd;

  let text = `【${{dateStr}} 經濟規劃科 · 每日新聞重點】\n`;
  text += `${'═'.repeat(36)}\n\n`;

  const targets = currentTab === 'all' ? CATS : [currentTab];
  targets.forEach(cat => {{
    const d = DATA[cat];
    text += `${{d.icon}} ${{cat}}\n${'─'.repeat(30)}\n`;
    d.items.forEach(item => {{
      text += `▌ [${{PRIO_LABEL[item.priority]}}] ${{item.main_title}}\n`;
      text += `   來源：${{item.sources.join('、')}}\n`;
      text += `   → ${{item.lead}}\n`;
      if (item.summary) text += `   重點：${{item.summary}}\n`;
      if (item.related_titles && item.related_titles.length > 0) {{
        const rel = item.related_titles.map(r => typeof r === 'object' ? r.title : r);
        text += `   相關：${{rel.join('；')}}\n`;
      }}
      text += `\n`;
    }});
    text += `\n`;
  }});

  navigator.clipboard.writeText(text).then(() => {{
    const btn = document.getElementById('btn-copy');
    btn.classList.add('success');
    btn.innerHTML = '✓ 已複製';
    setTimeout(() => {{
      btn.classList.remove('success');
      btn.innerHTML = '📋 複製今日摘要';
    }}, 2000);
  }});
}});

// ── 日期（民國年）──
const now = new Date();
const roc = now.getFullYear() - 1911;
document.getElementById('date-label').textContent =
  '民國 ' + roc + ' 年 ' + (now.getMonth()+1) + ' 月 ' + now.getDate() + ' 日';

renderTabs();
renderList();
</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    run_dashboard()
