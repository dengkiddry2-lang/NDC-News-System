import pdfplumber
import os
import json

# ── 分類定義 ──────────────────────────────────────────────
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

# ── 優先級規則 ────────────────────────────────────────────
# 必看：高度敏感、數據公告、重大政策
MUST_READ = [
    "Fed", "FOMC", "主計", "主計處", "台積電財報", "GDP", "升息", "降息",
    "央行理監事", "利率決議", "通膨數據", "CPI公布", "外銷訂單", "貿易統計",
    "戰爭", "地緣", "衝突", "制裁", "供應鏈斷鏈"
]
# 關注：有量化意涵但非即時公告
WATCH = [
    "出口", "進口", "資本支出", "AI", "台積電", "半導體", "景氣",
    "匯率", "油價", "通膨", "物價", "川普", "美伊", "離岸風電", "淨零", "算力"
]

def get_priority(title):
    if any(k in title for k in MUST_READ):
        return "must"    # 必看
    if any(k in title for k in WATCH):
        return "watch"   # 關注
    return "normal"      # 一般

def get_lead(title, cat):
    """卡片導語：對總經的影響，一句話"""
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
    return "一般經濟資訊，建議維持現行預測參數"

def get_analysis(title, cat):
    """展開後的三段判讀"""
    if any(k in title for k in ["資本支出", "AI", "設備", "伺服器"]):
        return (
            "本則新聞涉及 AI 相關資本支出與供應鏈投資動向，顯示市場對人工智慧硬體基礎建設需求持續擴張。"
            "\n\n從總體面觀察，此類資本支出增加將拉抬民間投資（I）分項，有助於支撐 GDP 成長動能。"
            "\n\n建議持續追蹤台灣 AI 伺服器出口訂單及相關供應商接單狀況，以評估實際需求是否符合預期。"
        )
    if any(k in title for k in ["出口", "訂單", "外銷"]):
        return (
            "本則新聞反映外需動能變化，出口數據為台灣經濟的核心領先指標之一。"
            "\n\n若出口呈現回穩或成長趨勢，代表主要貿易夥伴（美、中、歐）景氣同步改善，淨出口（X-M）對 GDP 的貢獻度將上升。"
            "\n\n需留意匯率走勢對出口競爭力的影響，以及美中貿易政策對訂單的排擠效應。"
        )
    if any(k in title for k in ["通膨", "油價", "物價", "CPI"]):
        return (
            "本則新聞涉及物價或通膨走勢，供給端成本壓力仍是現階段不確定因素之一。"
            "\n\n若通膨持續超出目標區間，將對貨幣政策路徑產生制約，影響央行是否調整利率決策。"
            "\n\n建議同步觀察核心 CPI 與生產者物價指數（PPI），以判斷成本壓力是否向下游消費端傳導。"
        )
    if any(k in title for k in ["川普", "戰爭", "地緣", "衝突", "制裁"]):
        return (
            "本則新聞屬地緣政治或國際情勢範疇，屬系統性風險訊號，對金融市場與貿易流向均可能產生非線性衝擊。"
            "\n\n地緣風險升溫通常導致風險資產承壓，並推升能源與避險資產（黃金、美元）價格。"
            "\n\n建議在預測模型中調高不確定性溢價，並規劃情境分析（基準、樂觀、悲觀）以覆蓋尾部風險。"
        )
    if any(k in title for k in ["Fed", "利率", "央行", "升息", "降息"]):
        return (
            "本則新聞聚焦貨幣政策走向，Fed 或各國央行的利率決策對全球資金流向與匯率具有直接影響。"
            "\n\n若市場預期利率維持高檔，將壓抑資產評價並影響企業融資成本；反之，降息訊號有助於刺激需求。"
            "\n\n台灣央行的決策通常與 Fed 方向保持一定連動，建議同步追蹤台美利率差對新台幣匯率的傳導效果。"
        )
    if any(k in title for k in ["政策", "計畫", "預算", "國發會"]):
        return (
            "本則新聞涉及政府政策規畫或預算配置，為經濟預測的重要結構性變數。"
            "\n\n政府支出（G）是 GDP 支出面的直接構成要素，預算執行進度與新政策方向將影響公共投資與民間信心。"
            "\n\n建議追蹤政策落地時程，評估對相關產業鏈（如綠能、數位基礎建設）的乘數效果。"
        )
    return (
        "本則新聞為一般性經濟資訊，目前不具明顯的高度風險或重大政策意涵。"
        "\n\n建議維持現行預測模型參數，持續追蹤後續相關數據發布，以確認訊號方向是否一致。"
        "\n\n若後續出現相關新聞佐證，可考慮對應調整預測假設或情境設定。"
    )

