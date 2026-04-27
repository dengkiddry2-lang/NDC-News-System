import pdfplumber
import os
import json
import re

# ── 1. 分類與優先級定義 ──────────────────────────────────────────────
DEPARTMENTS = {
    "台灣政府與政策訊息": {
        "icon": "🏛️", "label": "Gov & Policy",
        "keywords": ["總統府", "行政院", "國發會", "經濟部", "財政部", "金管會", "國科會", "央行", "環境部", "農業部", "勞動部", "內政部", "交通部", "政策", "計畫", "預算", "法案", "條例", "施政", "補助", "方案"]
    },
    "台灣總體經濟與人口數據": {
        "icon": "📊", "label": "Macro & Demographics",
        "keywords": ["主計", "主計總處", "經濟成長率", "GDP", "CPI", "消費者物價", "物價", "通膨", "失業率", "薪資", "景氣燈號", "景氣", "外銷訂單", "出口", "進口", "進出口", "貿易統計", "海關", "財政統計", "稅收", "出生率", "死亡率", "人口", "人口統計", "少子化", "高齡化"]
    },
    "台灣產業與投資動向": {
        "icon": "🏭", "label": "Industry & Invest",
        "keywords": ["AI", "半導體", "台積電", "聯發科", "鴻海", "廣達", "緯穎", "CSP", "ASIC", "TPU", "CoWoS", "先進製程", "先進封裝", "資本支出", "民間投資", "投資", "資料中心", "算力", "伺服器", "PCB", "載板", "散熱", "供應鏈", "房市", "金融", "離岸風電", "電力", "能源", "製造業"]
    },
    "國際經濟與金融情勢": {
        "icon": "🌐", "label": "Global Finance",
        "keywords": ["Fed", "FOMC", "ECB", "BOJ", "聯準會", "歐央", "日銀", "利率", "升息", "降息", "美元", "匯率", "油價", "原油", "美中", "關稅", "貿易戰", "全球投資", "供應鏈", "地緣", "美伊", "伊朗", "荷莫茲", "戰爭", "制裁", "中東", "槍響"]
    },
    "國際機構與智庫報告": {
        "icon": "📘", "label": "Institutions",
        "keywords": ["IMF", "OECD", "世界銀行", "World Bank", "WTO", "BIS", "ADB", "WEF", "UN", "聯合國", "Brookings", "PIIE", "國際貨幣基金", "經濟合作暨發展組織"]
    },
    "社論與評論觀點": {
        "icon": "📝", "label": "Opinions",
        "keywords": ["社論", "時評", "社評", "專欄", "論壇", "民意", "觀點", "評論", "自由廣場", "時論", "名家", "經濟教室"]
    },
    "其他重要國內外事件": {
        "icon": "🗞️", "label": "Other Events",
        "keywords": []
    }
}

MUST_READ = ["Fed", "FOMC", "國發會", "主計總處", "GDP", "央行", "利率決議", "通膨", "槍響", "衝突"]

# ── 2. PDF 解析與文字洗滌邏輯 (核心修改點) ──────────────────────────────

def clean_text_blocks(text_list):
    """
    處理 PDF 轉文字常見的斷句問題：
    1. 移除不必要的換行（若行末不是標點符號，代表與下行相連）
    2. 保留真正的段落換行
    """
    if not text_list: return ""
    
    cleaned_lines = []
    current_paragraph = ""
    
    for line in text_list:
        line = line.strip()
        if not line: continue
        
        # 移除頁碼或其他雜訊 (如純數字)
        if line.isdigit(): continue
        
        current_paragraph += line
        
        # 判斷是否為段落結尾：如果行末是 」。？！? !，則視為段落結束
        if any(line.endswith(p) for p in ["。", "」", "？", "！", "”", "!", "?", "；"]):
            cleaned_lines.append(current_paragraph)
            current_paragraph = ""
            
    if current_paragraph:
        cleaned_lines.append(current_paragraph)
        
    # 用雙換行連接，確保網頁上有明顯段落感
    return "\n\n".join(cleaned_lines)

def build_article_index(pdf):
    index = {}
    last_key = None
    raw_content_map = {}

    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines: continue
        
        # 尋找來源行
        has_source = any(l.startswith("來源:") or l.startswith("來源：") for l in lines[:8])
        
        if has_source:
            src_idx = next(i for i, l in enumerate(lines) if l.startswith("來源:") or l.startswith("來源："))
            title_key = "".join(lines[:src_idx]).replace(" ", "")
            raw_content_map[title_key] = lines[src_idx + 1:]
            last_key = title_key
        elif last_key:
            raw_content_map[last_key].extend(lines)
            
    # 對所有收集到的內容進行段落重組
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
                        found_cat = cat
                        break
                
                prio = "must" if any(k in title for k in MUST_READ) else "normal"
                content = article_index.get(title.replace(" ", ""), "")
                
                all_items.append({
                    "title": title,
                    "source": str(row[2]).replace("\n", " ") if len(row)>2 else "新聞摘要",
                    "cat": found_cat,
                    "icon": DEPARTMENTS[found_cat]["icon"],
                    "priority": prio,
                    "summary": content[:200].replace("\n", "") + "...", # 摘要不換行
                    "full_text": content # 全文則保留重組後的段落
                })

    generate_html(all_items)

