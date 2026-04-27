import pdfplumber
import os
import json

# ── 1. 分類與優先級定義 (維持您的邏輯，僅優化關鍵字) ──────────────────────
DEPARTMENTS = {
    "風險監控": {"icon": "▲", "keywords": ["美伊", "伊朗", "戰爭", "川普", "選情", "地緣", "供應鏈"]},
    "總體數據": {"icon": "■", "keywords": ["出口", "進口", "通膨", "GDP", "主計", "景氣", "成長", "外銷"]},
    "產業動能": {"icon": "◆", "keywords": ["AI", "台積電", "半導體", "伺服器", "CoWoS", "設備", "製程"]},
    "政策規畫": {"icon": "●", "keywords": ["國發會", "政策", "計畫", "電力", "預算", "綠能", "算力"]}
}

# ── 2. PDF 解析邏輯 ──────────────────────────────────────────────

def build_article_index(pdf):
    index = {}
    last_key = None
    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines: continue
        has_source = any(l.startswith("來源:") or l.startswith("來源：") for l in lines[:8])
        if has_source:
            src_idx = next(i for i, l in enumerate(lines) if l.startswith("來源:") or l.startswith("來源："))
            title_key = "".join(lines[:src_idx]).replace(" ", "")
            index[title_key] = "\n".join(lines[src_idx + 1:])
            last_key = title_key
        elif len("".join(lines)) > 30 and last_key:
            index[last_key] += "\n" + "\n".join(lines)
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
        
        for page in pdf.pages[:5]:
            table = page.extract_table()
            if not table: continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]: continue
                title = str(row[1]).replace("\n", "").strip()
                if len(title) < 5: continue
                
                cat = "總體數據"
                for c, info in DEPARTMENTS.items():
                    if any(k in title for k in info["keywords"]): cat = c; break
                
                all_items.append({
                    "title": title,
                    "source": str(row[2]).replace("\n", " ") if len(row)>2 else "日經整理",
                    "cat": cat,
                    "summary": (article_index.get(title.replace(" ", ""), "")[:250]),
                    "full_text": article_index.get(title.replace(" ", ""), "")
                })

    data_json = json.dumps(all_items, ensure_ascii=False)
    generate_html(data_json)

# ── 3. 日經風格 CSS ──────────────────────────────────────────────

NIKKEI_CSS = """
:root {
    --nikkei-red: #be0000;
    --nikkei-bg: #fff;
    --nikkei-text: #1a1a1a;
    --nikkei-gray: #666;
    --nikkei-line: #ddd;
    --nikkei-sub-bg: #f7f7f7;
}

body {
    font-family: "Noto Serif TC", "Songti TC", serif;
    background: var(--nikkei-bg); color: var(--nikkei-text); margin: 0; padding: 0;
}

/* 報頭 Header */
.nikkei-header { border-top: 4px solid var(--nikkei-red); padding: 20px 0; text-align: center; border-bottom: 1px solid var(--nikkei-line); }
.brand { font-size: 32px; font-weight: 900; letter-spacing: 2px; color: var(--nikkei-red); text-decoration: none; }
.sub-brand { font-size: 14px; color: var(--nikkei-gray); margin-top: 5px; }

/* 導航 */
.nikkei-nav { display: flex; justify-content: center; gap: 40px; padding: 12px 0; border-bottom: 3px double var(--nikkei-line); font-weight: 600; font-size: 15px; }
.nav-item { cursor: pointer; transition: 0.2s; }
.nav-item:hover { color: var(--nikkei-red); }

/* 主要容器 */
.container { max-width: 1100px; margin: 0 auto; padding: 20px; display: grid; grid-template-columns: 2fr 1fr; gap: 30px; }

/* 焦點新聞 (左側) */
.main-news-item { border-bottom: 1px solid var(--nikkei-line); padding-bottom: 25px; margin-bottom: 25px; }
.main-news-item h2 { font-size: 26px; margin: 10px 0; line-height: 1.4; cursor: pointer; }
.main-news-item h2:hover { color: var(--nikkei-red); text-decoration: underline; }
.meta { font-size: 12px; color: var(--nikkei-red); font-weight: bold; margin-bottom: 8px; }
.summary { font-size: 15px; color: #444; line-height: 1.8; }

/* 側邊欄 (右側) */
.sidebar-title { border-left: 4px solid var(--nikkei-red); padding-left: 10px; font-size: 18px; font-weight: bold; margin-bottom: 15px; }
.side-item { border-bottom: 1px solid #eee; padding: 12px 0; font-size: 14px; display: flex; gap: 10px; }
.side-item .rank { color: var(--nikkei-red); font-weight: bold; font-style: italic; }

/* 彈窗內容 */
.modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 9999; overflow-y: auto; padding: 40px 20px; }
.modal-content { background: #fff; max-width: 800px; margin: 0 auto; padding: 40px; position: relative; }
.close-btn { position: absolute; top: 20px; right: 20px; font-size: 30px; cursor: pointer; }
"""

