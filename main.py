import pdfplumber
import os
import json
import re

# ── 1. 分類定義與固定優先序 (修正點 1, 2) ──────────────────────────────────
DEPARTMENTS = {
    "社論與評論觀點": {
        "icon": "📝", "keywords": ["社論", "時評", "社評", "專欄", "論壇", "觀點", "評論", "名家", "經濟教室"]
    },
    "國際機構與智庫報告": {
        "icon": "📘", "keywords": ["IMF", "OECD", "World Bank", "WTO", "智庫", "Brookings", "PIIE", "BIS", "ADB", "WEF", "UN", "聯合國"]
    },
    "台灣總體經濟與人口數據": {
        "icon": "📊", "keywords": ["主計", "GDP", "CPI", "物價", "通膨", "失業率", "薪資", "景氣", "經濟成長率", "年增率", "月增率", "外銷訂單", "海關", "出口統計", "進口統計", "財政統計", "稅收", "出生率", "死亡率", "人口統計", "勞動力", "就業", "少子化", "高齡化"]
    },
    "台灣產業與投資動向": {
        "icon": "🏭", "keywords": ["AI", "半導體", "台積電", "聯發科", "資本支出", "投資", "供應鏈", "算力", "伺服器", "離岸風電"]
    },
    "國際經濟與金融情勢": {
        "icon": "🌐", "keywords": ["Fed", "FOMC", "聯準會", "利率", "升息", "降息", "美元", "匯率", "地緣", "美中", "貿易戰"]
    },
    "台灣政府與政策訊息": {
        "icon": "🏛️", "keywords": ["總統府", "行政院", "國發會", "經濟部", "財政部", "政策", "計畫", "預算", "法案", "行政院會", "施政報告", "補助"]
    },
    "其他重要國內外事件": {
        "icon": "🗞️", "keywords": []
    }
}

# 修正點 1: 固定判定優先順序
CATEGORY_ORDER = [
    "社論與評論觀點",
    "國際機構與智庫報告",
    "台灣總體經濟與人口數據",
    "台灣產業與投資動向",
    "國際經濟與金融情勢",
    "台灣政府與政策訊息",
    "其他重要國內外事件"
]

MUST_READ_KEYS = ["Fed", "國發會", "主計", "GDP", "利率", "槍響", "衝突", "戰爭", "下修", "調升"]

# ── 2. 文本處理函數 (修正點 4) ──────────────────────────────────────────

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

def extract_summary(content, limit=220):
    """ 修正點 4: 擷取第一個自然段落作為摘要 """
    if not content:
        return "尚未擷取到內文摘要"
    parts = [p.strip() for p in content.split("\n\n") if p.strip()]
    if parts:
        return parts[0][:limit] + ("..." if len(parts[0]) > limit else "")
    return content[:limit] + ("..." if len(content) > limit else "")

def find_article(article_index, title):
    key = title.replace(" ", "")
    for n in [12, 10, 8, 6, 4]:
        short = key[:n]
        if not short: continue
        for art_key, content in article_index.items():
            if short in art_key: return content
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
        for page in pdf.pages[:15]: # 擴大掃描範圍以涵蓋目錄
            table = page.extract_table()
            if not table: continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]: continue
                title = str(row[1]).replace("\n", "").strip()
                source = str(row[2]).replace("\n", " ") if len(row) > 2 and row[2] else "EPC智庫"
                
                # 修正點 3: 過濾短標題與表頭雜訊
                if len(title) < 5 or any(k in title for k in ["新聞議題", "報導媒體", "回到目錄"]):
                    continue
                
                classify_text = title + " " + source
                found_cat = "其他重要國內外事件"
                for cat in CATEGORY_ORDER:
                    if any(k in classify_text for k in DEPARTMENTS[cat]["keywords"]):
                        found_cat = cat; break
                
                content = find_article(article_index, title)
                summary = extract_summary(content) # 修正點 4
                
                all_items.append({
                    "title": title,
                    "source": source,
                    "cat": found_cat,
                    "priority": 1 if any(k in title for k in MUST_READ_KEYS) else 0,
                    "summary": summary,
                    "full_text": content
                })
    generate_html(all_items)

# ── 4. 真．IMF 風格 HTML (修正點 5, 6, 7) ───────────────────────

