import pdfplumber
import os
import json
import re

# ── 1. 分類與核心定義 ──────────────────────────────────────────────
DEPARTMENTS = {
    "社論評論": {"icon": "📝", "keywords": ["社論", "時評", "觀點", "專欄"]},
    "智庫報告": {"icon": "📘", "keywords": ["IMF", "OECD", "智庫", "BIS"]},
    "地緣政治": {"icon": "🌏", "keywords": ["戰爭", "衝突", "地緣", "關稅"]},
    "金融貨幣": {"icon": "🌐", "keywords": ["Fed", "利率", "通膨", "央行"]},
    "總體經濟": {"icon": "📊", "keywords": ["GDP", "景氣", "出口", "物價"]},
    "產業動態": {"icon": "🏭", "keywords": ["AI", "半導體", "台積", "供應鏈"]},
    "政府政務": {"icon": "🏛️", "keywords": ["國發會", "政院", "法案", "政策"]},
}

MUST_READ_KEYS = ["Fed", "FOMC", "鮑爾", "GDP", "景氣燈號", "衝突", "戰爭", "降息", "超徵"]

# ── 2. Apple 視覺規範 CSS (加強內文層次) ──────────────────────────

APPLE_CSS = """
:root {
    --bg: #f5f5f7;
    --panel: #ffffff;
    --text: #1d1d1f;
    --muted: #6e6e73;
    --link: #0066cc;
    --danger: #d70015;
    --font: "SF Pro TC","SF Pro Display","SF Pro Text","PingFang TC","Helvetica Neue",Arial,sans-serif;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }

body {
    margin: 0;
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
}

/* Apple 標準導航 */
.global-nav {
    position: fixed;
    top: 0; width: 100%; height: 44px; z-index: 999;
    background: rgba(255,255,255,.78);
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 1px solid rgba(0,0,0,.08);
}

.nav-container {
    max-width: 1024px; height: 44px; margin: 0 auto;
    padding: 0 22px; display: flex; align-items: center; justify-content: space-between;
    font-size: 12px; font-weight: 600;
}

/* Hero 區 */
.hero {
    min-height: 480px; padding: 104px 22px 56px;
    display: flex; align-items: center; justify-content: center;
    text-align: center; background: #fff;
}
.hero-headline { font-size: 64px; font-weight: 700; margin: 0; letter-spacing: -0.015em; }
.hero-subhead { font-size: 24px; color: var(--muted); margin-top: 12px; }

/* 類別導覽列 */
.category-nav {
    position: sticky; top: 44px; z-index: 20;
    display: flex; gap: 10px; overflow-x: auto;
    padding: 14px 22px; margin-bottom: 24px;
    background: rgba(245,245,247,.82);
    backdrop-filter: blur(18px);
}
.category-nav::-webkit-scrollbar { display: none; }
.cat-link {
    flex: 0 0 auto; padding: 8px 16px; border-radius: 999px;
    background: #fff; border: 1px solid transparent;
    font-size: 14px; cursor: pointer; transition: 0.2s;
}
.cat-link.active { border-color: var(--text); font-weight: 600; }

/* 網格與卡片 */
.main-wrapper { max-width: 1180px; margin: 0 auto; padding: 0 12px 80px; }
.news-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }

.apple-card {
    min-height: 400px; border-radius: 24px; background: #fff;
    padding: 42px; cursor: pointer; position: relative;
    transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.4s;
}
.apple-card:hover { transform: scale(1.01); box-shadow: 0 20px 40px rgba(0,0,0,0.08); }
.apple-card.urgent { background: linear-gradient(180deg, #fff 0%, #fff2f2 100%); }

.card-tag { font-size: 12px; font-weight: 700; color: var(--danger); margin-bottom: 8px; }
.card-title { font-size: 32px; font-weight: 700; line-height: 1.1; margin-bottom: 12px; }
.card-summary { font-size: 18px; color: var(--muted); line-height: 1.4; }
.card-more { position: absolute; left: 42px; bottom: 36px; color: var(--link); font-weight: 500; }

/* 彈窗樣式 - 針對閱讀優化 */
.modal {
    display: none; position: fixed; inset: 0; z-index: 1000;
    background: rgba(0,0,0,.4); backdrop-filter: blur(12px);
}
.modal-inner {
    width: min(800px, 95%); max-height: 85vh;
    margin: 7vh auto; padding: 0;
    background: #fff; border-radius: 28px; overflow: hidden;
    box-shadow: 0 25px 50px rgba(0,0,0,0.2);
    display: flex; flex-direction: column;
}
.modal-header-bar {
    padding: 20px 40px; border-bottom: 1px solid #f2f2f2;
    display: flex; justify-content: space-between; align-items: center;
}
.close-btn {
    width: 32px; height: 32px; border-radius: 50%; border: none;
    background: #f5f5f7; color: #000; font-size: 18px; cursor: pointer;
}
.modal-scroll-area { padding: 40px 60px 80px; overflow-y: auto; }
.modal-cat { color: var(--link); font-size: 14px; font-weight: 600; text-transform: uppercase; margin-bottom: 12px; }
.modal-title { font-size: 40px; font-weight: 700; line-height: 1.15; margin-bottom: 32px; color: #000; }

/* 內文排版 */
.modal-body p {
    font-size: 19px; line-height: 1.8; color: #333336;
    margin-bottom: 1.6em; /* 段落間距 */
    text-align: justify;
}

@media (max-width: 734px) {
    .hero-headline { font-size: 40px; }
    .news-grid { grid-template-columns: 1fr; }
    .modal-scroll-area { padding: 30px 24px; }
    .modal-title { font-size: 28px; }
}
"""

