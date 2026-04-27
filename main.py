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

# ── 2. Apple 視覺規範 CSS ──────────────────────────────────────────

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
    font-size: 12px; color: #333336;
}

.hero {
    min-height: 520px;
    padding: 104px 22px 56px;
    display: flex; align-items: center; justify-content: center;
    text-align: center; background: #fff;
}

.hero-headline { font-size: 64px; line-height: 1.05; font-weight: 700; margin: 0 0 14px; }
.hero-subhead { font-size: 28px; line-height: 1.18; color: var(--text); margin-bottom: 18px; }
.hero-date { font-size: 17px; color: var(--muted); }

.category-nav {
    position: sticky; top: 44px; z-index: 20;
    display: flex; gap: 10px; overflow-x: auto;
    padding: 14px 10px; margin-bottom: 12px;
    background: rgba(245,245,247,.82);
    backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
}
.category-nav::-webkit-scrollbar { display: none; }

.cat-link {
    flex: 0 0 auto; padding: 9px 16px; border-radius: 999px;
    background: #fff; border: 1px solid transparent;
    font-size: 14px; color: var(--text); cursor: pointer; transition: .2s ease;
}
.cat-link.active { border-color: var(--text); font-weight: 600; }

.main-wrapper { max-width: 1180px; margin: 0 auto; padding: 18px 12px 80px; }
.news-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }

.apple-card {
    min-height: 430px; border-radius: 28px; background: var(--panel);
    padding: 42px 36px; cursor: pointer; position: relative;
    transition: transform .35s ease, box-shadow .35s ease;
}
.apple-card:hover { transform: translateY(-3px); box-shadow: 0 18px 40px rgba(0,0,0,.08); }
.apple-card.urgent { background: linear-gradient(180deg, #fff 0%, #fff2f2 100%); }

.card-tag { font-size: 13px; font-weight: 700; color: var(--danger); margin-bottom: 10px; min-height: 20px; }
.card-title { font-size: 32px; line-height: 1.15; font-weight: 700; margin-bottom: 14px; }
.card-summary { font-size: 19px; line-height: 1.42; color: var(--muted); }
.card-more { position: absolute; left: 36px; bottom: 34px; font-size: 17px; color: var(--link); }

.modal {
    display: none; position: fixed; inset: 0; z-index: 1000;
    background: rgba(0,0,0,.42); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
}
.modal-inner {
    width: min(880px, calc(100% - 32px)); max-height: 86vh;
    margin: 7vh auto; padding: 58px 64px; overflow-y: auto;
    background: #fff; border-radius: 30px; position: relative;
}
.close-btn {
    position: sticky; top: 0; float: right; width: 36px; height: 36px;
    border-radius: 50%; border: none; background: #e8e8ed; color: #6e6e73;
    font-size: 20px; cursor: pointer; display: flex; align-items: center; justify-content: center;
}
.modal-cat { color: var(--link); font-weight: 700; font-size: 15px; margin-bottom: 12px; }
.modal-title { font-size: 44px; line-height: 1.1; font-weight: 700; margin-bottom: 28px; }
.modal-body p { font-size: 19px; line-height: 1.72; color: #333336; margin-bottom: 1.35em; }

@media (max-width: 734px) {
    .hero-headline { font-size: 44px; }
    .news-grid { grid-template-columns: 1fr; }
    .modal-inner { width: 100%; height: 100%; margin: 0; border-radius: 0; padding: 34px 26px; }
}
"""

# ── 3. 數據解析邏輯 ──────────────────────────────────────────────

def clean_text(text_list):
    if not text_list: return ""
    # 合併並過濾雜訊
    raw = " ".join([l.strip() for l in text_list if not (l.isdigit() or "回到目錄" in l)])
    # 簡單標點符號分段處理
    paragraphs = raw.replace("。", "。\n\n").split("\n\n")
    return "\n\n".join([p.strip() for p in paragraphs if len(p.strip()) > 5])

def build_index(pdf):
    index = {}
    last_key = None
    raw_map = {}
    for page in pdf.pages:
        lines = (page.extract_text() or "").split("\n")
        has_src = any("來源:" in l or "來源：" in l for l in lines[:10])
        if has_src:
            src_idx = next(i for i, l in enumerate(lines) if "來源:" in l or "來源：" in l)
            title = "".join(lines[:src_idx]).replace(" ", "")
            raw_map[title] = lines[src_idx+1:]
            last_key = title
        elif last_key:
            raw_map[last_key].extend(lines)
    for k, v in raw_map.items():
        index[k] = clean_text(v)
    return index

# ── 4. HTML 生成 ───────────────────────────────────────────────────

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    cat_buttons = "".join([f'<button class="cat-link" onclick="renderNews(\'{c}\', this)">{c}</button>' for c in DEPARTMENTS.keys()])

    html_template = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Intelligence Hub</title>
    <style>{APPLE_CSS}</style>
</head>
<body>
    <nav class="global-nav">
        <div class="nav-container">
            <strong>Intelligence Hub</strong>
            <div style="display:flex;gap:20px"><span>總經</span><span>產業</span><span>政策</span></div>
        </div>
    </nav>

    <header class="hero">
        <div>
            <h1 class="hero-headline">今日重點消息。</h1>
            <div class="hero-subhead">掌握最新經濟趨勢與政策訊號。</div>
            <div class="hero-date" id="hero-date"></div>
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
            <button class="close-btn" onclick="closeModal()">✕</button>
            <div id="modal-content"></div>
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
            const paragraphs = String(item.full_text || '').split('\\n\\n').filter(p => p.trim());
            const bodyHtml = paragraphs.map(p => `<p>${{escapeHtml(p.trim())}}</p>`).join('');
            
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

        document.getElementById('hero-date').textContent = new Date().toLocaleDateString('zh-TW', {{ year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }});
        renderNews('all');
    </script>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)

# ── 5. 執行程序 ─────────────────────────────────────────────────────

def run():
    data_path = "data"
    if not os.path.exists(data_path): os.makedirs(data_path)
    pdfs = [f for f in os.listdir(data_path) if f.lower().endswith(".pdf")]
    
    all_items = []
    if pdfs:
        target = os.path.join(data_path, sorted(pdfs)[-1])
        with pdfplumber.open(target) as pdf:
            article_index = build_index(pdf)
            for page in pdf.pages:
                table = page.extract_table()
                if not table: continue
                for row in table[1:]:
                    if not row or len(row) < 2 or not row[1]: continue
                    
                    # 關鍵：這裡直接取表格中的原始標題，不進行加工
                    raw_title = str(row[1]).replace("\n", "").strip()
                    
                    # 分類判斷
                    cat = "其他"
                    for k, v in DEPARTMENTS.items():
                        if any(key in raw_title for key in v["keywords"]):
                            cat = k; break
                    
                    # 內文匹配（使用去空白標題作為索引）
                    content = article_index.get(raw_title.replace(" ", ""), "")
                    
                    all_items.append({
                        "title": raw_title, # 保留完整原始標題
                        "cat": cat,
                        "priority": 1 if any(k in raw_title for k in MUST_READ_KEYS) else 0,
                        "summary": content[:100] + "..." if content else "點擊查看詳情。",
                        "full_text": content
                    })

    generate_html(all_items)
    print("✅ 處理完成。")

if __name__ == "__main__":
    run()
