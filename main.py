import pdfplumber
import os
import json
import re

# ── 1. 分類定義 ──────────────────────────────────────────────
DEPARTMENTS = {
    "社論與評論觀點": {"icon": "📝", "keywords": ["社論", "時評", "社評", "專欄", "論壇", "觀點", "評論", "名家"]},
    "國際機構與智庫報告": {"icon": "📘", "keywords": ["IMF", "OECD", "World Bank", "WTO", "智庫", "BIS", "ADB"]},
    "地緣政治與國際衝突": {"icon": "🌏", "keywords": ["戰爭", "衝突", "制裁", "俄烏", "關稅", "川普", "貿易戰", "地緣"]},
    "國際金融與貨幣政策": {"icon": "🌐", "keywords": ["Fed", "FOMC", "聯準會", "升息", "降息", "美債", "CPI", "通膨", "匯率"]},
    "台灣總體經濟與數據": {"icon": "📊", "keywords": ["主計", "GDP", "景氣燈號", "景氣", "物價", "出口統計", "外銷訂單"]},
    "台灣產業與投資動向": {"icon": "🏭", "keywords": ["AI", "半導體", "台積電", "供應鏈", "伺服器", "晶片", "綠能"]},
    "台灣政府與政策訊息": {"icon": "🏛️", "keywords": ["國發會", "行政院", "總統府", "經濟部", "法案", "預算", "政策"]},
}

CATEGORY_ORDER = ["社論與評論觀點", "國際機構與智庫報告", "地緣政治與國際衝突", "國際金融與貨幣政策", "台灣總體經濟與數據", "台灣政府與政策訊息", "台灣產業與投資動向"]
MUST_READ_KEYS = ["Fed", "FOMC", "鮑爾", "GDP", "景氣燈號", "衝突", "戰爭"]

# ── 2. 文本解析與輔助邏輯 (保持原有邏輯) ─────────────────────────
def is_noise_line(line):
    noise = ["回到目錄", "來源:", "來源：", "版面", "作者", "日期", "頁次"]
    return line.isdigit() or any(k in line for k in noise)

def clean_text_blocks(text_list):
    if not text_list: return ""
    merged = ""
    for line in text_list:
        line = line.strip()
        if not line or is_noise_line(line): continue
        if re.search(r'報導】$|記者.{0,10}報導', line): continue
        merged += ("\n" + line) if merged and merged[-1] in ("。", "！", "？", "；") else line
    
    paragraphs = []
    sentences = re.split(r'(?<=[。！？；])', merged)
    current, count = "", 0
    for s in sentences:
        current += s.strip()
        count += 1
        if count >= 3:
            paragraphs.append(current)
            current, count = "", 0
    if current: paragraphs.append(current)
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
            raw_content_map[title_key] = lines[src_idx+1:]
            last_key = title_key
        elif last_key:
            raw_content_map[last_key].extend(lines)
    for key, text_list in raw_content_map.items():
        index[key] = clean_text_blocks(text_list)
    return index

# ── 3. HTML & Apple Style CSS 生成 ──────────────────────────────

APPLE_CSS = """
:root {
  --apple-bg: #f5f5f7;
  --apple-nav: rgba(251, 251, 253, 0.8);
  --apple-text: #1d1d1f;
  --apple-subtext: #86868b;
  --apple-blue: #0066cc;
  --apple-red: #d70015;
  --apple-card: #ffffff;
  --sf-font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Icons", "Helvetica Neue", "Helvetica", "Arial", "Noto Sans TC", sans-serif;
}

body {
  font-family: var(--sf-font);
  background-color: var(--apple-bg);
  color: var(--apple-text);
  margin: 0; padding: 0;
  -webkit-font-smoothing: antialiased;
  line-height: 1.47;
}

/* ── Global Nav (Apple Style) ── */
.global-nav {
  background: var(--apple-nav);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  position: fixed; top: 0; width: 100%; z-index: 9999;
  border-bottom: 1px solid rgba(0,0,0,0.1);
}
.nav-content {
  max-width: 1024px; margin: 0 auto;
  display: flex; justify-content: space-between; align-items: center;
  height: 48px; padding: 0 22px;
}
.nav-logo { font-weight: 600; font-size: 17px; letter-spacing: -0.01em; color: var(--apple-text); }
.nav-list { display: flex; gap: 30px; list-style: none; }
.nav-list span { font-size: 12px; color: var(--apple-subtext); cursor: pointer; transition: color 0.3s; }
.nav-list span:hover { color: var(--apple-blue); }

/* ── Hero Section ── */
.hero {
  padding-top: 120px; padding-bottom: 60px;
  text-align: center; background: #fff;
}
.hero h2 { font-size: 21px; font-weight: 600; margin: 0; }
.hero h1 { font-size: 56px; font-weight: 700; letter-spacing: -0.005em; margin: 10px 0; }
.hero .date { font-size: 21px; color: var(--apple-subtext); }

/* ── Grid Layout ── */
.container { max-width: 1000px; margin: 40px auto; padding: 0 20px; }
.section-title { font-size: 32px; font-weight: 700; margin-bottom: 24px; }

.news-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
  gap: 20px;
}

/* ── Apple Style Card ── */
.card {
  background: var(--apple-card);
  border-radius: 18px;
  padding: 30px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  transition: transform 0.5s cubic-bezier(0.4, 0, 0.25, 1), box-shadow 0.5s;
  cursor: pointer;
  display: flex; flex-direction: column;
  position: relative; overflow: hidden;
}
.card:hover { transform: scale(1.02); box-shadow: 0 20px 40px rgba(0,0,0,0.1); }
.card.must { border-top: 4px solid var(--apple-red); }

.card-cat { font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--apple-subtext); margin-bottom: 8px; }
.card-title { font-size: 24px; font-weight: 700; line-height: 1.1; margin-bottom: 12px; }
.card-summary { font-size: 17px; color: var(--apple-subtext); margin-bottom: 20px; flex-grow: 1; }
.card-footer { font-size: 12px; font-weight: 600; color: var(--apple-blue); }

/* ── Modal (Apple Style) ── */
.modal {
  display:none; position:fixed; inset:0; background: rgba(0,0,0,0.4); 
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  z-index: 10000; padding: 40px 20px; overflow-y: auto;
}
.modal-content {
  background: #fff; max-width: 800px; margin: 0 auto;
  border-radius: 30px; padding: 60px; position: relative;
  animation: modalUp 0.6s cubic-bezier(0.2, 1, 0.2, 1);
}
@keyframes modalUp { from { transform: translateY(100px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.modal-close { position: absolute; top: 30px; right: 30px; cursor: pointer; font-size: 24px; opacity: 0.5; }
.modal-cat { color: var(--apple-blue); font-weight: 600; margin-bottom: 10px; }
.modal-title { font-size: 40px; font-weight: 700; margin-bottom: 30px; line-height: 1.1; }
.article-text { font-size: 19px; line-height: 1.6; color: #333; text-align: justify; }
.article-text p { margin-bottom: 1.5em; }

@media (max-width: 734px) {
  .hero h1 { font-size: 40px; }
  .news-grid { grid-template-columns: 1fr; }
  .modal-content { padding: 30px; border-radius: 0; height: 100%; }
}
"""

