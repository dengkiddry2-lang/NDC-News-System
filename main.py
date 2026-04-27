import pdfplumber
import os
import html
import json

# 1. 定義分類與智慧關鍵字
DEPARTMENTS = {
    "風險監控": {
        "icon": "⚠️",
        "label": "Risk Monitor",
        "keywords": ["美伊", "伊朗", "戰爭", "川普", "選情", "槍響", "Fed", "利率", "衝突"]
    },
    "總體數據": {
        "icon": "📊",
        "label": "Macro Data",
        "keywords": ["出口", "進口", "物價", "通膨", "匯率", "GDP", "主計", "景氣", "成長"]
    },
    "產業動能": {
        "icon": "⚙️",
        "label": "Industry",
        "keywords": ["AI", "資本支出", "台積電", "半導體", "伺服器", "CoWoS", "設備", "製程"]
    },
    "政策規畫": {
        "icon": "🏢",
        "label": "Policy",
        "keywords": ["國發會", "政策", "計畫", "電力", "預算", "離岸風電", "算力", "淨零"]
    }
}

def get_analysis(title, cat):
    """生成多行摘要判讀"""
    if any(k in title for k in ["資本支出", "AI", "設備", "伺服器"]):
        return (
            "本則新聞涉及 AI 相關資本支出與供應鏈投資動向，顯示市場對於人工智慧硬體基礎建設需求持續擴張。"
            "從總體面觀察，此類資本支出的增加將拉抬民間投資（I）分項，有助於支撐 GDP 成長動能。"
            "建議持續追蹤台灣 AI 伺服器出口訂單及相關供應商接單狀況，以評估實際需求是否符合預期。"
        )
    if any(k in title for k in ["出口", "訂單", "外銷"]):
        return (
            "本則新聞反映外需動能變化，出口數據為台灣經濟的核心領先指標之一。"
            "若出口呈現回穩或成長趨勢，代表主要貿易夥伴（美、中、歐）景氣同步改善，淨出口（X-M）對 GDP 的貢獻度將上升。"
            "需留意匯率走勢對出口競爭力的影響，以及美中貿易政策對訂單排擠效應的潛在風險。"
        )
    if any(k in title for k in ["通膨", "油價", "物價", "CPI"]):
        return (
            "本則新聞涉及物價或通膨走勢，供給端成本壓力仍是現階段不確定因素之一。"
            "若通膨持續超出目標區間，將對貨幣政策路徑產生制約，影響央行是否調整利率決策。"
            "建議同步觀察核心 CPI 與生產者物價指數（PPI），以判斷成本壓力是否向下游消費端傳導。"
        )
    if any(k in title for k in ["川普", "戰爭", "地緣", "衝突", "制裁"]):
        return (
            "本則新聞屬地緣政治或國際情勢範疇，屬於系統性風險訊號，對金融市場與貿易流向均可能產生非線性衝擊。"
            "地緣風險升溫通常導致風險資產承壓，並推升能源與避險資產（黃金、美元）價格。"
            "建議在預測模型中調高不確定性溢價，並規劃情境分析（基準、樂觀、悲觀）以覆蓋尾部風險。"
        )
    if any(k in title for k in ["Fed", "利率", "央行", "升息", "降息"]):
        return (
            "本則新聞聚焦貨幣政策走向，Fed 或各國央行的利率決策對全球資金流向與匯率具有直接影響。"
            "若市場預期利率維持高檔，將壓抑資產評價並影響企業融資成本；反之，降息訊號有助於刺激需求。"
            "台灣央行的決策通常與 Fed 方向保持一定連動，建議同步追蹤台美利率差對新台幣匯率的傳導效果。"
        )
    if any(k in title for k in ["政策", "計畫", "預算", "國發會"]):
        return (
            "本則新聞涉及政府政策規畫或預算配置，為經濟預測的重要結構性變數。"
            "政府支出（G）是 GDP 支出面的直接構成要素，預算執行進度與新政策方向將影響公共投資與民間信心。"
            "建議追蹤政策落地時程，評估對相關產業鏈（如綠能、數位基礎建設）的乘數效果。"
        )
    return (
        "本則新聞為一般性經濟資訊，目前不具明顯的高度風險或重大政策意涵。"
        "建議維持現行預測模型參數，持續追蹤後續相關數據發布，以確認訊號方向是否一致。"
        "若後續出現相關新聞佐證，可考慮對應調整預測假設或情境設定。"
    )

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
                if len(title) < 5 or "新聞議題" in title:
                    continue

                found_cat = "其他資訊"
                for cat, info in DEPARTMENTS.items():
                    if any(k in title for k in info["keywords"]):
                        found_cat = cat
                        break

                # 主題歸併 (取標題前 8 個字作為 key)
                theme_key = title[:8]
                if theme_key not in organized_data[found_cat]:
                    organized_data[found_cat][theme_key] = {
                        "main_title": title,
                        "related_titles": [],
                        "sources": [source],
                        "analysis": get_analysis(title, found_cat)
                    }
                else:
                    if title != organized_data[found_cat][theme_key]["main_title"]:
                        organized_data[found_cat][theme_key]["related_titles"].append(title)
                    if source not in organized_data[found_cat][theme_key]["sources"]:
                        organized_data[found_cat][theme_key]["sources"].append(source)

    generate_html(organized_data)
    print("✅ 已產生 index.html")