# ── 3. 數據解析與處理 ──────────────────────────────────────────────

def clean_and_format_text(text_list):
    if not text_list: return ""
    # 合併文字並初步清理
    full_text = " ".join([l.strip() for l in text_list if not (l.isdigit() or "回到目錄" in l)])
    # 強制在句號、問號、感嘆號後加上換行標記，以便 JS 分段
    formatted = full_text.replace("。", "。\n\n").replace("？", "？\n\n").replace("！", "！\n\n")
    return formatted

def build_pdf_index(pdf):
    index = {}
    last_key = None
    raw_content = {}
    for page in pdf.pages:
        lines = (page.extract_text() or "").split("\n")
        has_source = any("來源:" in l or "來源：" in l for l in lines[:10])
        
        if has_source:
            src_idx = next(i for i, l in enumerate(lines) if "來源:" in l or "來源：" in l)
            title = "".join(lines[:src_idx]).replace(" ", "")
            raw_content[title] = lines[src_idx+1:]
            last_key = title
        elif last_key:
            raw_content[last_key].extend(lines)
            
    for k, v in raw_content.items():
        index[k] = clean_and_format_text(v)
    return index

# ── 4. HTML 生成 ───────────────────────────────────────────────────

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    cat_buttons = "".join([f'<button class="cat-link" onclick="renderNews(\'{c}\', this)">{c}</button>' for c in DEPARTMENTS.keys()])

    full_html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>Intelligence Hub</title>
    <style>{APPLE_CSS}</style>
