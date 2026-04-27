import pdfplumber
import os
import json
import re

# ── 1. 分類定義與優先序 (修正點 2, 3: 擴充關鍵字與判定優先級) ──────────────────
DEPARTMENTS = {
    "社論與評論觀點": {
        "icon": "📝", "label": "EDITORIALS & OPINIONS", 
        "keywords": ["社論", "時評", "社評", "專欄", "論壇", "觀點", "評論", "時論", "名家", "經濟教室"]
    },
    "國際機構與智庫報告": {
        "icon": "📘", "label": "RESEARCH & INSTITUTIONS", 
        "keywords": ["IMF", "OECD", "World Bank", "WTO", "智庫", "Brookings", "PIIE", "國際貨幣基金", "世界銀行", "經濟合作暨發展組織", "BIS", "ADB", "WEF", "UN", "聯合國"]
    },
    "台灣政府與政策訊息": {
        "icon": "🏛️", "label": "GOVERNMENT & POLICY", 
        "keywords": ["總統府", "行政院", "國發會", "經濟部", "財政部", "政策", "計畫", "預算", "法案", "行政院會", "施政報告"]
    },
    "台灣總體經濟與人口數據": {
        "icon": "📊", "label": "MACRO & DATA", 
        "keywords": ["主計", "GDP", "CPI", "物價", "通膨", "失業率", "景氣", "出口", "外銷訂單", "進口", "進出口", "貿易統計", "薪資", "出生率", "死亡率", "人口統計", "少子化", "高齡化"]
    },
    "台灣產業與投資動向": {
        "icon": "🏭", "label": "INDUSTRY & INVESTMENT", 
        "keywords": ["AI", "半導體", "台積電", "聯發科", "資本支出", "投資", "供應鏈", "算力", "伺服器", "離岸風電"]
    },
    "國際經濟與金融情勢": {
        "icon": "🌐", "label": "GLOBAL STABILITY", 
        "keywords": ["Fed", "FOMC", "聯準會", "利率", "升息", "降息", "美元", "匯率", "地緣", "美中", "貿易戰"]
    },
    "其他重要國內外事件": {
        "icon": "🗞️", "label": "KEY EVENTS", "keywords": []
    }
}

# 定義分類判斷順序
CATEGORY_ORDER = list(DEPARTMENTS.keys())

# 特殊重點新聞關鍵字
MUST_READ_KEYS = ["Fed", "國發會", "主計", "GDP", "利率", "槍響", "衝突", "下修", "調升", "戰爭"]

# ── 2. 核心文本解析與模糊比對 ────────────────────────────────────────

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

def find_article(article_index, title):
    key = title.replace(" ", "")
    for n in [12, 10, 8, 6, 4]:
        short = key[:n]
        if not short: continue
        for art_key, content in article_index.items():
            if short in art_key:
                return content
    return ""

# ── 3. 解析與資料處理 ─────────────────────────────────────────────

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
        for page in pdf.pages[:12]:
            table = page.extract_table()
            if not table: continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]: continue
                title = str(row[1]).replace("\n", "").strip()
                source = str(row[2]).replace("\n", " ") if len(row) > 2 and row[2] else "EPC智庫"
                if len(title) < 5: continue
                
                # 修正點 4: 標題＋來源組合判定，避免漏分
                classify_text = title + " " + source
                found_cat = "其他重要國內外事件"
                for cat in CATEGORY_ORDER:
                    if any(k in classify_text for k in DEPARTMENTS[cat]["keywords"]):
                        found_cat = cat
                        break
                
                content = find_article(article_index, title)
                summary = content[:150].replace("\n", "") + "..." if content else "尚未擷取到內文摘要"
                
                all_items.append({
                    "title": title,
                    "source": source,
                    "cat": found_cat,
                    "label": DEPARTMENTS[found_cat]["label"],
                    "priority": 1 if any(k in title for k in MUST_READ_KEYS) else 0,
                    "summary": summary,
                    "full_text": content
                })
    generate_html(all_items)

# ── 4. 真．IMF 風格 HTML (修正點 1: 防斷版與 f-string 衝突) ──────────────────