def extract_full_text_by_title(pdf, title):
    search_keys = [title[i:i+4] for i in range(0, min(len(title), 16), 4) if title[i:i+4].strip()]
    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        for kw in search_keys:
            idx = text.find(kw)
            if idx != -1:
                start = max(0, idx - 80)
                end = min(len(text), idx + 1000)
                snippet = text[start:end].strip()
                if len(snippet) > 80:
                    return snippet
    return ""

def run_dashboard():
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("找不到 PDF 檔案")
        return
    latest_pdf = os.path.join("data", sorted(pdf_files)[-1])

    organized_data = {cat: {} for cat in DEPARTMENTS.keys()}
    organized_data["其他資訊"] = {}

    with pdfplumber.open(latest_pdf) as pdf:
        for page in pdf.pages[:5]:
            table = page.extract_table()
            if not table:
                continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]:
                    continue
                title = str(row[1]).replace("\n", "").strip()
                source = str(row[2]).replace("\n", " ").strip() if len(row) > 2 else "未知"
                full_text_col = str(row[3]).replace("\n", " ").strip() if len(row) > 3 else ""

                if len(title) < 5 or "新聞議題" in title:
                    continue

                found_cat = "其他資訊"
                for cat, info in DEPARTMENTS.items():
                    if any(k in title for k in info["keywords"]):
                        found_cat = cat
                        break

                if not full_text_col or len(full_text_col) < 30:
                    full_text_col = extract_full_text_by_title(pdf, title)

                theme_key = title[:8]
                priority = get_priority(title)
                lead = get_lead(title, found_cat)
                analysis = get_analysis(title, found_cat)

                if theme_key not in organized_data[found_cat]:
                    organized_data[found_cat][theme_key] = {
                        "main_title": title,
                        "related_titles": [],
                        "sources": [source],
                        "full_texts": {title: full_text_col} if full_text_col else {},
                        "priority": priority,
                        "lead": lead,
                        "analysis": analysis
                    }
                else:
                    # 升級優先級（取較高者）
                    prio_rank = {"must": 0, "watch": 1, "normal": 2}
                    if prio_rank[priority] < prio_rank[organized_data[found_cat][theme_key]["priority"]]:
                        organized_data[found_cat][theme_key]["priority"] = priority
                    if title != organized_data[found_cat][theme_key]["main_title"]:
                        organized_data[found_cat][theme_key]["related_titles"].append(title)
                        if full_text_col:
                            organized_data[found_cat][theme_key]["full_texts"][title] = full_text_col
                    if source not in organized_data[found_cat][theme_key]["sources"]:
                        organized_data[found_cat][theme_key]["sources"].append(source)

    generate_html(organized_data)
    print("✅ 已產生 index.html")