# ── 3. 日經風格 CSS (優化排版細節) ──────────────────────────────────

NIKKEI_STYLE = """
:root {
    --nikkei-red: #be0000;
    --nikkei-black: #1a1a1a;
    --nikkei-gray: #666;
    --nikkei-border: #dcdcdc;
}

body {
    font-family: "Noto Serif TC", serif;
    background: #fff; color: var(--nikkei-black); margin: 0; padding: 0; line-height: 1.8;
}

.header { border-top: 5px solid var(--nikkei-red); padding: 30px 0; text-align: center; border-bottom: 1px solid var(--nikkei-border); }
.brand { font-size: 36px; font-weight: 900; letter-spacing: 3px; color: var(--nikkei-red); }

.nav { display: flex; justify-content: center; gap: 25px; padding: 15px 0; border-bottom: 3px double var(--nikkei-border); overflow-x: auto; }
.nav-item { font-weight: 600; cursor: pointer; white-space: nowrap; font-size: 15px; }

.container { max-width: 1150px; margin: 0 auto; padding: 30px 20px; display: grid; grid-template-columns: 2.5fr 1.2fr; gap: 40px; }

/* 針對內容排版的深度優化 */
.main-article { border-bottom: 1px solid var(--nikkei-border); padding-bottom: 30px; margin-bottom: 30px; }
.main-article h2 { font-size: 28px; margin: 0 0 15px 0; line-height: 1.4; font-weight: 900; }
.summary { font-size: 16px; color: #444; text-align: justify; }

/* 彈窗內部的文字美化 */
.modal { display: none; position: fixed; inset: 0; background: rgba(255,255,255,0.98); z-index: 9999; overflow-y: auto; padding: 60px 20px; }
.modal-content { max-width: 800px; margin: 0 auto; }
.full-text-content { 
    font-size: 19px; 
    line-height: 2; 
    text-align: justify; 
    color: #222; 
    white-space: pre-wrap; 
    letter-spacing: 0.02em; 
}
.full-text-content p { margin-bottom: 1.5em; }

.side-title { border-left: 5px solid var(--nikkei-red); padding-left: 12px; font-size: 20px; font-weight: 900; margin-bottom: 20px; }
.side-item { border-bottom: 1px solid #eee; padding: 15px 0; font-size: 15px; display: flex; gap: 12px; }
"""

# ── 4. HTML 產生 (保留 JS 邏輯) ──────────────────────────────────────────────

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>國發會經濟規劃科 · 每日日經風格簡報</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@600;900&display=swap" rel="stylesheet">
        <style>{NIKKEI_STYLE}</style>
    </head>
    <body>
        <header class="header">
            <div class="brand">經濟規劃科 · 每日財經</div>
            <div id="current-date" style="margin-top:10px; font-weight:700; color:var(--nikkei-gray);"></div>
        </header>

        <nav class="nav" id="nav-bar">
            <div class="nav-item" onclick="filterData('all')">全領域</div>
        </nav>

        <div class="container">
            <main id="main-content"></main>
            <aside>
                <div class="side-title">最新快訊回顧</div>
                <div id="side-list"></div>
            </aside>
        </div>

        <div id="modal" class="modal">
            <span style="position:fixed; top:30px; right:50px; font-size:40px; cursor:pointer; color:var(--nikkei-red);" onclick="closeModal()">&times;</span>
            <div class="modal-content" id="modal-body"></div>
        </div>

        <script>
            const DATA = {data_json};
            
            function init() {{
                const d = new Date();
                document.getElementById('current-date').textContent = `${{d.getFullYear()}}年${{d.getMonth()+1}}月${{d.getDate()}}日`;
                filterData('all');
            }}

            function filterData(cat) {{
                const main = document.getElementById('main-content');
                const side = document.getElementById('side-list');
                main.innerHTML = '';
                side.innerHTML = '';

                const filtered = cat === 'all' ? DATA : DATA.filter(i => i.cat === cat);
                
                filtered.forEach((item, idx) => {{
                    const article = document.createElement('article');
                    article.className = 'main-article';
                    article.innerHTML = `
                        <div class="meta">${{item.icon}} ${{item.cat}} | ${{item.source}}</div>
                        <h2 onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</h2>
                        <div class="summary">${{item.summary}}</div>
                    `;
                    main.appendChild(article);

                    const sideDiv = document.createElement('div');
                    sideDiv.className = 'side-item';
                    sideDiv.innerHTML = `<span style="color:var(--nikkei-red); font-weight:900;">·</span><div style="cursor:pointer" onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</div>`;
                    side.appendChild(sideDiv);
                }});
            }}

            function showFull(idx) {{
                const item = DATA[idx];
                const modal = document.getElementById('modal');
                document.getElementById('modal-body').innerHTML = `
                    <div class="meta" style="font-size:18px">${{item.icon}} ${{item.cat}}</div>
                    <h1 style="font-size:38px; line-height:1.3; margin:20px 0; font-weight:900;">${{item.title}}</h1>
                    <div style="color:var(--nikkei-gray); margin-bottom:40px; border-bottom:1px solid #000; padding-bottom:10px;">來源：${{item.source}}</div>
                    <div class="full-text-content">${{item.full_text}}</div>
                `;
                modal.style.display = 'block';
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
    print("✅ 已優化段落重組：index.html")

if __name__ == "__main__":
    run_dashboard()
