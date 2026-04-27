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

# ── 2. Apple iPad Air 產品頁視覺規範 CSS ──────────────────────────

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
    letter-spacing: -0.022em;
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

/* iPad Air 風格 Hero 區 */
.hero {
    min-height: 620px;
    padding: 120px 22px 70px;
    display: flex; align-items: center; justify-content: center;
    text-align: center;
    background: radial-gradient(circle at 50% 35%, #ffffff 0%, #f5f5f7 58%, #e8e8ed 100%);
}
.hero-kicker { font-size: 22px; font-weight: 600; color: #1d1d1f; margin-bottom: 12px; }
.hero-headline { font-size: 64px; line-height: 1.05; font-weight: 700; margin: 0; }
.hero-headline::after { content: "。"; }
.hero-subhead { font-size: 30px; font-weight: 600; color: #1d1d1f; margin-top: 15px; }
.hero-date { font-size: 17px; color: var(--muted); margin-top: 20px; }

/* iPad Air 風格分段標題 */
.section-title {
    max-width: 1180px;
    margin: 80px auto 32px;
    padding: 0 22px;
    font-size: 48px;
    line-height: 1.08;
    font-weight: 700;
    letter-spacing: -0.015em;
}

/* 橫向重點帶 */
.highlight-strip {
    display: flex;
    gap: 16px;
    overflow-x: auto;
    padding: 0 22px 40px;
    max-width: 1180px;
    margin: 0 auto;
}
.highlight-strip::-webkit-scrollbar { display: none; }

.highlight-card {
    flex: 0 0 360px;
    min-height: 260px;
    border-radius: 28px;
    background: #fff;
    padding: 36px;
    box-shadow: 0 10px 30px rgba(0,0,0,.04);
}
.highlight-card .num { font-size: 13px; font-weight: 700; color: #86868b; margin-bottom: 18px; text-transform: uppercase; }
.highlight-card .text { font-size: 26px; line-height: 1.18; font-weight: 700; color: #1d1d1f; }

/* 類別切換鈕 (Sticky) */
.category-nav {
    position: sticky; top: 44px; z-index: 20;
    display: flex; gap: 10px; overflow-x: auto;
    padding: 14px 22px; margin-bottom: 24px;
    background: rgba(245,245,247,.82);
    backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
}
.category-nav::-webkit-scrollbar { display: none; }
.cat-link {
    flex: 0 0 auto; padding: 10px 18px; border-radius: 999px;
    background: #fff; border: 1px solid transparent;
    font-size: 14px; cursor: pointer; transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.cat-link.active { border-color: var(--text); font-weight: 600; background: #fff; }

/* 主新聞網格 */
.main-wrapper { max-width: 1180px; margin: 0 auto; padding: 0 12px 100px; }
.news-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }

.apple-card {
    min-height: 420px; border-radius: 26px; background: #fff;
    padding: 42px; cursor: pointer; position: relative;
    transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.4s;
}
.apple-card:hover { transform: scale(1.015); box-shadow: 0 20px 45px rgba(0,0,0,0.08); }
.apple-card.urgent { background: linear-gradient(180deg, #fff 0%, #fff2f2 100%); }

.card-tag { font-size: 12px; font-weight: 700; color: var(--danger); margin-bottom: 10px; }
.card-title { font-size: 34px; font-weight: 700; line-height: 1.1; margin-bottom: 14px; }
.card-summary { font-size: 19px; color: var(--muted); line-height: 1.45; }
.card-more { position: absolute; left: 42px; bottom: 38px; color: var(--link); font-weight: 600; font-size: 17px; }

/* 彈窗優化 (閱讀體驗) */
.modal {
    display: none; position: fixed; inset: 0; z-index: 1000;
    background: rgba(0,0,0,.45); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
}
.modal-inner {
    width: min(840px, 95%); max-height: 85vh;
    margin: 7vh auto; background: #fff; border-radius: 30px; overflow: hidden;
    box-shadow: 0 30px 60px rgba(0,0,0,0.25); display: flex; flex-direction: column;
}
.modal-header-bar {
    padding: 24px 40px; border-bottom: 1px solid #f5f5f7;
    display: flex; justify-content: space-between; align-items: center;
}
.close-btn {
    width: 34px; height: 34px; border-radius: 50%; border: none;
    background: #f5f5f7; color: #000; font-size: 20px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
}
.modal-scroll-area { padding: 48px 64px 100px; overflow-y: auto; }
.modal-cat { color: var(--link); font-size: 15px; font-weight: 700; margin-bottom: 14px; text-transform: uppercase; }
.modal-title { font-size: 44px; font-weight: 700; line-height: 1.12; margin-bottom: 36px; color: #000; }
.modal-body p {
    font-size: 20px; line-height: 1.85; color: #333336;
    margin-bottom: 1.7em; text-align: justify;
}

@media (max-width: 734px) {
    .hero-headline { font-size: 42px; }
    .section-title { font-size: 32px; margin-top: 50px; }
    .highlight-card { flex: 0 0 300px; padding: 28px; }
    .news-grid { grid-template-columns: 1fr; }
    .modal-scroll-area { padding: 32px 28px; }
    .modal-title { font-size: 30px; }
}
"""

# ── 3. 數據解析與處理邏輯 ──────────────────────────────────────────

def clean_and_format_text(text_list):
    if not text_list: return ""
    full_text = " ".join([l.strip() for l in text_list if not (l.isdigit() or "回到目錄" in l)])
    # 精準段落切分
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
    <title>EPC News Dashboard</title>
    <style>{APPLE_CSS}</style>
</head>
<body>
    <nav class="global-nav">
        <div class="nav-container">
            <strong>Intelligence Hub</strong>
            <div style="display:flex; gap:24px; opacity:0.7; font-weight:500;">
                <span>重點</span><span>全覽</span><span>分類</span>
            </div>
        </div>
    </nav>

    <header class="hero">
        <div>
            <div class="hero-kicker">經濟規劃科新聞儀表板</div>
            <h1 class="hero-headline">今日重點消息</h1>
            <div class="hero-subhead">快讀、分類、判斷政策訊號。</div>
            <p id="current-date" class="hero-date"></p>
        </div>
    </header>

    <main>
        <h2 class="section-title">看這裡，畫重點。</h2>
        <section class="highlight-strip">
            <div class="highlight-card">
                <div class="num">重點 1</div>
                <div class="text">快速掌握今日總體經濟、產業與政策訊號。</div>
            </div>
            <div class="highlight-card">
                <div class="num">重點 2</div>
                <div class="text">將新聞依經濟規劃科業務需求重新分類。</div>
            </div>
            <div class="highlight-card">
                <div class="num">重點 3</div>
                <div class="text">點選卡片即可閱讀完整內容，避免頁面資訊過載。</div>
            </div>
        </section>

        <h2 class="section-title">經得起細細看。</h2>
        <div class="main-wrapper">
            <nav class="category-nav">
                <button class="cat-link active" onclick="renderNews('all', this)">全部消息</button>
                {cat_buttons}
            </nav>
            <div class="news-grid" id="grid"></div>
        </div>
    </main>

    <div id="modal" class="modal" onclick="closeModal()">
        <article class="modal-inner" onclick="event.stopPropagation()">
            <div class="modal-header-bar">
                <span style="font-size:11px; font-weight:800; color:#86868b; letter-spacing:0.1em;">REPORT READER</span>
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
            const paragraphs = String(item.full_text || '')
                .split('\\n\\n')
                .filter(p => p.trim().length > 10);

            const bodyHtml = paragraphs.map(p => `<p>${{escapeHtml(p.trim())}}</p>`).join('');

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
                        "summary": content[:120].split('。')[0] + "..." if content else "點擊查看深度分析。",
                        "full_text": content
                    })

    generate_html(items)
    print("✅ 已生成 iPad Air 風格的產品故事化新聞看板。")

if __name__ == "__main__":
    run()