def generate_html(data):
    # 將資料序列化為 JSON 供 JS 使用
    js_data = {}
    for cat, items in data.items():
        if cat == "其他資訊":
            continue
        dept_info = DEPARTMENTS.get(cat, {"icon": "📂", "label": cat})
        js_data[cat] = {
            "icon": dept_info["icon"],
            "label": dept_info["label"],
            "items": []
        }
        for key, info in items.items():
            js_data[cat]["items"].append({
                "main_title": info["main_title"],
                "related_titles": info["related_titles"],
                "sources": info["sources"],
                "analysis": info["analysis"]
            })

    data_json = json.dumps(js_data, ensure_ascii=False, indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>新聞情報儀表板</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;600&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --white: #ffffff;
    --bg: #f5f4f0;
    --surface: #ffffff;
    --border: #e8e6e1;
    --border-hover: #c8c5be;
    --text-primary: #1a1917;
    --text-secondary: #6b6860;
    --text-muted: #a09e99;
    --accent: #2563eb;
    --accent-light: #eff6ff;
    --tag-bg: #f0efeb;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
    --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
    --shadow-lg: 0 8px 32px rgba(0,0,0,0.12);
    --radius: 10px;
    --radius-sm: 6px;
  }}

  body {{
    background-color: var(--bg);
    color: var(--text-primary);
    font-family: 'DM Sans', 'Noto Serif TC', sans-serif;
    min-height: 100vh;
    line-height: 1.6;
  }}

  /* Header */
  .header {{
    background: var(--white);
    border-bottom: 1px solid var(--border);
    padding: 20px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
  }}
  .header-left {{ display: flex; align-items: baseline; gap: 14px; }}
  .header-title {{
    font-family: 'Noto Serif TC', serif;
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: 0.02em;
  }}
  .header-sub {{
    font-size: 12px;
    color: var(--text-muted);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }}
  .live-indicator {{
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-muted);
  }}
  .live-dot {{
    width: 7px; height: 7px;
    background: #22c55e;
    border-radius: 50%;
    animation: pulse 2s infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50% {{ opacity: 0.5; transform: scale(0.85); }}
  }}

  /* Layout */
  .main {{
    padding: 32px 40px;
    max-width: 1600px;
    margin: 0 auto;
  }}

  .tabs {{
    display: flex;
    gap: 6px;
    margin-bottom: 28px;
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 5px;
    width: fit-content;
  }}
  .tab-btn {{
    padding: 8px 20px;
    border: none;
    background: transparent;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-family: inherit;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }}
  .tab-btn:hover {{ background: var(--bg); color: var(--text-primary); }}
  .tab-btn.active {{
    background: var(--text-primary);
    color: white;
    font-weight: 500;
  }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px;
  }}

  /* News Card */
  .news-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    cursor: pointer;
  }}
  .news-card:hover {{
    border-color: var(--border-hover);
    box-shadow: var(--shadow-md);
  }}
  .news-card.open {{
    border-color: var(--accent);
    box-shadow: var(--shadow-md);
  }}

  .card-header {{
    padding: 18px 20px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .card-meta {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .cat-tag {{
    font-size: 11px;
    font-weight: 500;
    color: var(--accent);
    background: var(--accent-light);
    padding: 2px 9px;
    border-radius: 20px;
    letter-spacing: 0.03em;
  }}
  .related-count {{
    font-size: 11px;
    color: var(--text-muted);
  }}
  .card-title {{
    font-family: 'Noto Serif TC', serif;
    font-size: 15px;
    font-weight: 600;
    line-height: 1.55;
    color: var(--text-primary);
  }}

  .source-row {{
    padding: 0 20px 14px;
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }}
  .source-tag {{
    font-size: 11px;
    color: var(--text-muted);
    background: var(--tag-bg);
    padding: 2px 8px;
    border-radius: 4px;
  }}

  .expand-btn {{
    width: 100%;
    border: none;
    border-top: 1px solid var(--border);
    background: transparent;
    padding: 10px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: var(--text-secondary);
    font-family: inherit;
    cursor: pointer;
    transition: background 0.15s;
  }}
  .expand-btn:hover {{ background: var(--bg); }}
  .expand-icon {{
    font-size: 14px;
    transition: transform 0.25s ease;
    color: var(--text-muted);
  }}
  .open .expand-icon {{ transform: rotate(180deg); }}

  /* Expanded panel */
  .card-detail {{
    display: none;
    border-top: 1px solid var(--border);
    animation: slideDown 0.22s ease;
  }}
  @keyframes slideDown {{
    from {{ opacity: 0; transform: translateY(-6px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  .open .card-detail {{ display: block; }}

  .related-section {{
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
  }}
  .related-label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 10px;
  }}
  .related-item {{
    font-size: 13px;
    color: var(--text-secondary);
    padding: 5px 0;
    border-bottom: 1px dashed var(--border);
    line-height: 1.5;
  }}
  .related-item:last-child {{ border-bottom: none; }}

  .analysis-section {{
    padding: 18px 20px;
    background: #fafaf8;
  }}
  .analysis-label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .analysis-label::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }}
  .analysis-text {{
    font-size: 13.5px;
    color: var(--text-secondary);
    line-height: 1.85;
    font-family: 'Noto Serif TC', serif;
    outline: none;
  }}

  /* Empty state */
  .empty-state {{
    grid-column: 1 / -1;
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
    font-size: 14px;
  }}

  /* All tab grid = 4 columns */
  .grid.all-view {{
    grid-template-columns: repeat(4, 1fr);
  }}

  @media (max-width: 1200px) {{
    .grid.all-view {{ grid-template-columns: repeat(2, 1fr); }}
    .main {{ padding: 24px; }}
  }}
  @media (max-width: 640px) {{
    .grid, .grid.all-view {{ grid-template-columns: 1fr; }}
    .header {{ padding: 16px 20px; }}
    .main {{ padding: 16px; }}
  }}
</style>
</head>
<body>

<header class="header">
  <div class="header-left">
    <span class="header-title">新聞情報儀表板</span>
    <span class="header-sub">Economic Intelligence · NDCP</span>
  </div>
  <div class="live-indicator">
    <span class="live-dot"></span>
    <span id="date-label"></span>
  </div>
</header>

<main class="main">
  <div class="tabs" id="tabs"></div>
  <div class="grid" id="card-grid"></div>
</main>

<script>
const DATA = {data_json};

const CATS = Object.keys(DATA);
let currentTab = 'all';

function renderTabs() {{
  const tabs = document.getElementById('tabs');
  const allBtn = document.createElement('button');
  allBtn.className = 'tab-btn active';
  allBtn.textContent = '全部';
  allBtn.dataset.tab = 'all';
  allBtn.onclick = () => switchTab('all');
  tabs.appendChild(allBtn);

  CATS.forEach(cat => {{
    const d = DATA[cat];
    const btn = document.createElement('button');
    btn.className = 'tab-btn';
    btn.dataset.tab = cat;
    btn.textContent = d.icon + ' ' + cat + ' (' + d.items.length + ')';
    btn.onclick = () => switchTab(cat);
    tabs.appendChild(btn);
  }});
}}

function switchTab(tab) {{
  currentTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => {{
    b.classList.toggle('active', b.dataset.tab === tab);
  }});
  renderCards();
}}

function renderCards() {{
  const grid = document.getElementById('card-grid');
  grid.innerHTML = '';
  grid.className = currentTab === 'all' ? 'grid all-view' : 'grid';

  const targets = currentTab === 'all' ? CATS : [currentTab];
  let total = 0;

  targets.forEach(cat => {{
    const d = DATA[cat];
    d.items.forEach(item => {{
      grid.appendChild(makeCard(item, cat, d));
      total++;
    }});
  }});

  if (total === 0) {{
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = '目前無相關新聞資料';
    grid.appendChild(empty);
  }}
}}

function makeCard(item, cat, dept) {{
  const card = document.createElement('div');
  card.className = 'news-card';

  const hasRelated = item.related_titles && item.related_titles.length > 0;

  const sourcesHtml = item.sources.map(s =>
    `<span class="source-tag">${{s}}</span>`
  ).join('');

  const relatedSection = hasRelated ? `
    <div class="related-section">
      <div class="related-label">相關報導 (${{item.related_titles.length}})</div>
      ${{item.related_titles.map(t => `<div class="related-item">${{t}}</div>`).join('')}}
    </div>
  ` : '';

  card.innerHTML = `
    <div class="card-header">
      <div class="card-meta">
        <span class="cat-tag">${{dept.icon}} ${{cat}}</span>
        ${{hasRelated ? `<span class="related-count">+${{item.related_titles.length}} 則相關</span>` : ''}}
      </div>
      <div class="card-title">${{item.main_title}}</div>
    </div>
    <div class="source-row">${{sourcesHtml}}</div>
    <button class="expand-btn">
      <span>展開分析與彙整</span>
      <span class="expand-icon">▾</span>
    </button>
    <div class="card-detail">
      ${{relatedSection}}
      <div class="analysis-section">
        <div class="analysis-label">判讀摘要</div>
        <div class="analysis-text" contenteditable="true">${{item.analysis}}</div>
      </div>
    </div>
  `;

  card.querySelector('.expand-btn').addEventListener('click', (e) => {{
    e.stopPropagation();
    card.classList.toggle('open');
  }});

  card.addEventListener('click', () => {{
    card.classList.toggle('open');
  }});

  return card;
}}

// Date display
const now = new Date();
document.getElementById('date-label').textContent =
  now.getFullYear() + '/' +
  String(now.getMonth()+1).padStart(2,'0') + '/' +
  String(now.getDate()).padStart(2,'0');

renderTabs();
renderCards();
</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    run_dashboard()
