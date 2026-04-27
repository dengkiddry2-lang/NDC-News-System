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
    if any(k in title for k in MUST_READ):
        return "must"
    if any(k in title for k in WATCH):
        return "watch"
    return "normal"

def get_lead(title, cat):
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


# ── 2. PDF 結構說明 ──────────────────────────────────────────────
#
# 此 PDF 結構：
#   - 前幾頁：目錄（表格，含編號、標題、來源媒體）
#   - 內文頁：每篇新聞獨立一頁
#       第一行（可能跨兩行）：標題
#       來源行：「來源:xxx 版面:xxx 類別:xxx 時間:xxx 作者:xxx」
#       來源行之後：正文
#   - 分隔頁：「回到目錄\n頁碼」，可跳過
#
# 正確抓法：先掃描所有頁面建立「標題→正文」索引，
# 再從目錄標題去比對索引（去空格後取前 10 字為 key）。

def build_article_index(pdf):
    """
    掃描 PDF 所有頁面，建立「去空格標題 → 完整正文」索引。

    通式判斷邏輯（不依賴固定字串，適用任何格式的日報 PDF）：
      'start' — 頁面含「來源:」行 → 內文首頁
      'toc'   — 頁面含表格 → 目錄頁
      'sep'   — 非首頁且去空格文字 < 30 字 → 分隔/空白頁
      'cont'  — 其餘 → 內文續頁，合併到前一篇

    跨頁新聞：cont 頁的內容直接接續到前一篇 start 的正文。
    連續多頁的 cont 也支援。
    """
    results = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        has_source = any(l.startswith("來源:") for l in lines[:8])
        has_table = page.extract_table() is not None
        char_count = len("".join(lines))

        if has_source:
            cat = "start"
        elif has_table:
            cat = "toc"
        elif char_count < 30:   # 分隔頁文字極少（如「回到目錄」+頁碼）
            cat = "sep"
        else:
            cat = "cont"
        results.append((cat, lines))

    index = {}
    last_key = None

    for cat, lines in results:
        if cat == "start":
            src_idx = next((j for j, l in enumerate(lines) if l.startswith("來源:")), None)
            if src_idx is None:
                last_key = None
                continue
            title_key = "".join(lines[:src_idx]).replace(" ", "")
            title_key = title_key.encode("utf-8", errors="replace").decode("utf-8")
            body_lines = [l for l in lines[src_idx + 1:] if not l.strip().isdigit()]
            body = "\n".join(body_lines).encode("utf-8", errors="replace").decode("utf-8")
            if title_key:
                index[title_key] = body
                last_key = title_key

        elif cat == "cont" and last_key:
            extra_lines = [l for l in lines if not l.strip().isdigit()]
            extra = "\n".join(extra_lines).encode("utf-8", errors="replace").decode("utf-8")
            if extra:
                index[last_key] = index[last_key] + "\n" + extra
            # last_key 維持，允許連續多頁續頁

        else:
            # sep / toc：重置，不合併
            last_key = None

    return index


def find_article(index, toc_title):
    """
    從目錄標題在索引中找出對應正文。
    策略：去空格後取前 10 字作為 key 比對。
    """
    search_key = toc_title.replace(" ", "")[:10]
    for art_key, body in index.items():
        if search_key in art_key:
            return body
    return ""


def extract_summary(body, limit=280):
    """
    從正文取第一段有意義的句子（含句號或逗號，長度 >= 20 字）。
    """
    if not body:
        return ""
    for line in body.split("\n"):
        line = line.strip()
        if len(line) >= 20 and ("，" in line or "。" in line or "、" in line):
            return line[:limit]
    # fallback：取第一行
    first = body.split("\n")[0].strip()
    return first[:limit]


# ── 3. 主程式 ──────────────────────────────────────────────