def generate_html(data):
    js_data = {}
    for cat, items in data.items():
        if cat == "其他資訊":
            continue
        dept_info = DEPARTMENTS.get(cat, {"icon": "📂", "label": cat})
        item_list = []
        for info in items.values():
            item_list.append({
                "main_title": info["main_title"],
                "related_titles": info["related_titles"],
                "sources": info["sources"],
                "full_texts": info.get("full_texts", {}),
                "priority": info["priority"],
                "lead": info["lead"],
                "analysis": info["analysis"]
            })
        # 排序：必看 → 關注 → 一般
        prio_rank = {"must": 0, "watch": 1, "normal": 2}
        item_list.sort(key=lambda x: prio_rank[x["priority"]])
        js_data[cat] = {
            "icon": dept_info["icon"],
            "label": dept_info["label"],
            "items": item_list
        }

    data_json = json.dumps(js_data, ensure_ascii=False, indent=2).replace("</", "<\\/")

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>國發會經濟規劃科 · 每日新聞重點</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500;600;700&family=Noto+Sans+TC:wght@300;400;500&display=swap" rel="stylesheet">
<style>
/* ── Reset & Root ── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --white: #ffffff;
  --bg: #f7f6f3;
  --surface: #ffffff;
  --border: #e5e3de;
  --border-hover: #cbc8c1;
  --text-primary: #18171a;
  --text-secondary: #5c5a57;
  --text-muted: #9e9c98;
  --accent: #1d4ed8;
  --accent-light: #eef2ff;

  /* 優先級色 */
  --must-bg: #fef2f2;
  --must-border: #fca5a5;
  --must-text: #b91c1c;
  --must-tag-bg: #fee2e2;

  --watch-bg: #fffbeb;
  --watch-border: #fcd34d;
  --watch-text: #92400e;
  --watch-tag-bg: #fef3c7;

  --normal-bg: #ffffff;
  --normal-border: #e5e3de;
  --normal-text: #5c5a57;

  --shadow-sm: 0 1px 4px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
  --shadow-xl: 0 20px 60px rgba(0,0,0,0.15);
  --radius: 8px;
  --radius-sm: 5px;
}}

body {{
  background: var(--bg);
  color: var(--text-primary);
  font-family: 'Noto Sans TC', sans-serif;
  min-height: 100vh;
  line-height: 1.65;
}}

/* ── Header ── */
.header {{
  background: var(--white);
  border-bottom: 1px solid var(--border);
  padding: 18px 40px;
  display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 100;
  box-shadow: var(--shadow-sm);
}}
.header-left {{ display: flex; flex-direction: column; gap: 2px; }}
.header-title {{
  font-family: 'Noto Serif TC', serif;
  font-size: 17px; font-weight: 600;
  color: var(--text-primary); letter-spacing: 0.04em;
}}
.header-sub {{ font-size: 11px; color: var(--text-muted); letter-spacing: 0.06em; }}
.header-right {{ display: flex; align-items: center; gap: 12px; }}
.header-date {{ font-size: 13px; color: var(--text-secondary); font-weight: 500; }}

