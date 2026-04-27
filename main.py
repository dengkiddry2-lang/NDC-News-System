import pdfplumber
import os
import json
import re

# ── 1. 分類定義與核心邏輯 ──────────────────────────────────────────
# 核心原則：精簡分類，確保卡片呈現時具有一致的美感
DEPARTMENTS = {
    "社論評論": {"icon": "📝", "keywords": ["社論", "時評", "觀點", "專欄"]},
    "智庫報告": {"icon": "📘", "keywords": ["IMF", "OECD", "智庫", "BIS"]},
    "地緣政治": {"icon": "🌏", "keywords": ["戰爭", "衝突", "地緣", "關稅"]},
    "金融貨幣": {"icon": "🌐", "keywords": ["Fed", "利率", "通膨", "央行"]},
    "總體經濟": {"icon": "📊", "keywords": ["GDP", "景氣", "出口", "物價"]},
    "產業投資": {"icon": "🏭", "keywords": ["AI", "半導體", "台積", "供應鏈"]},
    "政府政策": {"icon": "🏛️", "keywords": ["國發會", "政院", "法案", "施政"]},
}

MUST_READ_KEYS = ["Fed", "FOMC", "鮑爾", "GDP", "景氣燈號", "衝突", "戰爭", "降息", "超徵"]

# ── 2. Apple 台灣官網視覺規範 (CSS) ────────────────────────────────

APPLE_CSS = """
:root {
    --bg: #f5f5f7;
    --panel: #ffffff;
    --text: #1d1d1f;
    --muted: #6e6e73;
    --link: #0066cc;
    --danger: #d70015;
    --border: rgba(0,0,0,.12);
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
    letter-spacing: -0.022em;
}

/* Apple 標準導航 - 毛玻璃特效 */
.global-nav {
    position: fixed;
    top: 0;
    width: 100%;
    height: 44px;
    z-index: 999;
    background: rgba(255,255,255,.78);
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 1px solid rgba(0,0,0,.08);
}

.nav-container {
    max-width: 1024px;
    height: 44px;
    margin: 0 auto;
    padding: 0 22px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: #333336;
}

.nav-links {
    display: flex;
    gap: 28px;
}

.nav-links span {
    cursor: default;
    opacity: .88;
}

/* 沉浸式 Hero 區 - 全白背景與大標 */
.hero {
    min-height: 520px;
    padding: 104px 22px 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    background: #fff;
}

.hero-kicker {
    font-size: 21px;
    font-weight: 600;
    color: var(--danger);
    margin-bottom: 12px;
}

.hero-headline {
    font-size: 64px;
    line-height: 1.05;
    font-weight: 700;
    margin: 0 0 14px;
}

.hero-subhead {
    font-size: 28px;
    line-height: 1.18;
    color: var(--text);
    margin-bottom: 18px;
}

.hero-date {
    font-size: 17px;
    color: var(--muted);
}

.main-wrapper {
    max-width: 1180px;
    margin: 0 auto;
    padding: 18px 12px 80px;
}

/* 類別導覽列 - Sticky 且具備模糊感 */
.category-nav {
    position: sticky;
    top: 44px;
    z-index: 20;
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding: 14px 10px;
    margin-bottom: 12px;
    background: rgba(245,245,247,.82);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
}

.category-nav::-webkit-scrollbar { display: none; }

.cat-link {
    flex: 0 0 auto;
    padding: 9px 16px;
    border-radius: 999px;
    background: #fff;
    border: 1px solid transparent;
    font-size: 14px;
    color: var(--text);
    cursor: pointer;
    transition: .2s ease;
}

.cat-link:hover { color: var(--link); }

.cat-link.active {
    border-color: var(--text);
    font-weight: 600;
}

/* 產品網格 - 雙欄式區塊 */
.news-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
}

.apple-card {
    min-height: 430px;
    border-radius: 28px;
    background: var(--panel);
    padding: 42px 36px;
    cursor: pointer;
    overflow: hidden;
    position: relative;
    transition: transform .35s ease, box-shadow .35s ease;
    display: flex;
    flex-direction: column;
}

.apple-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 18px 40px rgba(0,0,0,.08);
}

.apple-card.urgent {
    background: linear-gradient(180deg, #fff 0%, #fff2f2 100%);
}

.card-tag {
    min-height: 20px;
    font-size: 13px;
    font-weight: 700;
    color: var(--danger);
    margin-bottom: 10px;
}

.card-title {
    font-size: 36px;
    line-height: 1.08;
    font-weight: 700;
    margin-bottom: 14px;
}

.card-summary {
    font-size: 19px;
    line-height: 1.42;
    color: var(--muted);
    max-width: 92%;
}

.card-more {
    position: absolute;
    left: 36px;
    bottom: 34px;
    font-size: 17px;
    color: var(--link);
}

/* 彈窗樣式 - 沉浸式背景模糊 */
.modal {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(0,0,0,.42);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
}

.modal-inner {
    width: min(880px, calc(100% - 32px));
    max-height: 86vh;
    margin: 7vh auto;
    padding: 58px 64px;
    overflow-y: auto;
    background: #fff;
    border-radius: 30px;
    position: relative;
}

.close-btn {
    position: sticky;
    top: 0;
    float: right;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: none;
    background: #e8e8ed;
    color: #6e6e73;
    font-size: 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal-cat {
    color: var(--link);
    font-weight: 700;
    font-size: 15px;
    margin-bottom: 12px;
}

.modal-title {
    font-size: 46px;
    line-height: 1.08;
    font-weight: 700;
    margin: 0 0 28px;
}

.modal-body p {
    font-size: 19px;
    line-height: 1.72;
    color: #333336;
    margin: 0 0 1.35em;
    word-break: break-word;
}

.empty-state {
    grid-column: 1 / -1;
    text-align: center;
    padding: 80px 20px;
    color: var(--muted);
    font-size: 20px;
}

@media (max-width: 734px) {
    .nav-links { display: none; }
    .hero-headline { font-size: 44px; }
    .hero-subhead { font-size: 22px; }
    .news-grid { grid-template-columns: 1fr; }
    .apple-card { min-height: 340px; padding: 34px 28px; }
    .card-title { font-size: 30px; }
    .modal-inner { width: 100%; height: 100%; margin: 0; border-radius: 0; padding: 34px 26px; }
}
"""

