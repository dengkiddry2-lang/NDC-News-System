import pdfplumber
import os
import json
import re

# ── 1. 分類定義 ───────────────────────────────────────────────────
DEPARTMENTS = {
    "台灣政府與政策訊息": {
        "icon": "🏛️", "label": "POLICY", "keywords": ["總統府", "行政院", "國發會", "經濟部", "財政部", "政策", "計畫", "預算", "法案"]
    },
    "台灣總體經濟與人口數據": {
        "icon": "📊", "label": "DATA", "keywords": ["主計", "GDP", "CPI", "物價", "通膨", "失業率", "景氣", "出口", "人口"]
    },
    "台灣產業與投資動向": {
        "icon": "🏭", "label": "INDUSTRY", "keywords": ["AI", "半導體", "台積電", "聯發科", "資本支出", "投資", "供應鏈"]
    },
    "國際經濟與金融情勢": {
        "icon": "🌐", "label": "GLOBAL", "keywords": ["Fed", "FOMC", "聯準會", "利率", "升息", "美元", "匯率", "地緣", "戰爭"]
    },
    "國際機構與智庫報告": {
        "icon": "📘", "label": "RESEARCH", "keywords": ["IMF", "OECD", "World Bank", "WTO", "智庫", "Brookings", "PIIE"]
    },
    "社論與評論觀點": {
        "icon": "📝", "label": "CAPACITY", "keywords": ["社論", "時評", "社評", "專欄", "論壇", "觀點", "評論"]
    },
    "其他重要國內外事件": {
        "icon": "🗞️", "label": "NEWS", "keywords": []
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
                    "source": str(row[2]).replace("\n", " ") if len(row)>2 else "EPC REPORT",
                    "cat": found_cat,
                    "label": DEPARTMENTS[found_cat]["label"],
                    "priority": 1 if any(k in title for k in MUST_READ_KEYS) else 0,
                    "summary": content[:160].replace("\n", "") + "...",
                    "full_text": content
                })
    generate_html(all_items)

