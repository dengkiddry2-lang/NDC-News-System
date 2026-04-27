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

# ── 2. 文字清洗與段落重組邏輯 (核心升級版) ─────────────────────────────

def clean_text_blocks(text_list):
    """
    強化版段落重組：
    1. 合併 PDF 斷行
    2. 用標點做句子切分
    3. 再組回自然段落（每 3-4 句一段）
    """
    if not text_list:
        return ""

    # Step 1：合併亂斷行
    combined_text = ""
    for line in text_list:
        line = line.strip()
        if not line or line.isdigit():
            continue

        # 如果前一行結尾不是標點，代表這行跟前一行是連在一起的
        if combined_text and not combined_text.endswith(("。", "！", "？", "；", "」", "”")):
            combined_text += line
        else:
            combined_text += "\n" + line

    combined_text = combined_text.strip()

    # Step 2：用標點切句 (利用正則表達式的 Lookbehind)
    sentences = re.split(r'(?<=[。！？；])', combined_text)

    # Step 3：重組段落
    paragraphs = []
    current_para = ""
    sentence_count = 0

    for s in sentences:
        s = s.strip()
        if not s:
            continue

        current_para += s
        sentence_count += 1

        # 邏輯：滿 3 句且該句以結尾標點結束，或者句子特別長，就斷段
        if (sentence_count >= 3 and s.endswith(("。", "！", "？", "；"))) or s.endswith(("」", "”")):
            paragraphs.append(current_para.strip())
            current_para = ""
            sentence_count = 0

    if current_para:
        paragraphs.append(current_para.strip())

    return "\n\n".join(paragraphs)

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

# ── 3. 日經風格 CSS 與 HTML 產生 ──────────────────────────────────

def run_dashboard():
    if not os.path.exists("data"): os.makedirs("data")
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files: return
    
    pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join("data", x)))
    latest_pdf = os.path.join("data", pdf_files[-1])

    with pdfplumber.open(latest_pdf) as pdf:
        article_index = build_article_index(pdf)
        all_items = []
        
        for page in pdf.pages[:10]: # 掃描目錄
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
                    "source": str(row[2]).replace("\n", " ") if len(row)>2 else "智庫動態",
                    "cat": found_cat,
                    "icon": DEPARTMENTS[found_cat]["icon"],
                    "priority": prio,
                    "summary": content[:120].replace("\n", "") + "...",
                    "full_text": content
                })

    generate_html(all_items)

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    
    css = """
    :root { --nikkei-red: #be0000; --nikkei-black: #1a1a1a; --nikkei-border: #dcdcdc; }
    body { font-family: "Noto Serif TC", serif; background: #fff; color: var(--nikkei-black); margin: 0; padding: 0; }
    .header { border-top: 5px solid var(--nikkei-red); padding: 25px 0; text-align: center; border-bottom: 1px solid var(--nikkei-border); }
    .brand { font-size: 32px; font-weight: 900; letter-spacing: 2px; color: var(--nikkei-red); }
    .nav { display: flex; justify-content: center; gap: 20px; padding: 12px 0; border-bottom: 3px double var(--nikkei-border); overflow-x: auto; }
    .nav-item { font-weight: 600; cursor: pointer; white-space: nowrap; font-size: 14px; }
    .container { max-width: 1100px; margin: 0 auto; padding: 30px 20px; display: grid; grid-template-columns: 2.5fr 1fr; gap: 40px; }
    .main-article { border-bottom: 1px solid var(--nikkei-border); padding-bottom: 25px; margin-bottom: 25px; }
    .meta { font-size: 12px; color: var(--nikkei-red); font-weight: 700; margin-bottom: 8px; }
    .main-article h2 { font-size: 26px; margin: 0 0 12px 0; line-height: 1.4; font-weight: 900; cursor: pointer; }
    .main-article h2:hover { color: var(--nikkei-red); text-decoration: underline; }
    
    /* 閱讀體驗優化 CSS */
    .full-text-content { 
        font-size: 19px; 
        line-height: 2.1; 
        text-align: justify; 
        color: #222; 
        white-space: pre-line; 
        word-break: break-word;
        letter-spacing: 0.03em;
    }
    .modal { display: none; position: fixed; inset: 0; background: #fff; z-index: 9999; overflow-y: auto; padding: 50px 20px; }
    .modal-content { max-width: 780px; margin: 0 auto; }
    .close-btn { position: fixed; top: 20px; right: 40px; font-size: 40px; cursor: pointer; color: var(--nikkei-red); }
    .side-item { border-bottom: 1px solid #eee; padding: 12px 0; font-size: 15px; }
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>經濟規劃科 · 每日新聞報 (智庫升級版)</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@600;900&display=swap" rel="stylesheet">
        <style>{css}</style>
    </head>
    <body>
        <header class="header">
            <div class="brand">經濟規劃科 · 每日新聞</div>
            <div id="current-date" style="margin-top:8px; font-weight:700; color:#666;"></div>
        </header>
        <nav class="nav" id="nav-bar"><div class="nav-item" onclick="filterData('all')">全領域</div></nav>
        <div class="container"><main id="main-content"></main><aside><div style="border-left:5px solid var(--nikkei-red); padding-left:10px; font-weight:900; margin-bottom:15px;">焦點回顧</div><div id="side-list"></div></aside></div>
        <div id="modal" class="modal"><span class="close-btn" onclick="closeModal()">&times;</span><div class="modal-content" id="modal-body"></div></div>
        <script>
            const DATA = {data_json};
            function init() {{
                const d = new Date();
                document.getElementById('current-date').textContent = `${{d.getFullYear()}}年${{d.getMonth()+1}}月${{d.getDate()}}日`;
                const cats = [...new Set(DATA.map(i => i.cat))];
                const nav = document.getElementById('nav-bar');
                cats.forEach(c => {{
                    const div = document.createElement('div');
                    div.className = 'nav-item';
                    div.textContent = c.replace('台灣', '');
                    div.onclick = () => filterData(c);
                    nav.appendChild(div);
                }});
                filterData('all');
            }}
            function filterData(cat) {{
                const main = document.getElementById('main-content');
                const side = document.getElementById('side-list');
                main.innerHTML = ''; side.innerHTML = '';
                const filtered = cat === 'all' ? DATA : DATA.filter(i => i.cat === cat);
                filtered.forEach((item, idx) => {{
                    const art = document.createElement('article'); art.className = 'main-article';
                    art.innerHTML = `<div class="meta">${{item.icon}} ${{item.cat}}</div><h2 onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</h2><div style="color:#444;">${{item.summary}}</div>`;
                    main.appendChild(art);
                    const sd = document.createElement('div'); sd.className = 'side-item';
                    sd.innerHTML = `<span style="color:var(--nikkei-red); margin-right:8px;">●</span><span style="cursor:pointer" onclick="showFull(${{DATA.indexOf(item)}})">${{item.title}}</span>`;
                    side.appendChild(sd);
                }});
            }}
            function showFull(idx) {{
                const item = DATA[idx];
                document.getElementById('modal-body').innerHTML = `
                    <div class="meta" style="font-size:16px;">${{item.icon}} ${{item.cat}}</div>
                    <h1 style="font-size:36px; line-height:1.3; font-weight:900; margin:15px 0;">${{item.title}}</h1>
                    <div style="color:#666; margin-bottom:30px; border-bottom:1px solid #000; padding-bottom:8px;">來源：${{item.source}}</div>
                    <div class="full-text-content">${{item.full_text}}</div>
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
    print("✅ 專業報紙級儀表板已生成：index.html")

if __name__ == "__main__":
    run_dashboard()