# ── 3. 核心數據處理與生成函數 ───────────────────────────────────────

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    cats = list(DEPARTMENTS.keys())
    cat_html = ''.join([
        f'<button class="cat-link" onclick="renderNews(\'{c}\', this)">{c}</button>'
        for c in cats
    ])

    html_template = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>經濟規劃科 | Intelligence Hub</title>
    <style>{APPLE_CSS}</style>
</head>
<body>
    <nav class="global-nav">
        <div class="nav-container">
            <strong>Intelligence Hub</strong>
            <div class="nav-links">
                <span>總經</span><span>產業</span><span>政策</span><span>國際</span><span>社論</span>
            </div>
        </div>
    </nav>

    <header class="hero">
        <div>
            <div class="hero-kicker">EPC Newsroom</div>
            <h1 class="hero-headline">今日重點消息。</h1>
            <div class="hero-subhead">掌握總體經濟、產業動態與政策訊號。</div>
            <div class="hero-date" id="date-display"></div>
        </div>
    </header>

    <main class="main-wrapper">
        <nav class="category-nav">
            <button class="cat-link active" onclick="renderNews('all', this)">全部</button>
            {cat_html}
        </nav>
        <section class="news-grid" id="grid"></section>
    </main>

    <div id="modal" class="modal" onclick="closeModal()">
        <article class="modal-inner" onclick="event.stopPropagation()">
            <button class="close-btn" onclick="closeModal()">✕</button>
            <div id="modal-content"></div>
        </article>
    </div>

    <script>
        const news = {data_json};

        function escapeHtml(value) {{
            return String(value || '')
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#039;');
        }}

        function renderNews(cat, el) {{
            if (el) {{
                document.querySelectorAll('.cat-link').forEach(link => link.classList.remove('active'));
                el.classList.add('active');
            }}

            const grid = document.getElementById('grid');
            grid.innerHTML = '';

            const filtered = cat === 'all' ? news : news.filter(item => item.cat === cat);

            if (!filtered.length) {{
                grid.innerHTML = '<div class="empty-state">此分類目前沒有新聞。</div>';
                return;
            }}

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
            
            // 處理換行：針對雙換行切段
            const paragraphs = String(item.full_text || '')
                .replace(/\\\\r\\\\n/g, '\\\\n')
                .split(/\\\\n\\\\s*\\\\n/)
                .filter(p => p.trim().length > 0);

            const bodyHtml = paragraphs
                .map(p => `<p>${{escapeHtml(p.trim())}}</p>`)
                .join('');

            content.innerHTML = `
                <div class="modal-cat">${{escapeHtml(item.cat)}}</div>
                <h2 class="modal-title">${{escapeHtml(item.title)}}</h2>
                <div class="modal-body">${{bodyHtml || '<p>目前沒有全文內容。</p>'}}</div>
            `;

            document.getElementById('modal').style.display = 'block';
            document.body.style.overflow = 'hidden';
        }}

        function closeModal() {{
            document.getElementById('modal').style.display = 'none';
            document.body.style.overflow = 'auto';
        }}

        document.addEventListener('keydown', e => {{
            if (e.key === 'Escape') closeModal();
        }});

        document.getElementById('date-display').textContent =
            new Date().toLocaleDateString('zh-TW', {{
                year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
            }});

        renderNews('all');
    </script>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)