.btn-copy {{
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px;
  background: var(--text-primary); color: white;
  border: none; border-radius: var(--radius-sm);
  font-size: 12px; font-family: inherit; font-weight: 500;
  cursor: pointer; transition: opacity 0.15s; letter-spacing: 0.03em;
}}
.btn-copy:hover {{ opacity: 0.85; }}
.btn-copy.copied {{ background: #16a34a; }}

.btn-print {{
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px;
  background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  font-size: 12px; font-family: inherit;
  cursor: pointer; transition: all 0.15s;
}}
.btn-print:hover {{ border-color: var(--border-hover); color: var(--text-primary); }}

/* ── Layout ── */
.main {{ padding: 28px 40px; max-width: 1100px; margin: 0 auto; }}

/* ── Legend ── */
.legend {{
  display: flex; align-items: center; gap: 16px;
  margin-bottom: 20px; font-size: 12px; color: var(--text-muted);
}}
.legend-item {{ display: flex; align-items: center; gap: 5px; }}
.prio-dot {{
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}}
.prio-dot.must {{ background: #ef4444; }}
.prio-dot.watch {{ background: #f59e0b; }}
.prio-dot.normal {{ background: #d1d5db; }}

/* ── Tabs ── */
.tabs {{
  display: flex; gap: 2px; margin-bottom: 24px;
  border-bottom: 2px solid var(--border);
}}
.tab-btn {{
  padding: 10px 22px; border: none; background: transparent;
  font-size: 13px; font-family: inherit; color: var(--text-muted);
  cursor: pointer; transition: all 0.15s; border-bottom: 2px solid transparent;
  margin-bottom: -2px; white-space: nowrap; font-weight: 500;
}}
.tab-btn:hover {{ color: var(--text-primary); }}
.tab-btn.active {{ color: var(--accent); border-bottom-color: var(--accent); }}

/* ── News List (single column) ── */
.news-list {{ display: flex; flex-direction: column; gap: 10px; }}

/* ── Card ── */
.news-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--border);
  border-radius: var(--radius);
  transition: box-shadow 0.2s, border-color 0.2s;
  overflow: hidden;
}}
.news-card:hover {{ box-shadow: var(--shadow-md); }}
.news-card.priority-must {{
  border-left-color: var(--must-border);
  background: var(--must-bg);
}}
.news-card.priority-watch {{
  border-left-color: var(--watch-border);
  background: var(--watch-bg);
}}

.card-main {{
  padding: 16px 20px;
  display: flex; align-items: flex-start; gap: 14px;
  cursor: pointer;
}}
.card-main:hover .card-title {{ color: var(--accent); }}

.card-left {{ flex-shrink: 0; padding-top: 2px; }}
.prio-badge {{
  font-size: 10px; font-weight: 600; padding: 2px 7px;
  border-radius: 3px; letter-spacing: 0.05em; white-space: nowrap;
}}
.prio-badge.must {{
  background: var(--must-tag-bg); color: var(--must-text);
}}
.prio-badge.watch {{
  background: var(--watch-tag-bg); color: var(--watch-text);
}}
.prio-badge.normal {{
  background: var(--bg); color: var(--text-muted); border: 1px solid var(--border);
}}

.card-body {{ flex: 1; min-width: 0; }}
.card-title {{
  font-family: 'Noto Serif TC', serif;
  font-size: 15px; font-weight: 600; line-height: 1.55;
  color: var(--text-primary); margin-bottom: 5px;
  transition: color 0.15s;
}}
.card-lead {{
  font-size: 12px; color: var(--text-secondary);
  margin-bottom: 8px; line-height: 1.5;
}}
.card-meta-row {{
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}}
.source-tag {{
  font-size: 11px; color: var(--text-muted);
  background: var(--bg); padding: 1px 7px;
  border-radius: 3px; border: 1px solid var(--border);
}}
.related-badge {{
  font-size: 11px; color: var(--text-muted);
}}
.card-arrow {{
  font-size: 16px; color: var(--text-muted); flex-shrink: 0;
  transition: transform 0.25s, color 0.15s; padding-top: 2px;
  align-self: flex-start;
}}
.news-card.open .card-arrow {{ transform: rotate(90deg); color: var(--accent); }}

/* ── Expand Panel ── */
.card-detail {{
  display: none; border-top: 1px solid var(--border);
  animation: slideDown 0.2s ease;
}}
@keyframes slideDown {{
  from {{ opacity: 0; transform: translateY(-5px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
.news-card.open .card-detail {{ display: block; }}

.detail-tabs {{
  display: flex; border-bottom: 1px solid var(--border);
  background: var(--bg); padding: 0 20px;
}}
.detail-tab {{
  padding: 9px 16px; border: none; background: transparent;
  font-size: 12px; font-family: inherit; color: var(--text-muted);
  cursor: pointer; border-bottom: 2px solid transparent;
  margin-bottom: -1px; transition: all 0.15s; font-weight: 500;
}}
.detail-tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
.detail-tab:hover:not(.active) {{ color: var(--text-primary); }}

.detail-panel {{ display: none; padding: 20px; }}
.detail-panel.active {{ display: block; }}

/* 判讀摘要 */
.analysis-block {{
  font-size: 13.5px; color: var(--text-secondary);
  line-height: 1.9; font-family: 'Noto Serif TC', serif;
  white-space: pre-line; outline: none;
}}
.analysis-block:focus {{ background: #fffef9; border-radius: 4px; padding: 4px; margin: -4px; }}

/* 全文區 */
.fulltext-body {{
  font-size: 14px; color: var(--text-secondary);
  line-height: 2; font-family: 'Noto Serif TC', serif;
  white-space: pre-wrap; outline: none;
}}
.fulltext-body:focus {{ background: #fffef9; padding: 4px; margin: -4px; border-radius: 4px; }}
.fulltext-empty {{
  font-size: 13px; color: var(--text-muted); text-align: center;
  padding: 16px; background: var(--bg); border-radius: var(--radius-sm);
  border: 1px dashed var(--border); margin-bottom: 12px;
}}
.fulltext-input {{
  width: 100%; min-height: 120px; padding: 12px;
  border: 1px dashed var(--border); border-radius: var(--radius-sm);
  font-family: 'Noto Serif TC', serif; font-size: 14px;
  color: var(--text-secondary); background: #fafaf8;
  resize: vertical; outline: none; line-height: 1.9;
}}
.fulltext-input:focus {{ border-color: var(--accent); background: white; }}

/* 相關報導小列表 */
.related-list {{ margin-top: 12px; }}
.related-row {{
  font-size: 13px; color: var(--text-secondary);
  padding: 6px 0; border-bottom: 1px dashed var(--border);
  display: flex; align-items: flex-start; gap: 6px;
}}
.related-row:last-child {{ border-bottom: none; }}
.related-row-bullet {{ color: var(--text-muted); flex-shrink: 0; }}

/* Empty */
.empty-state {{
  text-align: center; padding: 60px 20px;
  color: var(--text-muted); font-size: 14px;
}}

/* ── Print ── */
@media print {{
  .header {{ position: static; box-shadow: none; }}
  .btn-copy, .btn-print, .tabs {{ display: none !important; }}
  .news-card {{ break-inside: avoid; border-left-width: 3px; }}
  .card-detail {{ display: block !important; }}
  .detail-panel {{ display: block !important; }}
  .detail-tabs {{ display: none; }}
  .fulltext-input, .fulltext-empty {{ display: none; }}
}}

@media (max-width: 640px) {{
  .header {{ padding: 14px 16px; }}
  .main {{ padding: 16px; }}
  .btn-print span {{ display: none; }}
}}
</style>
</head>
<body>

<header class="header">
  <div class="header-left">
    <span class="header-title">國家發展委員會 · 經濟規劃科</span>
    <span class="header-sub">每日新聞重點整理 · Economic Intelligence Briefing</span>
  </div>
  <div class="header-right">
    <span class="header-date" id="date-label"></span>
    <button class="btn-print" onclick="window.print()">
      <span>🖨</span><span>列印 / 匯出PDF</span>
    </button>
    <button class="btn-copy" id="btn-copy">
      <span>📋</span><span>複製今日摘要</span>
    </button>
  </div>
</header>

<main class="main">
  <div class="legend">
    <span>優先級：</span>
    <div class="legend-item"><span class="prio-dot must"></span>必看</div>
    <div class="legend-item"><span class="prio-dot watch"></span>關注</div>
    <div class="legend-item"><span class="prio-dot normal"></span>一般</div>
  </div>
  <div class="tabs" id="tabs"></div>
  <div class="news-list" id="news-list"></div>
</main>

<script>
const DATA = {data_json};
const CATS = Object.keys(DATA);
let currentTab = 'all';
const userTexts = {{}};

const PRIO_LABEL = {{ must: '必看', watch: '關注', normal: '一般' }};

// ── Tabs ──
function renderTabs() {{
  const tabs = document.getElementById('tabs');
  tabs.appendChild(mkTab('全部', 'all', true));
  CATS.forEach(cat => {{
    const d = DATA[cat];
    const count = d.items.length;
    const mustCount = d.items.filter(i => i.priority === 'must').length;
    const label = d.icon + ' ' + cat + ' (' + count + (mustCount ? ' ⚑' + mustCount : '') + ')';
    tabs.appendChild(mkTab(label, cat, false));
  }});
}}
function mkTab(label, tab, active) {{
  const b = document.createElement('button');
  b.className = 'tab-btn' + (active ? ' active' : '');
  b.dataset.tab = tab;
  b.textContent = label;
  b.onclick = () => switchTab(tab);
  return b;
}}
function switchTab(tab) {{
  currentTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  renderList();
}}

// ── List ──
function renderList() {{
  const list = document.getElementById('news-list');
  list.innerHTML = '';
  const targets = currentTab === 'all' ? CATS : [currentTab];
  let total = 0;
  targets.forEach(cat => {{
    DATA[cat].items.forEach(item => {{
      list.appendChild(makeCard(item, cat, DATA[cat]));
      total++;
    }});
  }});
  if (!total) {{
    const e = document.createElement('div');
    e.className = 'empty-state';
    e.textContent = '目前無相關新聞資料';
    list.appendChild(e);
  }}
}}

// ── Card ──
function makeCard(item, cat, dept) {{
  const card = document.createElement('div');
  card.className = 'news-card priority-' + item.priority;

  const sourcesHtml = item.sources.map(s => `<span class="source-tag">${{s}}</span>`).join('');
  const hasRelated = item.related_titles && item.related_titles.length > 0;

  card.innerHTML = `
    <div class="card-main">
      <div class="card-left">
        <span class="prio-badge ${{item.priority}}">${{PRIO_LABEL[item.priority]}}</span>
      </div>
      <div class="card-body">
        <div class="card-title">${{item.main_title}}</div>
        <div class="card-lead">→ ${{item.lead}}</div>
        <div class="card-meta-row">
          ${{sourcesHtml}}
          ${{hasRelated ? `<span class="related-badge">＋${{item.related_titles.length}} 則相關</span>` : ''}}
        </div>
      </div>
      <span class="card-arrow">›</span>
    </div>
    <div class="card-detail" id="detail-${{encodeURIComponent(item.main_title)}}"></div>`;

  card.querySelector('.card-main').addEventListener('click', () => {{
    const isOpen = card.classList.contains('open');
    if (!isOpen) buildDetail(card, item, cat, dept);
    card.classList.toggle('open');
  }});

  return card;
}}

// ── Build detail on first open ──
function buildDetail(card, item, cat, dept) {{
  const detail = card.querySelector('.card-detail');
  if (detail.dataset.built) return;
  detail.dataset.built = '1';

  const allTitles = [item.main_title, ...item.related_titles];
  const fullTexts = item.full_texts || {{}};

  // 內部 tab bar（判讀 / 全文 / 相關）
  const tabBar = document.createElement('div');
  tabBar.className = 'detail-tabs';

  const panels = {{}};

  function addTab(key, label) {{
    const t = document.createElement('button');
    t.className = 'detail-tab';
    t.textContent = label;
    t.dataset.key = key;
    t.onclick = () => {{
      detail.querySelectorAll('.detail-tab').forEach(x => x.classList.remove('active'));
      detail.querySelectorAll('.detail-panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      panels[key].classList.add('active');
    }};
    tabBar.appendChild(t);
    return t;
  }}

  // 1. 判讀摘要
  const t1 = addTab('analysis', '判讀摘要');
  const p1 = document.createElement('div');
  p1.className = 'detail-panel active';
  p1.innerHTML = `<div class="analysis-block" contenteditable="true">${{item.analysis}}</div>`;
  panels['analysis'] = p1;

  // 2. 全文（主文）
  const t2 = addTab('fulltext', '新聞全文');
  const storageKey = item.main_title + '__0';
  const savedText = userTexts[storageKey] || '';
  const originalText = fullTexts[item.main_title] || '';
  const displayText = savedText || originalText;
  const p2 = document.createElement('div');
  p2.className = 'detail-panel';
  if (displayText) {{
    p2.innerHTML = `<div class="fulltext-body" contenteditable="true">${{displayText}}</div>`;
    p2.querySelector('.fulltext-body').addEventListener('input', e => {{ userTexts[storageKey] = e.target.innerText; }});
  }} else {{
    p2.innerHTML = `
      <div class="fulltext-empty">📋 尚無全文資料，請在下方貼入新聞內容</div>
      <textarea class="fulltext-input" placeholder="在此貼入全文...">${{savedText}}</textarea>`;
    p2.querySelector('.fulltext-input').addEventListener('input', e => {{ userTexts[storageKey] = e.target.value; }});
  }}
  panels['fulltext'] = p2;

  // 3. 相關報導（若有）
  if (item.related_titles && item.related_titles.length > 0) {{
    const t3 = addTab('related', '相關報導 (' + item.related_titles.length + ')');
    const p3 = document.createElement('div');
    p3.className = 'detail-panel';
    p3.innerHTML = `<div class="related-list">` +
      item.related_titles.map((t, i) => {{
        const rKey = item.main_title + '__' + (i+1);
        const rText = userTexts[rKey] || fullTexts[t] || '';
        return `<div class="related-row">
          <span class="related-row-bullet">▸</span>
          <span>${{t}}</span>
        </div>` +
        (rText ? `<div style="padding:0 0 10px 16px; font-size:13px; color:var(--text-secondary); font-family:'Noto Serif TC',serif; line-height:1.8; white-space:pre-wrap;">${{rText}}</div>` : '');
      }}).join('') +
    `</div>`;
    panels['related'] = p3;
  }}

  // 啟動第一個 tab
  t1.classList.add('active');
  detail.appendChild(tabBar);
  Object.values(panels).forEach(p => detail.appendChild(p));
}}

// ── 複製今日摘要 ──
document.getElementById('btn-copy').addEventListener('click', () => {{
  const now = new Date();
  const dateStr = now.getFullYear() + '.' +
    String(now.getMonth()+1).padStart(2,'0') + '.' +
    String(now.getDate()).padStart(2,'0');

  let text = `【${{dateStr}} 經濟規劃科 · 每日新聞重點】\n`;
  text += `═══════════════════════════\n\n`;

  const targets = currentTab === 'all' ? CATS : [currentTab];
  targets.forEach(cat => {{
    const d = DATA[cat];
    text += `${{d.icon}} ${{cat}}\n`;
    text += `───────────────────────────\n`;
    d.items.forEach(item => {{
      const label = PRIO_LABEL[item.priority];
      text += `▌ [${{label}}] ${{item.main_title}}\n`;
      text += `  來源：${{item.sources.join('、')}}\n`;
      text += `  → ${{item.lead}}\n`;
      if (item.related_titles.length > 0) {{
        text += `  相關：${{item.related_titles.join('；')}}\n`;
      }}
      text += `\n`;
    }});
    text += `\n`;
  }});

  navigator.clipboard.writeText(text).then(() => {{
    const btn = document.getElementById('btn-copy');
    btn.classList.add('copied');
    btn.querySelector('span:last-child').textContent = '已複製！';
    setTimeout(() => {{
      btn.classList.remove('copied');
      btn.querySelector('span:last-child').textContent = '複製今日摘要';
    }}, 2000);
  }});
}});

// ── Date ──
const now = new Date();
document.getElementById('date-label').textContent =
  now.getFullYear() + ' 年 ' +
  String(now.getMonth()+1) + ' 月 ' +
  String(now.getDate()) + ' 日';

renderTabs();
renderList();
</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    run_dashboard()