# ── 4. IMF 風格 HTML ───────────────────────────────────────────────

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    dept_info = json.dumps(DEPARTMENTS, ensure_ascii=False)
    
    css = """
    :root { --imf-blue: #004b87; --imf-light-blue: #0076d6; --imf-gray: #f4f4f4; --imf-dark: #333; }
    body { font-family: 'Public Sans', -apple-system, sans-serif; margin: 0; background: #fff; color: var(--imf-dark); }
    
    /* Top Bar */
    .top-nav { background: #000; color: #fff; padding: 10px 50px; font-size: 11px; letter-spacing: 1px; display: flex; justify-content: space-between; }
    
    /* Main Header */
    .header { background: #fff; padding: 25px 50px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #ddd; }
    .logo { color: var(--imf-blue); font-size: 24px; font-weight: 800; text-decoration: none; border-left: 4px solid var(--imf-blue); padding-left: 15px; }
    
    /* Navigation */
    .nav { background: var(--imf-blue); display: flex; padding: 0 50px; sticky: top; }
    .nav-item { color: #fff; padding: 15px 20px; font-size: 13px; font-weight: 700; cursor: pointer; transition: 0.3s; }
    .nav-item:hover { background: var(--imf-light-blue); }

    .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }

    /* IMF Style Featured Section */
    .featured-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 50px; }
    .hero-card { background: var(--imf-blue); color: #fff; padding: 40px; display: flex; flex-direction: column; justify-content: flex-end; cursor: pointer; }
    .hero-card .label { font-size: 12px; font-weight: 700; color: #ffca28; margin-bottom: 10px; }
    .hero-card h2 { font-size: 36px; margin: 0; line-height: 1.1; font-family: 'Noto Serif TC', serif; }

    /* News Sections */
    .section-title { font-size: 24px; font-weight: 800; border-bottom: 2px solid var(--imf-blue); padding-bottom: 10px; margin-bottom: 25px; display: flex; justify-content: space-between; }
    
    .imf-list-item { display: grid; grid-template-columns: 120px 1fr; gap: 20px; padding: 20px 0; border-bottom: 1px solid #eee; transition: 0.2s; }
    .imf-list-item:hover { background: #fcfcfc; }
    .imf-list-item .date { font-size: 12px; font-weight: 700; color: #888; text-transform: uppercase; }
    .imf-list-item .content-type { font-size: 11px; font-weight: 800; color: var(--imf-blue); margin-bottom: 5px; }
    .imf-list-item h3 { margin: 0 0 10px 0; font-size: 20px; color: var(--imf-blue); cursor: pointer; font-family: 'Noto Serif TC', serif; }
    .imf-list-item .summary { font-size: 15px; color: #666; line-height: 1.5; }

    /* Modal IMF Report Style */
    .modal { display: none; position: fixed; inset: 0; background: #fff; z-index: 1000; overflow-y: auto; }
    .modal-nav { background: #f8f8f8; padding: 15px 50px; border-bottom: 1px solid #ddd; position: sticky; top: 0; }
    .modal-content { max-width: 800px; margin: 60px auto; padding: 0 20px; }
    .full-text { font-size: 18px; line-height: 1.8; text-align: justify; color: #333; white-space: pre-line; font-family: 'Public Sans', sans-serif; }
    .full-text h1 { color: var(--imf-blue); font-size: 42px; margin-bottom: 20px; }
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>EPC Intelligence - IMF Style</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@700;900&family=Public+Sans:wght@400;700;800&display=swap" rel="stylesheet">
        <style>{css}</style>
    </head>
    <body>
        <div class="top-nav">
            <div>NATIONAL DEVELOPMENT COUNCIL · ECONOMIC PLANNING</div>
            <div>INTERNAL USE ONLY</div>
        </div>
        <header class="header">
            <a href="#" class="logo" onclick="location.reload()">EPC Intelligence</a>
            <div id="header-date" style="font-weight:700; font-size:14px;"></div>
        </header>
        <nav class="nav" id="nav-bar"></nav>

        <div class="container">
            <div id="home-view">
                <div class="featured-grid" id="featured-area"></div>
                <div class="section-title">Latest Updates <span style="font-size:14px; font-weight:400; color:#666;">分類動態</span></div>
                <div id="imf-list"></div>
            </div>
        </div>

        <div id="modal" class="modal">
            <div class="modal-nav"><span style="cursor:pointer; font-weight:700; color:var(--imf-blue);" onclick="closeModal()">❮ BACK TO HOME</span></div>
            <div class="modal-content" id="modal-body"></div>
        </div>

        <script>
            const DATA = {data_json};
            const DEPTS = {dept_info};

            function init() {{
                const d = new Date();
                document.getElementById('header-date').textContent = d.toLocaleDateString('zh-TW', {{ year:'numeric', month:'long', day:'numeric' }});
                
                const nav = document.getElementById('nav-bar');
                Object.keys(DEPTS).forEach(cat => {{
                    const div = document.createElement('div');
                    div.className = 'nav-item';
                    div.textContent = DEPTS[cat].label;
                    div.onclick = () => renderList(cat);
                    nav.appendChild(div);
                }});
                
                renderHome();
            }}

            function renderHome() {{
                const featuredArea = document.getElementById('featured-area');
                featuredArea.innerHTML = '';
                const mustRead = DATA.filter(i => i.priority === 1).slice(0, 3);
                
                if(mustRead[0]) {{
                    const hero = document.createElement('div');
                    hero.className = 'hero-card';
                    hero.onclick = () => showFull(DATA.indexOf(mustRead[0]));
                    hero.innerHTML = `<div class="label">FEATURED REPORT</div><h2>${{mustRead[0].title}}</h2>`;
                    featuredArea.appendChild(hero);
                }}

                renderList('all');
            }}

            function renderList(cat) {{
                const list = document.getElementById('imf-list');
                list.innerHTML = '';
                const filtered = cat === 'all' ? DATA : DATA.filter(i => i.cat === cat);
                
                filtered.forEach(item => {{
                    const div = document.createElement('div');
                    div.className = 'imf-list-item';
                    div.innerHTML = `
                        <div class="date">${{item.source.split(' ')[0]}}</div>
                        <div>
                            <div class="content-type">${{item.label}}</div>
                            <h3 onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</h3>
                            <div class="summary">${{item.summary}}</div>
                        </div>
                    `;
                    list.appendChild(div);
                }});
            }}

            function showFull(idx) {{
                const item = DATA[idx];
                document.getElementById('modal-body').innerHTML = `
                    <div class="full-text">
                        <div style="font-weight:800; color:var(--imf-blue); text-transform:uppercase; font-size:14px;">${{item.cat}}</div>
                        <h1>${{item.title}}</h1>
                        <p style="color:#666; font-weight:700;">Source: ${{item.source}}</p>
                        <div style="margin-top:40px;">${{item.full_text}}</div>
                    </div>
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
    print("✅ 已生成 IMF 風格專業儀表板：index.html")

if __name__ == "__main__":
    run_dashboard()
