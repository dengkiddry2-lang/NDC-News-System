import pdfplumber
import os
import json
import re

# ── 1. 分類定義與優先序 (完全按照您的中文分類) ──────────────────────────────────
DEPARTMENTS = {
    "社論與評論觀點": {
        "icon": "📝", "keywords": ["社論", "時評", "社評", "專欄", "論壇", "觀點", "評論", "名家", "經濟教室"]
    },
    "國際機構與智庫報告": {
        "icon": "📘", "keywords": ["IMF", "OECD", "World Bank", "WTO", "智庫", "Brookings", "PIIE", "BIS", "ADB", "WEF", "UN", "聯合國", "世界銀行"]
    },
    "台灣總體經濟與人口數據": {
        "icon": "📊", "keywords": ["主計", "GDP", "CPI", "物價", "通膨", "失業率", "薪資", "景氣", "經濟成長率", "統計", "公布", "年增", "月增", "外銷訂單", "海關", "出口", "人口", "少子化", "高齡化"]
    },
    "台灣產業與投資動向": {
        "icon": "🏭", "keywords": ["AI", "半導體", "台積電", "聯發科", "資本支出", "投資", "供應鏈", "算力", "伺服器", "離岸風電"]
    },
    "國際經濟與金融情勢": {
        "icon": "🌐", "keywords": ["Fed", "FOMC", "聯準會", "利率", "升息", "降息", "美元", "匯率", "地緣", "美中", "貿易戰"]
    },
    "台灣政府與政策訊息": {
        "icon": "🏛️", "keywords": ["總統府", "行政院", "國發會", "經濟部", "財政部", "政策", "計畫", "預算", "法案", "施政"]
    },
    "其他重要國內外事件": {
        "icon": "🗞️", "keywords": []
    }
}

CATEGORY_ORDER = ["社論與評論觀點", "國際機構與智庫報告", "台灣總體經濟與人口數據", "台灣產業與投資動向", "國際經濟與金融情勢", "台灣政府與政策訊息", "其他重要國內外事件"]
MUST_READ_KEYS = ["Fed", "國發會", "主計", "GDP", "利率", "槍響", "衝突", "戰爭", "下修", "調升"]

# ── 2. 文本解析與清洗 ──────────────────────────────────────────

def is_noise_line(line):
    noise = ["回到目錄", "來源:", "來源：", "版面", "作者", "日期", "頁次"]
    if line.isdigit(): return True
    return any(k in line for k in noise)

def clean_text_blocks(text_list):
    if not text_list: return ""
    combined_text = ""
    for line in text_list:
        line = line.strip()
        if not line or is_noise_line(line): continue
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
    best_content = ""
    best_score = 0
    for art_key, content in article_index.items():
        score = 0
        for n in [14, 12, 10, 8, 6]:
            if key[:n] and key[:n] in art_key:
                score = n
                break
        if score > best_score:
            best_score = score
            best_content = content
    return best_content if best_score >= 6 else ""

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
        elif last_key and len("".join(lines)) > 50 and not page.extract_table():
            raw_content_map[last_key].extend(lines)
        else:
            last_key = None
    for key, text_list in raw_content_map.items():
        index[key] = clean_text_blocks(text_list)
    return index

# ── 3. 執行流程 ───────────────────────────────────────────────────

def run_dashboard():
    data_folder = "data"
    if not os.path.exists(data_folder): os.makedirs(data_folder)
    pdf_files = [f for f in os.listdir(data_folder) if f.lower().endswith(".pdf")]
    
    all_items = []
    if pdf_files:
        pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join(data_folder, x)))
        latest_pdf = os.path.join(data_folder, pdf_files[-1])
        
        with pdfplumber.open(latest_pdf) as pdf:
            article_index = build_article_index(pdf)
            for page in pdf.pages[:15]:
                table = page.extract_table()
                if not table: continue
                for row in table[1:]:
                    if not row or len(row) < 2 or not row[1]: continue
                    title = str(row[1]).replace("\n", "").strip()
                    source = str(row[2]).replace("\n", " ").strip() if len(row) > 2 else "EPC彙整"
                    if len(title) < 5 or any(k in title for k in ["新聞議題", "報導媒體", "目錄", "頁次"]): continue
                    
                    classify_text = title + " " + source
                    found_cat = "其他重要國內外事件"
                    for cat in CATEGORY_ORDER:
                        if any(k in classify_text for k in DEPARTMENTS[cat]["keywords"]):
                            found_cat = cat; break
                    
                    content = find_article(article_index, title)
                    all_items.append({
                        "title": title, "source": source, "cat": found_cat,
                        "priority": 1 if any(k in title for k in MUST_READ_KEYS) else 0,
                        "summary": content[:150].replace("\n", "") + "..." if content else "摘要抓取中...",
                        "full_text": content
                    })
    
    generate_html(all_items)

