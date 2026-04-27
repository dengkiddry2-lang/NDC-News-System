import pdfplumber
import os
import json
import re

# ── 1. 分類定義 ───────────────────────────────────────────────────
DEPARTMENTS = {
    "台灣政府與政策訊息": {
        "icon": "🏛️", "keywords": ["總統府", "行政院", "國發會", "經濟部", "財政部", "金管會", "國科會", "央行", "政策", "計畫", "預算", "法案", "施政"]
    },
    "台灣總體經濟與人口數據": {
        "icon": "📊", "keywords": ["主計", "GDP", "CPI", "物價", "通膨", "失業率", "景氣", "出口", "貿易", "人口", "少子化"]
    },
    "台灣產業與投資動向": {
        "icon": "🏭", "keywords": ["AI", "半導體", "台積電", "聯發科", "鴻海", "資本支出", "投資", "算力", "供應鏈", "能源"]
    },
    "國際經濟與金融情勢": {
        "icon": "🌐", "keywords": ["Fed", "FOMC", "ECB", "聯準會", "利率", "升息", "美元", "匯率", "美中", "貿易戰", "地緣", "戰爭"]
    },
    "國際機構與智庫報告": {
        "icon": "📘", "keywords": ["IMF", "OECD", "世界銀行", "World Bank", "WTO", "智庫", "Brookings", "PIIE"]
    },
    "社論與評論觀點": {
        "icon": "📝", "keywords": ["社論", "時評", "社評", "專欄", "論壇", "觀點", "評論", "名家"]
    },
    "其他重要國內外事件": {
        "icon": "🗞️", "keywords": []
    }
}

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
                    "icon": DEPARTMENTS[found_cat]["icon"],
                    "summary": content[:150].replace("\n", "") + "...",
                    "full_text": content
                })

    generate_html(all_items)

