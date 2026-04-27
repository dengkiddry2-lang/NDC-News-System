import pdfplumber
import os
import json
import re

# ── 1. 分類定義 (對應 IMF 專業標籤) ───────────────────────────────────
DEPARTMENTS = {
    "台灣政府與政策訊息": {
        "icon": "🏛️", "label": "POLICY & GOVERNANCE", "keywords": ["總統府", "行政院", "國發會", "經濟部", "財政部", "政策", "計畫", "法案"]
    },
    "台灣總體經濟與人口數據": {
        "icon": "📊", "label": "SURVEILLANCE & DATA", "keywords": ["主計", "GDP", "CPI", "物價", "通膨", "失業率", "景氣", "出口"]
    },
    "台灣產業與投資動向": {
        "icon": "🏭", "label": "INDUSTRY ANALYSIS", "keywords": ["AI", "半導體", "台積電", "聯發科", "資本支出", "投資", "供應鏈"]
    },
    "國際經濟與金融情勢": {
        "icon": "🌐", "label": "GLOBAL STABILITY", "keywords": ["Fed", "FOMC", "聯準會", "利率", "升息", "美元", "匯率", "地緣"]
    },
    "國際機構與智庫報告": {
        "icon": "📘", "label": "RESEARCH & PUBLICATIONS", "keywords": ["IMF", "OECD", "World Bank", "WTO", "智庫", "Brookings"]
    },
    "社論與評論觀點": {
        "icon": "📝", "label": "CAPACITY DEVELOPMENT", "keywords": ["社論", "時評", "社評", "專欄", "觀點", "評論"]
    },
    "其他重要國內外事件": {
        "icon": "🗞️", "label": "NEWS & EVENTS", "keywords": []
    }
}

MUST_READ_KEYS = ["Fed", "國發會", "主計", "GDP", "利率", "槍響", "衝突"]

# ── 2. 文字清洗與段落重組 ──────────────────────────────────────────
def clean_text_blocks(text_list):
    if not text_list: return ""
    combined_text = ""
    for line in text_list:
        line = line.strip()
        if not line or line.isdigit(): continue
        if combined_text and not combined_text.endswith(("。", "！", "？", "；", "」", "”")):
            combined_text += line
        else:
            combined_text += "\n" + line
    
    combined_text = combined_text.strip()
    sentences = re.split(r'(?<=[。！？；])', combined_text)
    
    paragraphs = []
    current_para = ""
    count = 0
    for s in sentences:
        s = s.strip()
        if not s: continue
        current_para += s
        count += 1
        if (count >= 3 and s.endswith(("。", "！", "？", "；"))) or s.endswith(("」", "”")):
            paragraphs.append(current_para.strip())
            current_para = ""
            count = 0
    if current_para: paragraphs.append(current_para.strip())
    return "\n\n".join(paragraphs)

# ── 3. 解析與資料封裝 ─────────────────────────────────────────────
def build_article_index(pdf):
    index = {}
    last_key = None
    raw_content_map = {}
    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines: continue
        has_source = any(l.startswith("來源:") or l.startswith("來源：") for l in lines[:8])
        if has_source:
            src_idx = next(i for i, l in enumerate(lines) if l.startswith("來源:") or l.startswith("來源："))
            title_key = "".join(lines[:src_idx]).replace(" ", "")
            raw_content_map[title_key] = lines[src_idx + 1:]
            last_key = title_key
        elif last_key:
            raw_content_map[last_key].extend(lines)
    for key, text_list in raw_content_map.items():
        index[key] = clean_text_blocks(text_list)
    return index