# ── 4. HTML 生成 (修正 JS 語法衝突與中文化) ──────────────────────────

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    dept_info = json.dumps(DEPARTMENTS, ensure_ascii=False).replace("</", "<\\/")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>經濟規劃科 Intelligence Hub</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@900&family=Public+Sans:wght@400;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{ --imf-navy: #00335e; --imf-accent: #0076d6; --imf-bg-light: #f8f9fa; }}
            body {{ font-family: 'Public Sans', sans-serif, "Noto Serif TC"; background: #fff; color: #212529; margin:0; line-height: 1.6; }}
            .header {{ padding: 30px 60px; display: flex; align-items: center; border-bottom: 1px solid #eee; }}
            .brand-titles h1 {{ margin: 0; font-size: 26px; color: var(--imf-navy); font-weight: 800; border-left: 5px solid var(--imf-navy); padding-left: 15px; }}
            .imf-nav {{ background: var(--imf-navy); display: flex; padding: 0 60px; position: sticky; top: 0; z-index: 100; overflow-x: auto; scrollbar-width: none; }}
            .nav-item {{ color: #fff; padding: 18px 25px; font-size: 13.5px; font-weight: 700; cursor: pointer; transition: 0.3s; white-space: nowrap; }}
            .nav-item:hover, .nav-item.active {{ background: var(--imf-accent); }}
            .carousel-container {{ background: var(--imf-bg-light); padding: 50px 0; border-bottom: 1px solid #eee; overflow: hidden; }}
            .carousel-inner {{ max-width: 1200px; margin: 0 auto; padding: 0 60px; position: relative; height: 320px; }}
            .carousel-slide {{ position: absolute; inset: 0 60px; background: var(--imf-navy); color: #fff; padding: 45px; display: none; flex-direction: column; justify-content: center; border-top: 8px solid var(--imf-accent); opacity: 0; transition: opacity 0.8s ease; }}
            .carousel-slide.active {{ display: flex; opacity: 1; }}
            .news-item {{ padding: 25px 0; border-bottom: 1px solid #eee; }}
            .modal {{ display: none; position: fixed; inset: 0; background: #fff; z-index: 1000; overflow-y: auto; padding: 50px; }}
        </style>
    </head>
    <body>
        <div style="background:#000; color:#fff; font-size:10px; padding:12px 60px;">EPC INTELLIGENCE · <span id="roc-year"></span></div>
        <header class="header">
            <div class="brand-titles"><h1>經濟規劃科 Intelligence Hub</h1></div>
            <div id="today-date" style="margin-left:auto; font-weight:800; color:var(--imf-navy);"></div>
        </header>
        <nav class="imf-nav" id="nav-bar"><div class="nav-item active" onclick="location.reload()">最新首頁</div></nav>
        
        <section class="carousel-container"><div class="carousel-inner" id="carousel-area"></div></section>
        
        <div style="max-width:1200px; margin:50px auto; padding:0 60px; display:grid; grid-template-columns:1fr 320px; gap:70px;">
            <section><div id="news-feed"></div></section>
            <aside>
                <div style="background:var(--imf-bg-light); padding:30px; border-top:5px solid var(--imf-navy);">
                    <h3 style="font-size:16px; margin-top:0;">系統提示</h3>
                    <p style="font-size:14px; color:#666;">如畫面空白，請確認 PDF 目錄表格是否正常並放置於 data 資料夾內。</p>
                </div>
            </aside>
        </div>

        <div id="modal" class="modal">
            <div style="max-width:800px; margin:0 auto;">
                <button onclick="closeModal()" style="float:right; background:var(--imf-navy); color:#fff; border:none; padding:10px 20px; cursor:pointer; font-weight:700;">關閉 CLOSE</button>
                <div id="modal-content"></div>
            </div>
        </div>

        <script>
            const DATA = {data_json};
            const DEPTS = {dept_info};

            function esc(s) {{ return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }}

            function init() {{
                const yr = new Date().getFullYear();
                document.getElementById('roc-year').textContent = '民國 ' + (yr - 1911) + ' 年 INTERNAL USE ONLY';
                document.getElementById('today-date').textContent = new Date().toLocaleDateString('zh-TW', {{ year:'numeric', month:'long', day:'numeric' }});
                
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
                if (DATA.length === 0) {{ area.innerHTML = '<div class="carousel-slide active"><h2>今日尚無新聞解析資料</h2></div>'; return; }}
                
                const featured = DATA.filter(i => i.priority === 1).slice(0, 5);
                if(featured.length === 0) featured.push(...DATA.slice(0, 5));
                
                featured.forEach((item, idx) => {{
                    const slide = document.createElement('div');
                    slide.className = 'carousel-slide' + (idx === 0 ? ' active' : '');
                    slide.innerHTML = `<span style="color:#ffca28; font-weight:800; font-size:12px;">FEATURED REPORT · \${{esc(item.cat)}}</span><h2 style="font-size:40px; font-family:'Noto Serif TC'; cursor:pointer" onclick="showFull(\${{DATA.indexOf(item)}})">\${{esc(item.title)}}</h2><div style="opacity:0.8; font-size:14px;">來源：\${{esc(item.source)}}</div>`;
                    area.appendChild(slide);
                }});

                let cur = 0;
                setInterval(() => {{
                    const s = document.querySelectorAll('.carousel-slide');
                    if(s.length <= 1) return;
                    s[cur].classList.remove('active');
                    cur = (cur + 1) % s.length;
                    s[cur].classList.add('active');
                }}, 5000);
            }}

            function renderFeed(cat) {{
                const list = document.getElementById('news-feed');
                list.innerHTML = '';
                const f = cat === 'all' ? DATA : DATA.filter(i => i.cat === cat);
                if (f.length === 0) {{ list.innerHTML = '<p style="color:#999;">此分類今日暫無資料</p>'; return; }}
                f.forEach(item => {{
                    const div = document.createElement('div');
                    div.className = 'news-item';
                    div.innerHTML = `<div style="font-size:11px; font-weight:800; color:var(--imf-accent); margin-bottom:5px;">\${{esc(item.cat)}}</div><h3 style="cursor:pointer; font-size:22px; color:var(--imf-navy); margin:0 0 10px 0; font-family:'Noto Serif TC', serif;" onclick="showFull(\${{DATA.indexOf(item)}})">\${{esc(item.title)}}</h3><div style="font-size:15px; color:#555; text-align:justify;">\${{esc(item.summary)}}</div>`;
                    list.appendChild(div);
                }});
            }}

            function filterFeed(cat, el) {{
                document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
                if (el) el.classList.add('active');
                renderFeed(cat);
                window.scrollTo(0, 500);
            }}

            function showFull(idx) {{
                const item = DATA[idx];
                document.getElementById('modal-content').innerHTML = `
                    <div style="color:var(--imf-accent); font-weight:800; font-size:14px; margin-bottom:10px;">\${{esc(item.cat)}}</div>
                    <h1 style="font-size:42px; font-family:'Noto Serif TC'; line-height:1.2; color:var(--imf-navy); margin-bottom:20px;">\${{esc(item.title)}}</h1>
                    <div style="font-weight:700; color:#666; margin-bottom:30px; border-bottom:1px solid #eee; padding-bottom:10px;">來源：\${{esc(item.source)}}</div>
                    <div style="font-size:19px; line-height:2.1; white-space:pre-line; text-align:justify; word-break:break-word;">\${{esc(item.full_text) || '尚未擷取到全文內容'}}</div>
                `;
                document.getElementById('modal').style.display = 'block';
                document.body.style.overflow = 'hidden';
            }}

            function closeModal() {{ document.getElementById('modal').style.display = 'none'; document.body.style.overflow = 'auto'; }}
            init();
        </script>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ 已生成修正版 index.html。")

if __name__ == "__main__":
    run_dashboard()