# ── 4. 日經風格 HTML/JS (首頁看板架構) ────────────────────────────────

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    dept_info = json.dumps(DEPARTMENTS, ensure_ascii=False)
    
    css = """
    :root { --nikkei-red: #be0000; --nikkei-black: #1a1a1a; --nikkei-border: #dcdcdc; }
    body { font-family: "Noto Serif TC", serif; background: #fff; color: var(--nikkei-black); margin: 0; padding: 0; }
    .header { border-top: 5px solid var(--nikkei-red); padding: 20px 0; text-align: center; border-bottom: 1px solid var(--nikkei-border); cursor: pointer; }
    .brand { font-size: 32px; font-weight: 900; letter-spacing: 2px; color: var(--nikkei-red); }
    
    /* 導航列 */
    .nav { display: flex; justify-content: center; gap: 15px; padding: 12px 0; border-bottom: 3px double var(--nikkei-border); position: sticky; top: 0; background: #fff; z-index: 100; }
    .nav-item { font-weight: 600; cursor: pointer; font-size: 14px; padding: 5px 10px; transition: 0.2s; }
    .nav-item:hover { color: var(--nikkei-red); }

    .container { max-width: 1200px; margin: 0 auto; padding: 30px 20px; }
    
    /* 看板網格 */
    .board-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 30px; }
    .board-section { border-top: 2px solid #000; padding-top: 15px; margin-bottom: 20px; }
    .board-title { color: var(--nikkei-red); font-size: 20px; font-weight: 900; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
    .board-title:hover { opacity: 0.7; }
    .board-title i { font-style: normal; font-size: 12px; color: #999; font-weight: 400; }
    
    .news-link { border-bottom: 1px solid #eee; padding: 10px 0; font-size: 16px; font-weight: 600; cursor: pointer; transition: 0.2s; }
    .news-link:hover { color: var(--nikkei-red); }
    .news-link .source { font-size: 12px; color: #999; font-weight: 400; display: block; margin-top: 4px; }

    /* 分類列表頁 */
    .list-view { display: none; }
    .list-item { border-bottom: 1px solid var(--nikkei-border); padding: 20px 0; }
    .list-item h3 { margin: 0 0 10px 0; font-size: 24px; cursor: pointer; }
    .list-item .summary { color: #555; font-size: 16px; line-height: 1.6; }

    /* 全文 Modal */
    .modal { display: none; position: fixed; inset: 0; background: #fff; z-index: 9999; overflow-y: auto; padding: 50px 20px; }
    .modal-content { max-width: 780px; margin: 0 auto; }
    .full-text { font-size: 19px; line-height: 2.1; text-align: justify; white-space: pre-line; word-break: break-word; }
    .close-btn { position: fixed; top: 20px; right: 40px; font-size: 40px; cursor: pointer; color: var(--nikkei-red); }
    
    .breadcrumb { margin-bottom: 20px; font-size: 14px; color: var(--nikkei-gray); }
    .breadcrumb span { cursor: pointer; color: var(--nikkei-red); font-weight: bold; }
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>經濟規劃科 · 每日新聞門戶</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@600;900&display=swap" rel="stylesheet">
        <style>{css}</style>
    </head>
    <body>
        <header class="header" onclick="showHome()">
            <div class="brand">經濟規劃科 · 每日新聞</div>
        </header>
        <nav class="nav" id="nav-bar"></nav>

        <div class="container">
            <div id="home-view" class="board-grid"></div>

            <div id="list-view" class="list-view">
                <div class="breadcrumb">您在：<span onclick="showHome()">首頁</span> / <b id="current-cat-name"></b></div>
                <div id="list-container"></div>
            </div>
        </div>

        <div id="modal" class="modal">
            <span class="close-btn" onclick="closeModal()">&times;</span>
            <div class="modal-content" id="modal-body"></div>
        </div>

        <script>
            const DATA = {data_json};
            const DEPTS = {dept_info};

            function init() {{
                const nav = document.getElementById('nav-bar');
                Object.keys(DEPTS).forEach(cat => {{
                    const div = document.createElement('div');
                    div.className = 'nav-item';
                    div.textContent = cat.replace('台灣', '').split('與')[0];
                    div.onclick = () => showCategory(cat);
                    nav.appendChild(div);
                }});
                showHome();
            }}

            // 顯示首頁聚合看板
            function showHome() {{
                document.getElementById('home-view').style.display = 'grid';
                document.getElementById('list-view').style.display = 'none';
                const container = document.getElementById('home-view');
                container.innerHTML = '';

                Object.keys(DEPTS).forEach(cat => {{
                    const items = DATA.filter(i => i.cat === cat);
                    if (items.length === 0) return;

                    const section = document.createElement('div');
                    section.className = 'board-section';
                    section.innerHTML = `
                        <div class="board-title" onclick="showCategory('${{cat}}')">
                            <span>${{DEPTS[cat].icon}} ${{cat}}</span>
                            <i>查看更多 ❯</i>
                        </div>
                    `;
                    
                    // 每個看板只顯示前 4 條
                    items.slice(0, 4).forEach(item => {{
                        const link = document.createElement('div');
                        link.className = 'news-link';
                        link.innerHTML = `${{item.title}}<span class="source">${{item.source}}</span>`;
                        link.onclick = () => showFull(${{DATA.indexOf(item)}});
                        section.appendChild(link);
                    }});
                    container.appendChild(section);
                }});
            }}

            // 顯示特定分類列表
            function showCategory(cat) {{
                document.getElementById('home-view').style.display = 'none';
                document.getElementById('list-view').style.display = 'block';
                document.getElementById('current-cat-name').textContent = cat;
                
                const container = document.getElementById('list-container');
                container.innerHTML = '';
                
                const items = DATA.filter(i => i.cat === cat);
                items.forEach(item => {{
                    const div = document.createElement('div');
                    div.className = 'list-item';
                    div.innerHTML = `
                        <div class="meta" style="color:var(--nikkei-red); font-size:12px; font-weight:bold;">${{item.source}}</div>
                        <h3 onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</h3>
                        <div class="summary">${{item.summary}}</div>
                    `;
                    container.appendChild(div);
                }});
                window.scrollTo(0,0);
            }}

            function showFull(idx) {{
                const item = DATA[idx];
                document.getElementById('modal-body').innerHTML = `
                    <div style="color:var(--nikkei-red); font-weight:bold; margin-bottom:10px;">${{item.cat}}</div>
                    <h1 style="font-size:36px; line-height:1.3; font-weight:900; margin-bottom:20px;">${{item.title}}</h1>
                    <div style="border-bottom:1px solid #000; padding-bottom:10px; margin-bottom:30px; color:#666;">來源：${{item.source}}</div>
                    <div class="full-text">${{item.full_text}}</div>
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
    print("✅ 看板式門戶網頁已生成：index.html")

if __name__ == "__main__":
    run_dashboard()