def generate_html(data):
    # 修正點 1: 防斷版處理 (JSON stringify 安全性)
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    dept_info = json.dumps(DEPARTMENTS, ensure_ascii=False).replace("</", "<\\/")
    
    css = """
    :root { --imf-navy: #00335e; --imf-accent: #0076d6; --imf-bg-light: #f8f9fa; }
    body { font-family: 'Public Sans', sans-serif; background: #fff; color: #212529; margin:0; line-height: 1.6; }

    .top-utility { background: #000; color: #fff; font-size: 10px; font-weight: 700; padding: 12px 60px; letter-spacing: 1px; display: flex; justify-content: space-between; }
    .header { padding: 35px 60px; display: flex; align-items: center; background: #fff; border-bottom: 1px solid #eee; }
    .logo-seal { width: 55px; height: 55px; background: var(--imf-navy); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 900; font-size: 14px; margin-right: 25px; }
    .brand-titles h1 { margin: 0; font-size: 26px; color: var(--imf-navy); font-weight: 800; }
    .brand-titles p { margin: 0; font-size: 12px; color: #6c757d; font-weight: 600; text-transform: uppercase; }

    .imf-nav { background: var(--imf-navy); display: flex; padding: 0 60px; position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow-x: auto; scrollbar-width: none; }
    .nav-item { color: #fff; padding: 18px 25px; font-size: 12.5px; font-weight: 700; cursor: pointer; transition: 0.3s; border-right: 1px solid rgba(255,255,255,0.08); white-space: nowrap; }
    .nav-item:hover, .nav-item.active { background: var(--imf-accent); }

    .hero-wrap { background: var(--imf-bg-light); padding: 60px; }
    .hero-inner { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 2.2fr 1fr; gap: 40px; }
    .featured-card { background: #fff; padding: 45px; border-top: 8px solid var(--imf-navy); box-shadow: 0 15px 45px rgba(0,0,0,0.05); }
    .cat-tag { font-size: 11px; font-weight: 800; color: var(--imf-accent); letter-spacing: 1px; margin-bottom: 15px; display: block; }
    .featured-card h2 { font-size: 42px; margin: 0 0 25px 0; font-family: 'Noto Serif TC', serif; font-weight: 900; color: var(--imf-navy); line-height: 1.15; }
    .imf-btn { background: var(--imf-navy); color: #fff; border: none; padding: 14px 28px; font-weight: 700; font-size: 13px; cursor: pointer; }

    .main-layout { max-width: 1200px; margin: 50px auto; padding: 0 60px; display: grid; grid-template-columns: 1fr 320px; gap: 70px; }
    .feed-section-title { font-size: 22px; font-weight: 800; color: var(--imf-navy); border-bottom: 2px solid var(--imf-navy); padding-bottom: 15px; margin-bottom: 30px; }
    .news-item { padding: 30px 0; border-bottom: 1px solid #eee; transition: 0.3s; }
    .news-title { font-size: 24px; font-weight: 800; color: var(--imf-navy); margin: 0 0 12px 0; cursor: pointer; font-family: 'Noto Serif TC', serif; }
    
    .modal { display: none; position: fixed; inset: 0; background: #fff; z-index: 1000; overflow-y: auto; }
    .modal-header { padding: 20px 60px; background: #fff; border-bottom: 1px solid #eee; position: sticky; top: 0; display: flex; justify-content: space-between; align-items: center; }
    .modal-body { max-width: 850px; margin: 70px auto; padding: 0 60px; }
    .report-headline { font-size: 56px; font-weight: 900; line-height: 1.1; margin: 25px 0 40px; color: var(--imf-navy); font-family: 'Noto Serif TC', serif; border-bottom: 12px solid var(--imf-bg-light); padding-bottom: 35px; }
    .report-content { font-size: 20px; line-height: 2.1; text-align: justify; white-space: pre-line; word-break: break-word; overflow-wrap: anywhere; }

    .sidebar-block { background: var(--imf-bg-light); padding: 30px; }
    .sidebar-block h3 { font-size: 16px; font-weight: 800; color: var(--imf-navy); border-bottom: 2px solid var(--imf-navy); padding-bottom: 12px; margin-top: 0; }
    .side-link { padding: 15px 0; border-bottom: 1px solid #e2e2e2; font-size: 14.5px; font-weight: 700; cursor: pointer; color: var(--imf-navy); }

    @media (max-width: 900px) {
        .hero-inner, .main-layout { grid-template-columns: 1fr; }
        .header, .imf-nav { padding: 0 20px; }
    }
    """

    # 修正點 1: 改用 span 標記，由 JS 填入日期，避免 Python 報錯
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
        <div class="top-utility">
            <div>EPC INTELLIGENCE NETWORK</div>
            <div>INTERNAL ADVISORY · <span id="roc-year-label"></span></div>
        </div>
        
        <header class="header">
            <div class="logo-seal">EPC</div>
            <div class="brand-titles">
                <h1>EPC Intelligence Hub</h1>
                <p>National Development Council · Economic Planning Division</p>
            </div>
        </header>

        <nav class="imf-nav" id="nav-bar">
            <div class="nav-item active" id="nav-home" onclick="goHome(this)">HOME</div>
        </nav>

        <div id="home-view">
            <div class="hero-wrap">
                <div class="hero-inner" id="hero-area"></div>
            </div>
            <div class="main-layout">
                <section>
                    <div class="feed-section-title" id="current-view-title">LATEST ANALYSIS</div>
                    <div id="news-feed"></div>
                </section>
                <aside>
                    <div class="sidebar-block">
                        <h3>TOP BRIEFS</h3>
                        <div id="side-feed"></div>
                    </div>
                </aside>
            </div>
        </div>

        <div id="modal" class="modal">
            <div class="modal-header">
                <div class="logo-seal" style="width:35px; height:35px; font-size:10px;">EPC</div>
                <button class="imf-btn" onclick="closeModal()">CLOSE REPORT</button>
            </div>
            <div class="modal-body" id="modal-content"></div>
        </div>

        <script>
            const DATA = {data_json};
            const DEPTS = {dept_info};

            function init() {{
                // 修正點 1: JS 處理民國日期
                const yr = new Date().getFullYear();
                document.getElementById('roc-year-label').textContent = '民國 ' + (yr - 1911) + ' 年';
                
                const nav = document.getElementById('nav-bar');
                Object.keys(DEPTS).forEach(cat => {{
                    const div = document.createElement('div');
                    div.className = 'nav-item';
                    div.textContent = cat.replace('台灣', '').replace('與政策訊息', '').toUpperCase();
                    div.onclick = function() {{ filterFeed(cat, this); }}; // 修正點 6
                    nav.appendChild(div);
                }});

                renderHero();
                renderFeed('all');
            }}

            function renderHero() {{
                const area = document.getElementById('hero-area');
                const featured = DATA.filter(i => i.priority === 1)[0] || DATA[0];
                if (!featured) return;

                area.innerHTML = `
                    <div class="featured-card">
                        <span class="cat-tag">${{featured.label}}</span>
                        <h2>${{featured.title}}</h2>
                        <p>${{featured.summary}}</p>
                        <button class="imf-btn" onclick="showFull(${{DATA.indexOf(featured)}})">VIEW FULL ANALYSIS</button>
                    </div>
                    <div style="background:var(--imf-navy); color:#fff; padding:40px; display:flex; flex-direction:column; justify-content:center;">
                        <span class="cat-tag" style="color:#ffca28">ECONOMIC SNAPSHOT</span>
                        <h3 style="margin:10px 0; font-size:24px; line-height:1.2;">EPC Analytics Briefing</h3>
                        <p style="font-size:14px; opacity:0.8;">Cross-sectoral analysis from NDC Economic Planning Division.</p>
                    </div>
                `;
            }}

            function renderFeed(cat) {{
                const list = document.getElementById('news-feed');
                const side = document.getElementById('side-feed');
                list.innerHTML = ''; side.innerHTML = '';

                const filtered = cat === 'all' ? DATA : DATA.filter(i => i.cat === cat);
                
                filtered.forEach((item, idx) => {{
                    const div = document.createElement('div');
                    div.className = 'news-item';
                    div.innerHTML = `
                        <div class="cat-tag" style="margin-bottom:8px;">${{item.label}}</div>
                        <h3 class="news-title" onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</h3>
                        <div class="news-summary">${{item.summary}}</div>
                        <div style="font-size:11px; font-weight:700; color:#999;">SOURCE: ${{item.source}}</div>
                    `;
                    list.appendChild(div);

                    if(idx < 8) {{
                        const sDiv = document.createElement('div');
                        sDiv.className = 'side-link';
                        sDiv.textContent = item.title;
                        sDiv.onclick = () => showFull(${{DATA.indexOf(item)}});
                        side.appendChild(sDiv);
                    }}
                }});
            }}

            function filterFeed(cat, el) {{
                document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
                if (el) el.classList.add('active'); // 修正點 6
                document.getElementById('current-view-title').textContent = cat;
                renderFeed(cat);
                window.scrollTo(0, 450);
            }}

            function goHome(el) {{
                document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
                el.classList.add('active');
                document.getElementById('current-view-title').textContent = 'LATEST ANALYSIS';
                renderFeed('all');
                window.scrollTo(0, 0);
            }}

            function showFull(idx) {{
                const item = DATA[idx];
                const modal = document.getElementById('modal-content');
                modal.innerHTML = `
                    <span class="cat-tag" style="font-size:14px;">${{item.label}}</span>
                    <h1 class="report-headline">${{item.title}}</h1>
                    <div style="font-weight:700; color:#6c757d; margin-bottom:40px; letter-spacing:1px;">SOURCE: ${{item.source}}</div>
                    <div class="report-content">${{item.full_text || '尚未擷取到全文內容'}}</div>
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
    print("✅ 最終優化版儀表板已生成：index.html")

if __name__ == "__main__":
    run_dashboard()