def run_dashboard():
    if not os.path.exists("data"):
        os.makedirs("data")
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("data 資料夾內找不到 PDF")
        return

    pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join("data", x)))
    latest_pdf = os.path.join("data", pdf_files[-1])
    print(f"正在分析: {latest_pdf}")

    organized_data = {cat: {} for cat in DEPARTMENTS.keys()}
    organized_data["其他資訊"] = {}

    with pdfplumber.open(latest_pdf) as pdf:
        print("建立文章索引中...")
        article_index = build_article_index(pdf)
        print(f"找到 {len(article_index)} 篇內文頁")

        # 掃描目錄頁（前 10 頁內的表格）
        for page in pdf.pages[:10]:
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

                # 從索引中找正確的正文
                full_text = find_article(article_index, title)
                summary = extract_summary(full_text)
                priority = get_priority(title)
                lead = get_lead(title, found_cat)
                theme_key = title[:8]

                if theme_key not in organized_data[found_cat]:
                    organized_data[found_cat][theme_key] = {
                        "main_title": title,
                        "related_titles": [],
                        "sources": [source],
                        "full_text": full_text,
                        "summary": summary,
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
        for item in item_list:
            item["related_count"] = len(item["related_titles"])
        js_data[cat] = {
            "icon": dept["icon"],
            "label": dept["label"],
            "items": item_list
        }

    data_json = json.dumps(js_data, ensure_ascii=True).replace("</", "<\\/")

    sep_double = "\u2550" * 36
    sep_single = "\u2500" * 30

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>國發會經濟規劃科 · 每日新聞重點</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;600;700&family=Noto+Sans+TC:wght@300;400;500&display=swap" rel="stylesheet">
<style>
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
.main {{ padding: 24px 40px; max-width: 960px; margin: 0 auto; }}
.legend {{
  display: flex; align-items: center; gap: 14px;
  margin-bottom: 18px; font-size: 12px; color: var(--text-m);
}}
.leg {{ display: flex; align-items: center; gap: 4px; }}
.leg-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
.leg-dot.must {{ background: #ef4444; }}
.leg-dot.watch {{ background: #f59e0b; }}
.leg-dot.normal {{ background: #d1d5db; }}
.tabs {{
  display: flex;
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
.card-lead {{ font-size: 12px; color: var(--text-s); margin-bottom: 7px; }}
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
.card-expand {{ display: none; border-top: 1px solid var(--border); }}
.news-card.open .card-expand {{ display: block; }}
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
.fulltext-hint {{ font-size: 12px; color: var(--text-m); margin-bottom: 10px; font-style: italic; }}
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
const pasteStore = {{}};
const PRIO_LABEL = {{ must: '必看', watch: '關注', normal: '一般' }};

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

function makeCard(item, cat) {{
  const card = document.createElement('div');
  card.className = 'news-card priority-' + item.priority;
  const srcHtml = item.sources.map(s => '<span class="src-tag">' + s + '</span>').join('');
  const relN = item.related_count || 0;
  card.innerHTML =
    '<div class="card-top">' +
      '<div class="prio-col"><span class="prio-badge ' + item.priority + '">' + PRIO_LABEL[item.priority] + '</span></div>' +
      '<div class="card-info">' +
        '<div class="card-title">' + item.main_title + '</div>' +
        '<div class="card-lead">\u2192 ' + item.lead + '</div>' +
        '<div class="card-meta">' + srcHtml + (relN ? '<span class="related-badge">\uff0b' + relN + ' \u5247\u76f8\u95dc</span>' : '') + '</div>' +
      '</div>' +
      '<span class="toggle-icon">\u203a</span>' +
    '</div>' +
    '<div class="card-expand"></div>';

  card.querySelector('.card-top').addEventListener('click', () => {{
    const isOpen = card.classList.contains('open');
    if (!isOpen) buildExpand(card, item);
    card.classList.toggle('open');
  }});
  return card;
}}

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

  // Panel 1: 新聞重點
  const p1 = addInnerTab('\u65b0\u8a0a\u91cd\u9ede', true);
  if (item.summary) {{
    const div = document.createElement('div');
    div.className = 'summary-block';
    div.contentEditable = 'true';
    div.textContent = item.summary;
    p1.appendChild(div);
  }} else {{
    p1.innerHTML = '<div class="summary-empty">\u26a0\ufe0f \u81ea\u52d5\u6293\u53d6\u5931\u6557\uff0c\u8acb\u5207\u63db\u81f3\u300c\u65b0\u8a0a\u5168\u6587\u300d\u624b\u52d5\u8cbc\u5165</div>';
  }}

  // Panel 2: 新聞全文
  const p2 = addInnerTab('\u65b0\u8a0a\u5168\u6587', false);
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
    p2.innerHTML = '<div class="fulltext-hint">\ud83d\udccb \u672a\u80fd\u81ea\u52d5\u64f7\u53d6\uff0c\u8acb\u624b\u52d5\u8cbc\u5165\uff1a</div>' +
      '<textarea class="fulltext-paste" placeholder="\u5728\u6b64\u8cbc\u5165\u300a' + item.main_title + '\u300b\u5168\u6587...">' + saved + '</textarea>';
    p2.querySelector('textarea').addEventListener('input', e => {{ pasteStore[storeKey] = e.target.value; }});
  }}

  // Panel 3: 相關報導
  if (item.related_titles && item.related_titles.length > 0) {{
    const p3 = addInnerTab('\u76f8\u95dc\u5831\u5c0e (' + item.related_titles.length + ')', false);
    item.related_titles.forEach(r => {{
      const row = document.createElement('div');
      row.className = 'related-row';
      const t = typeof r === 'object' ? r.title : r;
      const s = typeof r === 'object' ? r.source : '';
      row.innerHTML =
        '<span class="related-bullet">\u25b8</span>' +
        '<span style="flex:1">' + t + '</span>' +
        (s ? '<span class="related-src">' + s + '</span>' : '');
      p3.appendChild(row);
    }});
  }}
}}

document.getElementById('btn-copy').addEventListener('click', () => {{
  const now = new Date();
  const roc = now.getFullYear() - 1911;
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  const dateStr = roc + '.' + mm + '.' + dd;
  const sep1 = '{sep_double}';
  const sep2 = '{sep_single}';

  let text = '\u3010' + dateStr + ' \u7d93\u6fdf\u898f\u5283\u79d1 \u30b7 \u6bcf\u65e5\u65b0\u8a0a\u91cd\u9ede\u3011\n' + sep1 + '\n\n';
  const targets = currentTab === 'all' ? CATS : [currentTab];
  targets.forEach(cat => {{
    const d = DATA[cat];
    text += d.icon + ' ' + cat + '\n' + sep2 + '\n';
    d.items.forEach(item => {{
      text += '\u258c [' + PRIO_LABEL[item.priority] + '] ' + item.main_title + '\n';
      text += '   \u4f86\u6e90\uff1a' + item.sources.join('\u3001') + '\n';
      text += '   \u2192 ' + item.lead + '\n';
      if (item.summary) text += '   \u91cd\u9ede\uff1a' + item.summary + '\n';
      if (item.related_titles && item.related_titles.length > 0) {{
        const rel = item.related_titles.map(r => typeof r === 'object' ? r.title : r);
        text += '   \u76f8\u95dc\uff1a' + rel.join('\uff1b') + '\n';
      }}
      text += '\n';
    }});
    text += '\n';
  }});

  navigator.clipboard.writeText(text).then(() => {{
    const btn = document.getElementById('btn-copy');
    btn.classList.add('success');
    btn.innerHTML = '\u2713 \u5df2\u8907\u88fd';
    setTimeout(() => {{
      btn.classList.remove('success');
      btn.innerHTML = '\ud83d\udccb \u8907\u88fd\u4eca\u65e5\u6458\u8981';
    }}, 2000);
  }});
}});

const now = new Date();
const roc = now.getFullYear() - 1911;
document.getElementById('date-label').textContent =
  '\u6c11\u570b ' + roc + ' \u5e74 ' + (now.getMonth() + 1) + ' \u6708 ' + now.getDate() + ' \u65e5';

renderTabs();
renderList();
</script>
</body>
</html>"""

    html_content = html_content.encode("utf-8", errors="replace").decode("utf-8")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    run_dashboard()