def run_dashboard():
    if not os.path.exists("data"): os.makedirs("data")
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files: return
    
    pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join("data", x)))
    latest_pdf = os.path.join("data", pdf_files[-1])

    with pdfplumber.open(latest_pdf) as pdf:
        article_index = build_article_index(pdf)
        all_items = []
        for page in pdf.pages[:10]:
            table = page.extract_table()
            if not table: continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]: continue
                title = str(row[1]).replace("\n", "").strip()
                if len(title) < 5: continue
                
                found_cat = "其他重要國內外事件"
                for cat, info in DEPARTMENTS.items():
                    if any(k in title for k in info["keywords"]):
                        found_cat = cat; break
                
                content = article_index.get(title.replace(" ", ""), "")
                all_items.append({
                    "title": title,
                    "source": str(row[2]).replace("\n", " ") if len(row)>2 else "智庫",
                    "cat": found_cat,
                    "label": DEPARTMENTS[found_cat]["label"],
                    "priority": 1 if any(k in title for k in MUST_READ_KEYS) else 0,
                    "summary": content[:140].replace("\n", ""),
                    "full_text": content
                })
    generate_html(all_items)

# ── 4. 真．IMF 風格 HTML ──────────────────────────────────────────

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    dept_info = json.dumps(DEPARTMENTS, ensure_ascii=False)
    
    css = """
    :root {
        --imf-navy: #00335e; /* IMF 深藍 */
        --imf-accent: #0076d6;
        --imf-bg-light: #f8f9fa;
        --imf-text-main: #212529;
        --imf-text-sub: #6c757d;
    }
    body { font-family: 'Public Sans', sans-serif; background-color: #fff; color: var(--imf-text-main); margin:0; line-height: 1.6; }

    /* Top Utility */
    .util-bar { background: #000; color: #fff; font-size: 10px; font-weight: 700; padding: 10px 60px; letter-spacing: 1px; display: flex; justify-content: space-between; }

    /* Header & Brand */
    .header { padding: 30px 60px; display: flex; align-items: center; justify-content: space-between; background: #fff; }
    .brand-group { display: flex; align-items: center; gap: 20px; }
    .brand-logo { width: 50px; height: 50px; background: var(--imf-navy); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 900; font-size: 12px; }
    .brand-text { border-left: 1px solid #ddd; padding-left: 20px; }
    .brand-text h1 { margin: 0; font-size: 22px; color: var(--imf-navy); font-weight: 800; }
    .brand-text p { margin: 0; font-size: 12px; color: var(--imf-text-sub); font-weight: 600; letter-spacing: 1px; }

    /* Navigation IMF Blue Ribbon */
    .imf-nav { background: var(--imf-navy); display: flex; padding: 0 60px; position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 10px rgba(0,0,0,0.1); overflow-x: auto; scrollbar-width: none; }
    .nav-item { color: #fff; padding: 18px 25px; font-size: 13px; font-weight: 700; cursor: pointer; border-right: 1px solid rgba(255,255,255,0.1); white-space: nowrap; }
    .nav-item:hover, .nav-item.active { background: var(--imf-accent); }

    /* Hero IMF Hero Section */
    .hero-container { background: var(--imf-bg-light); padding: 60px; border-bottom: 1px solid #eee; }
    .hero-grid { display: grid; grid-template-columns: 2.5fr 1.5fr; gap: 40px; max-width: 1200px; margin: 0 auto; }
    .hero-main-card { background: #fff; padding: 40px; border-top: 6px solid var(--imf-navy); box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
    .label-tag { font-size: 12px; font-weight: 800; color: var(--imf-accent); text-transform: uppercase; margin-bottom: 15px; display: block; }
    .hero-main-card h2 { font-size: 44px; margin: 0 0 20px 0; font-family: 'Noto Serif TC', serif; line-height: 1.2; color: var(--imf-navy); }
    .hero-main-card p { font-size: 18px; color: #444; margin-bottom: 30px; }
    .read-more-btn { background: var(--imf-navy); color: #fff; border: none; padding: 12px 24px; font-weight: 700; font-size: 13px; cursor: pointer; transition: 0.3s; }
    .read-more-btn:hover { background: var(--imf-accent); }

    /* News Feed List */
    .main-grid { max-width: 1200px; margin: 40px auto; padding: 0 60px; display: grid; grid-template-columns: 1fr 300px; gap: 60px; }
    .imf-feed-item { border-bottom: 1px solid #eee; padding: 30px 0; transition: transform 0.2s; }
    .imf-feed-item:hover { transform: translateX(10px); }
    .feed-meta { font-size: 12px; font-weight: 800; color: var(--imf-accent); text-transform: uppercase; margin-bottom: 10px; }
    .feed-title { font-size: 24px; font-weight: 800; color: var(--imf-navy); margin-bottom: 12px; cursor: pointer; font-family: 'Noto Serif TC', serif; }
    .feed-summary { font-size: 16px; color: var(--imf-text-sub); }
    .feed-source { font-size: 12px; color: #999; margin-top: 10px; font-weight: 600; }

    /* Modal Overlay (IMF Report View) */
    .modal { display: none; position: fixed; inset: 0; background: #fff; z-index: 1000; overflow-y: auto; }
    .modal-nav { padding: 20px 60px; background: #fff; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; }
    .modal-body { max-width: 850px; margin: 60px auto; padding: 0 60px; }
    .report-label { color: var(--imf-accent); font-weight: 800; font-size: 14px; text-transform: uppercase; }
    .report-title { font-size: 52px; font-weight: 900; line-height: 1.1; margin: 20px 0; color: var(--imf-navy); font-family: 'Noto Serif TC', serif; border-bottom: 10px solid var(--imf-bg-light); padding-bottom: 30px; }
    .report-text { font-size: 20px; line-height: 2; color: #333; text-align: justify; white-space: pre-line; word-break: break-word; }

    .sidebar-block { background: var(--imf-bg-light); padding: 25px; border-radius: 4px; }
    .sidebar-block h3 { font-size: 16px; font-weight: 800; color: var(--imf-navy); border-bottom: 2px solid var(--imf-navy); padding-bottom: 10px; margin-top: 0; }
    .side-list-item { padding: 12px 0; border-bottom: 1px solid #e0e0e0; font-size: 14px; font-weight: 700; cursor: pointer; color: var(--imf-navy); }
    .side-list-item:hover { color: var(--imf-accent); }

    @media (max-width: 900px) {
        .hero-grid, .main-grid { grid-template-columns: 1fr; padding: 20px; }
        .hero-container, .header { padding: 20px; }
    }
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>EPC Intelligence Hub</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@900&family=Public+Sans:wght@400;700;800&display=swap" rel="stylesheet">
        <style>{css}</style>
    </head>
    <body>
        <div class="util-bar">
            <div>EPC INTELLIGENCE NETWORK</div>
            <div>STRICTLY INTERNAL · DATA PRIVACY ADVISORY</div>
        </div>
        
        <header class="header">
            <div class="brand-group">
                <div class="brand-logo">EPC</div>
                <div class="brand-text">
                    <h1>EPC Intelligence Hub</h1>
                    <p>NATIONAL DEVELOPMENT COUNCIL</p>
                </div>
            </div>
            <div id="h-date" style="font-weight:800; color:var(--imf-navy)"></div>
        </header>

        <nav class="imf-nav" id="nav-bar">
            <div class="nav-item active" onclick="location.reload()">HOME</div>
        </nav>

        <div id="home-view">
            <section class="hero-container">
                <div class="hero-grid" id="hero-area"></div>
            </section>

            <div class="main-grid">
                <section id="feed-list"></section>
                <aside>
                    <div class="sidebar-block">
                        <h3>KEY INDICATORS</h3>
                        <div id="side-list"></div>
                    </div>
                </aside>
            </div>
        </div>

        <div id="modal" class="modal">
            <div class="modal-nav">
                <div class="brand-group"><div class="brand-logo" style="width:30px; height:30px; font-size:8px;">EPC</div></div>
                <button class="read-more-btn" onclick="closeModal()">CLOSE REPORT</button>
            </div>
            <div class="modal-body" id="modal-content"></div>
        </div>

        <script>
            const DATA = {data_json};
            const DEPTS = {dept_info};

            function init() {{
                const d = new Date();
                document.getElementById('h-date').textContent = d.toLocaleDateString('en-US', {{ month:'short', day:'numeric', year:'numeric' }}).toUpperCase();
                
                const nav = document.getElementById('nav-bar');
                Object.keys(DEPTS).forEach(cat => {{
                    const div = document.createElement('div');
                    div.className = 'nav-item';
                    div.textContent = DEPTS[cat].label;
                    div.onclick = () => filterFeed(cat);
                    nav.appendChild(div);
                }});

                renderHero();
                renderFeed('all');
            }}

            function renderHero() {{
                const area = document.getElementById('hero-area');
                const top = DATA.filter(i => i.priority === 1)[0] || DATA[0];
                if (!top) return;

                area.innerHTML = `
                    <div class="hero-main-card">
                        <span class="label-tag">FEATURED INSIGHTS</span>
                        <h2>${{top.title}}</h2>
                        <p>${{top.summary}}...</p>
                        <button class="read-more-btn" onclick="showFull(${{DATA.indexOf(top)}})">READ FULL REPORT</button>
                    </div>
                    <div style="display:flex; flex-direction:column; gap:20px;">
                        <div style="background:var(--imf-navy); color:#fff; padding:30px; border-radius:4px;">
                            <span class="label-tag" style="color:#fff; opacity:0.8;">DAILY DATA</span>
                            <h3 style="margin:10px 0; font-size:24px;">Macro Economic Snapshot</h3>
                            <p style="font-size:14px; opacity:0.8;">Real-time analysis of market shifts and policy implications.</p>
                        </div>
                    </div>
                `;
            }}

            function renderFeed(cat) {{
                const list = document.getElementById('feed-list');
                const side = document.getElementById('side-list');
                list.innerHTML = ''; side.innerHTML = '';

                const filtered = cat === 'all' ? DATA : DATA.filter(i => i.cat === cat);
                
                filtered.forEach((item, idx) => {{
                    const div = document.createElement('div');
                    div.className = 'imf-feed-item';
                    div.innerHTML = `
                        <div class="feed-meta">${{item.label}}</div>
                        <div class="feed-title" onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</div>
                        <div class="feed-summary">${{item.summary}}...</div>
                        <div class="feed-source">SOURCE: ${{item.source}}</div>
                    `;
                    list.appendChild(div);

                    if(idx < 8) {{
                        const sDiv = document.createElement('div');
                        sDiv.className = 'side-list-item';
                        sDiv.textContent = item.title;
                        sDiv.onclick = () => showFull(${{DATA.indexOf(item)}});
                        side.appendChild(sDiv);
                    }}
                }});
            }}

            function filterFeed(cat) {{
                document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
                renderFeed(cat);
            }}

            function showFull(idx) {{
                const item = DATA[idx];
                const content = document.getElementById('modal-content');
                content.innerHTML = `
                    <span class="report-label">${{item.cat}}</span>
                    <h1 class="report-title">${{item.title}}</h1>
                    <div style="font-weight:700; margin-bottom:40px; color:var(--imf-text-sub);"> EPC ANALYSIS SERIES | SOURCE: ${{item.source}} </div>
                    <div class="report-text">${{item.full_text}}</div>
                `;
                document.getElementById('modal').style.display = 'block';
                document.body.style.overflow = 'hidden';
            }}

            function closeModal() {{
                document.getElementById('modal').style.display = 'none';
                document.body.style.overflow = 'auto';
            }}

            init();
        </script>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ 深度 IMF 官網風格已生成：index.html")

if __name__ == "__main__":
    run_dashboard()