def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    
    html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EPC Intelligence Hub</title>
    <style>{APPLE_CSS}</style>
</head>
<body>
    <nav class="global-nav">
        <div class="nav-content">
            <div class="nav-logo">Intelligence Hub</div>
            <div class="nav-list">
                <span onclick="renderGrid('all')">最新動態</span>
                <span onclick="renderGrid('社論與評論觀點')">觀點</span>
                <span onclick="renderGrid('國際金融與貨幣政策')">金融</span>
                <span onclick="renderGrid('台灣產業與投資動向')">產業</span>
            </div>
        </div>
    </nav>

    <section class="hero">
        <h2>EPC 每日情報彙整</h2>
        <h1>探索今日關鍵。</h1>
        <div class="date" id="hero-date"></div>
    </section>

    <div class="container">
        <div class="section-title" id="grid-title">最新</div>
        <div class="news-grid" id="news-grid"></div>
    </div>

    <div id="modal" class="modal" onclick="closeModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="modal-close" onclick="closeModal()">✕</span>
            <div id="modal-body"></div>
        </div>
    </div>

    <script>
        const DATA = {data_json};
        
        function init() {{
            document.getElementById('hero-date').textContent = new Date().toLocaleDateString('zh-TW', {{ year:'numeric', month:'long', day:'numeric' }});
            renderGrid('all');
        }}

        function renderGrid(filter) {{
            const grid = document.getElementById('news-grid');
            grid.innerHTML = '';
            document.getElementById('grid-title').textContent = filter === 'all' ? '最新' : filter;
            
            const filtered = filter === 'all' ? DATA : DATA.filter(item => item.cat === filter);
            
            filtered.forEach((item, idx) => {{
                const card = document.createElement('div');
                card.className = `card ${{item.priority ? 'must' : ''}}`;
                card.onclick = () => showFull(item);
                card.innerHTML = `
                    <div class="card-cat">${{item.cat}}</div>
                    <div class="card-title">${{item.title}}</div>
                    <div class="card-summary">${{item.summary}}</div>
                    <div class="card-footer">閱讀全文 →</div>
                `;
                grid.appendChild(card);
            }});
            window.scrollTo({{ top: 400, behavior: 'smooth' }});
        }}

        function showFull(item) {{
            const body = document.getElementById('modal-body');
            const contentHtml = item.full_text.split('\\n\\n').map(p => `<p>${{p}}</p>`).join('');
            body.innerHTML = `
                <div class="modal-cat">${{item.cat}}</div>
                <div class="modal-title">${{item.title}}</div>
                <div class="article-text">${{contentHtml || '尚未擷取到全文內容'}}</div>
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

def run_dashboard():
    # 這裡簡化了 PDF 處理邏輯，直接調用之前的結構
    data_folder = "data"
    if not os.path.exists(data_folder): os.makedirs(data_folder)
    pdf_files = [f for f in os.listdir(data_folder) if f.lower().endswith(".pdf")]
    
    all_items = []
    if pdf_files:
        latest_pdf = os.path.join(data_folder, sorted(pdf_files)[-1])
        with pdfplumber.open(latest_pdf) as pdf:
            article_index = build_article_index(pdf)
            # 獲取目錄數據 (假設在第一頁或特定頁面，這裡沿用您原本的表格掃描邏輯)
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    for row in table[1:]:
                        if not row or len(row) < 2 or not row[1]: continue
                        title = str(row[1]).replace("\n", "").strip()
                        if len(title) < 5: continue
                        
                        # 分類邏輯
                        found_cat = "其他"
                        for cat, meta in DEPARTMENTS.items():
                            if any(k in title for k in meta["keywords"]):
                                found_cat = cat; break
                        
                        full_text = ""
                        # 簡單匹配內文索引
                        for k, v in article_index.items():
                            if title[:8] in k:
                                full_text = v; break

                        all_items.append({
                            "title": title,
                            "cat": found_cat,
                            "priority": 1 if any(k in title for k in MUST_READ_KEYS) else 0,
                            "summary": full_text[:120] + "..." if full_text else "點擊查看詳情",
                            "full_text": full_text
                        })

    generate_html(all_items)
    print("✅ 已產生 Apple 風格 index.html")

if __name__ == "__main__":
    run_dashboard()