</head>
<body>
    <nav class="global-nav">
        <div class="nav-container">
            <strong>Intelligence Hub</strong>
            <div style="display:flex; gap:24px; opacity:0.6"><span>報導</span><span>數據</span><span>分析</span></div>
        </div>
    </nav>

    <header class="hero">
        <div>
            <h1 class="hero-headline">今日重點消息。</h1>
            <p class="hero-subhead">精選全球趨勢，為您深度解碼。</p>
            <p id="current-date" style="color:#86868b; font-weight:500;"></p>
        </div>
    </header>

    <main class="main-wrapper">
        <nav class="category-nav">
            <button class="cat-link active" onclick="renderNews('all', this)">全部</button>
            {cat_buttons}
        </nav>
        <div class="news-grid" id="grid"></div>
    </main>

    <div id="modal" class="modal" onclick="closeModal()">
        <article class="modal-inner" onclick="event.stopPropagation()">
            <div class="modal-header-bar">
                <span style="font-size:12px; font-weight:700; opacity:0.4">READING MODE</span>
                <button class="close-btn" onclick="closeModal()">✕</button>
            </div>
            <div class="modal-scroll-area">
                <div id="modal-content"></div>
            </div>
        </article>
    </div>

    <script>
        const newsData = {data_json};

        function escapeHtml(s) {{
            return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        }}

        function renderNews(cat, el) {{
            if (el) {{
                document.querySelectorAll('.cat-link').forEach(l => l.classList.remove('active'));
                el.classList.add('active');
            }}
            const grid = document.getElementById('grid');
            grid.innerHTML = '';
            const filtered = cat === 'all' ? newsData : newsData.filter(n => n.cat === cat);

            filtered.forEach(item => {{
                const card = document.createElement('article');
                card.className = 'apple-card' + (item.priority ? ' urgent' : '');
                card.onclick = () => openModal(item);
                card.innerHTML = `
                    <div class="card-tag">${{item.priority ? '必讀重點' : '&nbsp;'}}</div>
                    <div class="card-title">${{escapeHtml(item.title)}}</div>
                    <div class="card-summary">${{escapeHtml(item.summary)}}</div>
                    <div class="card-more">進一步了解 ›</div>
                `;
                grid.appendChild(card);
            }});
        }}

        function openModal(item) {{
            const content = document.getElementById('modal-content');
            
            // 處理段落：根據雙換行切分，並包裝成 <p>
            const paragraphs = String(item.full_text || '')
                .split('\\n\\n')
                .filter(p => p.trim().length > 10); // 過濾過短的雜訊

            const bodyHtml = paragraphs
                .map(p => `<p>${{escapeHtml(p.trim())}}</p>`)
                .join('');

            content.innerHTML = `
                <div class="modal-cat">${{escapeHtml(item.cat)}}</div>
                <h1 class="modal-title">${{escapeHtml(item.title)}}</h1>
                <div class="modal-body">${{bodyHtml || '<p>目前沒有全文內容。</p>'}}</div>
            `;

            document.getElementById('modal').style.display = 'block';
            document.body.style.overflow = 'hidden';
        }}

        function closeModal() {{
            document.getElementById('modal').style.display = 'none';
            document.body.style.overflow = 'auto';
        }}

        document.getElementById('current-date').textContent = new Date().toLocaleDateString('zh-TW', {{ 
            year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' 
        }});
        
        renderNews('all');
    </script>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)

# ── 5. 執行程序 ─────────────────────────────────────────────────────

def run():
    # 確保資料夾存在
    if not os.path.exists("data"): os.makedirs("data")
    pdfs = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    
    items = []
    if pdfs:
        latest = os.path.join("data", sorted(pdfs)[-1])
        with pdfplumber.open(latest) as pdf:
            article_index = build_pdf_index(pdf)
            for page in pdf.pages:
                table = page.extract_table()
                if not table: continue
                for row in table[1:]:
                    if not row or not row[1]: continue
                    
                    raw_title = str(row[1]).replace("\n", "").strip()
                    
                    cat = "其他"
                    for k, v in DEPARTMENTS.items():
                        if any(key in raw_title for key in v["keywords"]):
                            cat = k; break
                    
                    content = article_index.get(raw_title.replace(" ", ""), "")
                    
                    items.append({
                        "title": raw_title,
                        "cat": cat,
                        "priority": 1 if any(k in raw_title for k in MUST_READ_KEYS) else 0,
                        "summary": content[:110].split('。')[0] + "..." if content else "點擊展開詳細內容。",
                        "full_text": content
                    })

    generate_html(items)
    print(f"✅ 生成完成！共處理 {len(items)} 則報導。")

if __name__ == "__main__":
    run()