def generate_html(data):
    # 修正點 6: Python 端 Escape HTML 特殊字元 (簡易防注入)
    def escape_html(text):
        if not text: return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    
    for item in data:
        item["full_text"] = escape_html(item["full_text"])
        item["title"] = escape_html(item["title"])
        item["summary"] = escape_html(item["summary"])

    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    dept_info = json.dumps(DEPARTMENTS, ensure_ascii=False).replace("</", "<\\/")
    
    css = """
    :root { --imf-navy: #00335e; --imf-accent: #0076d6; --imf-bg-light: #f8f9fa; }
    body { font-family: 'Public Sans', sans-serif, "Noto Serif TC"; background: #fff; color: #212529; margin:0; line-height: 1.6; }

    .top-utility { background: #000; color: #fff; font-size: 10px; font-weight: 700; padding: 12px 60px; letter-spacing: 1px; display: flex; justify-content: space-between; }
    .header { padding: 30px 60px; display: flex; align-items: center; background: #fff; border-bottom: 1px solid #eee; }
    .brand-titles h1 { margin: 0; font-size: 26px; color: var(--imf-navy); font-weight: 800; border-left: 5px solid var(--imf-navy); padding-left: 15px; }

    .imf-nav { background: var(--imf-navy); display: flex; padding: 0 60px; position: sticky; top: 0; z-index: 100; overflow-x: auto; scrollbar-width: none; }
    .nav-item { color: #fff; padding: 18px 25px; font-size: 13.5px; font-weight: 700; cursor: pointer; transition: 0.3s; white-space: nowrap; }
    .nav-item:hover, .nav-item.active { background: var(--imf-accent); }

    .carousel-container { background: var(--imf-bg-light); padding: 50px 0; border-bottom: 1px solid #eee; overflow: hidden; }
    .carousel-inner { max-width: 1200px; margin: 0 auto; padding: 0 60px; position: relative; height: 320px; }
    .carousel-slide { 
        position: absolute; inset: 0 60px; background: var(--imf-navy); color: #fff; padding: 45px; 
        box-shadow: 0 15px 45px rgba(0,0,0,0.1); display: none; flex-direction: column; justify-content: center;
        border-top: 8px solid var(--imf-accent); opacity: 0; transition: opacity 0.8s ease-in-out;
    }
    .carousel-slide.active { display: flex; opacity: 1; }
    .carousel-slide h2 { font-size: 40px; margin: 0 0 20px 0; font-family: 'Noto Serif TC', serif; line-height: 1.2; cursor: pointer; }

    .main-layout { max-width: 1200px; margin: 50px auto; padding: 0 60px; display: grid; grid-template-columns: 1fr 320px; gap: 70px; }
    .feed-section-title { font-size: 22px; font-weight: 800; color: var(--imf-navy); border-bottom: 2px solid var(--imf-navy); padding-bottom: 15px; margin-bottom: 30px; }
    .news-item { padding: 25px 0; border-bottom: 1px solid #eee; }
    .news-title { font-size: 22px; font-weight: 800; color: var(--imf-navy); margin: 0 0 10px 0; cursor: pointer; font-family: 'Noto Serif TC', serif; }
    
    .modal { display: none; position: fixed; inset: 0; background: #fff; z-index: 1000; overflow-y: auto; }
    .modal-header { padding: 20px 60px; background: #fff; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; position: sticky; top: 0; }
    .modal-body { max-width: 850px; margin: 60px auto; padding: 0 60px; }

    /* 修正點 7: 全文內容渲染樣式 */
    .article-content { 
        font-size: 19px; 
        line-height: 2.1; 
        white-space: pre-line; 
        text-align: justify; 
        word-break: break-word;
        color: #222;
    }

    .read-btn { background: #fff; color: var(--imf-navy); border: none; padding: 10px 20px; font-weight: 800; cursor: pointer; align-self: flex-start; margin-top: 15px; }
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>經濟規劃科 Intelligence Hub</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@900&family=Public+Sans:wght@400;700;800&display=swap" rel="stylesheet">
        <style>{css}</style>
    </head>
    <body>
        <div class="top-utility">
            <div>EPC INTELLIGENCE NETWORK</div>
            <div id="roc-year-label"></div>
        </div>
        
        <header class="header">
            <div class="brand-titles">
                <h1>經濟規劃科 Intelligence Hub</h1>
                <p>National Development Council · Economic Planning Division</p>
            </div>
            <div style="margin-left:auto; font-weight:800; color:var(--imf-navy);" id="today-date"></div>
        </header>

        <nav class="imf-nav" id="nav-bar">
            <div class="nav-item active" onclick="location.reload()">首頁 HOME</div>
        </nav>

        <div id="home-view">
            <section class="carousel-container">
                <div class="carousel-inner" id="carousel-area"></div>
            </section>

            <div class="main-layout">
                <section>
                    <div class="feed-section-title" id="current-view-title">最新分析 LATEST ANALYSIS</div>
                    <div id="news-feed"></div>
                </section>
                <aside>
                    <div style="background:var(--imf-bg-light); padding:30px; border-top:5px solid var(--imf-navy);">
                        <h3 style="font-size:16px; margin-top:0;">INTERNAL USE ONLY</h3>
                        <p style="font-size:14px; color:#666;">本資訊供國發會經濟規劃科內部參考，請注意資安規範。</p>
                    </div>
                </aside>
            </div>
        </div>

        <div id="modal" class="modal">
            <div class="modal-header">
                <div style="font-weight:900; color:var(--imf-navy);">經濟規劃科 EPC REPORT</div>
                <button onclick="closeModal()" style="border:none; background:var(--imf-navy); color:#fff; padding:8px 20px; cursor:pointer; font-weight:700;">關閉 CLOSE</button>
            </div>
            <div class="modal-body" id="modal-content"></div>
        </div>

        <script>
            const DATA = {data_json};
            const DEPTS = {dept_info};

            function init() {{
                const yr = new Date().getFullYear();
                document.getElementById('roc-year-label').textContent = '民國 ' + (yr - 1911) + ' 年';
                document.getElementById('today-date').textContent = new Date().toLocaleDateString('zh-TW', {{ year: 'numeric', month: 'long', day: 'numeric' }});
                
                const nav = document.getElementById('nav-bar');
                Object.keys(DEPTS).forEach(cat => {{
                    if(cat === "其他重要國內外事件") return;
                    const div = document.createElement('div');
                    div.className = 'nav-item';
                    div.textContent = cat;
                    div.onclick = function() {{ filterFeed(cat, this); }};
                    nav.appendChild(div);
                }});

                renderCarousel();
                renderFeed('all');
            }}

            function renderCarousel() {{
                const area = document.getElementById('carousel-area');
                
                // 修正點 5: 處理無資料情況
                if (DATA.length === 0) {{
                    area.innerHTML = '<div class="carousel-slide active"><h2>今日尚無新聞資料錄入</h2></div>';
                    return;
                }}

                const featured = DATA.filter(i => i.priority === 1).slice(0, 5);
                if(featured.length === 0) featured.push(...DATA.slice(0, 5));

                featured.forEach((item, idx) => {{
                    const slide = document.createElement('div');
                    slide.className = 'carousel-slide' + (idx === 0 ? ' active' : '');
                    slide.innerHTML = `
                        <span style="font-size:12px; color:#ffca28; font-weight:800; text-transform:uppercase;">FEATURED · ${{item.cat}}</span>
                        <h2 onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</h2>
                        <div style="opacity:0.8; font-size:16px;">來源：${{item.source}}</div>
                        <button class="read-btn" onclick="showFull(${{DATA.indexOf(item)}})">閱讀全文 VIEW REPORT</button>
                    `;
                    area.appendChild(slide);
                }});

                let current = 0;
                setInterval(() => {{
                    const slides = document.querySelectorAll('.carousel-slide');
                    if(slides.length <= 1) return;
                    slides[current].classList.remove('active');
                    current = (current + 1) % slides.length;
                    slides[current].classList.add('active');
                }}, 6000);
            }}

            function renderFeed(cat) {{
                const list = document.getElementById('news-feed');
                list.innerHTML = '';
                const filtered = cat === 'all' ? DATA : DATA.filter(i => i.cat === cat);
                
                filtered.forEach(item => {{
                    const div = document.createElement('div');
                    div.className = 'news-item';
                    div.innerHTML = `
                        <div style="font-size:11px; font-weight:800; color:var(--imf-accent); margin-bottom:5px;">${{item.cat}}</div>
                        <h3 class="news-title" onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</h3>
                        <div style="font-size:15px; color:#555; text-align:justify;">${{item.summary}}</div>
                    `;
                    list.appendChild(div);
                }});
            }}

            function filterFeed(cat, el) {{
                document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
                if (el) el.classList.add('active');
                document.getElementById('current-view-title').textContent = cat;
                renderFeed(cat);
                window.scrollTo(0, 500);
            }}

            function showFull(idx) {{
                const item = DATA[idx];
                // 修正點 7: 統一內文樣式渲染
                document.getElementById('modal-content').innerHTML = `
                    <div style="color:var(--imf-accent); font-weight:800; font-size:14px; border-bottom:2px solid #eee; padding-bottom:10px; margin-bottom:20px;">
                        ${{item.cat}}
                    </div>
                    <h1 style="font-size:48px; line-height:1.2; color:var(--imf-navy); margin-bottom:30px; font-family:'Noto Serif TC', serif;">
                        ${{item.title}}
                    </h1>
                    <div style="font-weight:700; color:#666; margin-bottom:40px;">來源：${{item.source}}</div>
                    <div class="article-content">${{item.full_text || '尚未擷取到全文內容'}}</div>
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
    print("✅ 深度優化版 (穩定度升級) 已生成：index.html")

if __name__ == "__main__":
    run_dashboard()