# ── 4. HTML 產生 ──────────────────────────────────────────────

def generate_html(data_json):
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>經濟規劃科 · 每日日經風格簡報</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@600;900&display=swap" rel="stylesheet">
        <style>{NIKKEI_CSS}</style>
    </head>
    <body>
        <header class="nikkei-header">
            <div class="brand">經濟規劃科新聞網</div>
            <div class="sub-brand">NDCEPC INTERNAL REPORT · <span id="current-date"></span></div>
        </header>

        <nav class="nikkei-nav">
            <div class="nav-item" onclick="filterCat('all')">最新新聞</div>
            <div class="nav-item" onclick="filterCat('風險監控')">風險監控</div>
            <div class="nav-item" onclick="filterCat('總體數據')">總體數據</div>
            <div class="nav-item" onclick="filterCat('產業動能')">產業動能</div>
            <div class="nav-item" onclick="filterCat('政策規畫')">政策規畫</div>
        </nav>

        <div class="container">
            <main id="main-content">
                </main>

            <aside>
                <div class="sidebar-title">重點指標</div>
                <div id="side-list">
                    </div>
            </aside>
        </div>

        <div id="modal" class="modal">
            <div class="modal-content">
                <span class="close-btn" onclick="closeModal()">&times;</span>
                <div id="modal-body"></div>
            </div>
        </div>

        <script>
            const DATA = {data_json};
            
            function init() {{
                const d = new Date();
                document.getElementById('current-date').textContent = `${{d.getFullYear()}}年${{d.getMonth()+1}}月${{d.getDate()}}日`;
                render('all');
            }}

            function render(filter) {{
                const main = document.getElementById('main-content');
                const side = document.getElementById('side-list');
                main.innerHTML = '';
                side.innerHTML = '';

                const filtered = filter === 'all' ? DATA : DATA.filter(i => i.cat === filter);

                filtered.forEach((item, idx) => {{
                    // 渲染左側主要內容
                    if(idx < 5) {{
                        const div = document.createElement('article');
                        div.className = 'main-news-item';
                        div.innerHTML = `
                            <div class="meta">${{item.cat}} | ${{item.source}}</div>
                            <h2 onclick="showModal(${{DATA.indexOf(item)}})">${{item.title}}</h2>
                            <div class="summary">${{item.summary}}... <span style="color:var(--nikkei-red); cursor:pointer;">[閱讀全文]</span></div>
                        `;
                        main.appendChild(div);
                    }}
                    
                    // 渲染右側列表
                    const sDiv = document.createElement('div');
                    sDiv.className = 'side-item';
                    sDiv.innerHTML = `<span class="rank">${{idx+1}}</span><span style="cursor:pointer" onclick="showModal(${{DATA.indexOf(item)}})">${{item.title}}</span>`;
                    side.appendChild(sDiv);
                }});
            }}

            function filterCat(cat) {{ render(cat); }}

            function showModal(idx) {{
                const item = DATA[idx];
                const modal = document.getElementById('modal');
                document.getElementById('modal-body').innerHTML = `
                    <div class="meta" style="font-size:16px">${{item.cat}}</div>
                    <h1 style="font-size:32px; border-bottom:2px solid #000; padding-bottom:15px">${{item.title}}</h1>
                    <div class="meta" style="color:#666">來源：${{item.source}}</div>
                    <div class="summary" style="font-size:18px; margin-top:30px; white-space:pre-wrap;">${{item.full_text || item.summary}}</div>
                `;
                modal.style.display = 'block';
            }}

            function closeModal() {{ document.getElementById('modal').style.display = 'none'; }}

            init();
        </script>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ 已生成日經風格新聞網頁：index.html")

if __name__ == "__main__":
    run_dashboard()