# ── 4. PDF 解析邏輯 (整合並優化) ──────────────────────────────────────

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
            raw_content_map[title_key] = lines[src_idx+1:]
            last_key = title_key
        elif last_key:
            raw_content_map[last_key].extend(lines)
            
    for key, text_list in raw_content_map.items():
        # 清洗與合併
        cleaned = " ".join([l for l in text_list if not (l.isdigit() or "回到目錄" in l)])
        # 嘗試簡單段落切分（在。之後加雙換行以便前端解析）
        formatted = cleaned.replace("。", "。\n\n")
        index[key] = formatted
    return index

def run_dashboard():
    data_folder = "data"
    if not os.path.exists(data_folder): os.makedirs(data_folder)
    pdf_files = [f for f in os.listdir(data_folder) if f.lower().endswith(".pdf")]

    all_items = []
    if pdf_files:
        latest_pdf = os.path.join(data_folder, sorted(pdf_files)[-1])
        with pdfplumber.open(latest_pdf) as pdf:
            article_index = build_article_index(pdf)
            for page in pdf.pages:
                table = page.extract_table()
                if not table: continue
                for row in table[1:]:
                    if not row or len(row) < 2 or not row[1]: continue
                    title = str(row[1]).replace("\n", "").strip()
                    if len(title) < 5: continue
                    
                    found_cat = "其他"
                    for cat, meta in DEPARTMENTS.items():
                        if any(k in title for k in meta["keywords"]):
                            found_cat = cat; break
                    
                    content = ""
                    clean_title = title.replace(" ", "")
                    for k, v in article_index.items():
                        if clean_title[:8] in k:
                            content = v; break
                    
                    all_items.append({
                        "title": title,
                        "cat": found_cat,
                        "priority": 1 if any(k in title for k in MUST_READ_KEYS) else 0,
                        "summary": content[:110] + "..." if content else "點擊了解更多細節。",
                        "full_text": content
                    })

    generate_html(all_items)
    print(f"✅ 已成功產出 Apple 風格看板，共計 {len(all_items)} 則消息。")

if __name__ == "__main__":
    run_dashboard()
