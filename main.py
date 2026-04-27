import pdfplumber
import os
import json

# ── 1. 分類與優先級定義 ──────────────────────────────────────────────
DEPARTMENTS = {
    "風險監控": {
        "icon": "⚠️",
        "label": "Risk Monitor",
        "keywords": ["美伊", "伊朗", "戰爭", "川普", "選情", "槍響", "Fed", "利率", "衝突", "地緣", "供應鏈"]
    },
    "總體數據": {
        "icon": "📊",
        "label": "Macro Data",
        "keywords": ["出口", "進口", "物價", "通膨", "匯率", "GDP", "主計", "景氣", "成長", "外銷"]
    },
    "產業動能": {
        "icon": "⚙️",
        "label": "Industry",
        "keywords": ["AI", "資本支出", "台積電", "半導體", "伺服器", "CoWoS", "設備", "製程", "先進封裝"]
    },
    "政策規畫": {
        "icon": "🏢",
        "label": "Policy",
        "keywords": ["國發會", "政策", "計畫", "電力", "預算", "離岸風電", "算力", "淨零", "綠能"]
    }
}

MUST_READ = [
    "Fed", "FOMC", "主計", "主計處", "GDP", "升息", "降息",
    "央行理監事", "利率決議", "通膨數據", "外銷訂單", "貿易統計",
    "戰爭", "地緣", "衝突", "制裁", "供應鏈斷鏈"
]

WATCH = [
    "出口", "進口", "資本支出", "AI", "台積電", "半導體",
    "景氣", "匯率", "油價", "通膨", "物價", "川普",
    "美伊", "離岸風電", "淨零", "算力"
]

def get_priority(title):
    if any(k in title for k in MUST_READ): return "must"
    if any(k in title for k in WATCH): return "watch"
    return "normal"

def get_lead(title, cat):
    if any(k in title for k in ["資本支出", "AI", "設備", "伺服器"]): return "投資動能支撐 GDP 成長預期"
    if any(k in title for k in ["出口", "訂單", "外銷"]): return "外需指標影響淨出口貢獻"
    if any(k in title for k in ["通膨", "油價", "物價"]): return "供給端壓力制約消費空間"
    if any(k in title for k in ["川普", "戰爭", "地緣"]): return "系統性風險需調高溢價"
    if any(k in title for k in ["Fed", "利率", "央行"]): return "貨幣路徑牽動資金流向"
    if any(k in title for k in ["政策", "國發會"]): return "政府支出結構影響投資預期"
    return "一般經濟資訊，建議持續觀察"

# ── 2. PDF 解析邏輯 (保留原邏輯但優化穩定性) ──────────────────────────────

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
            body = "\n".join(lines[src_idx + 1:])
            index[title_key] = body
            last_key = title_key
        elif len("".join(lines)) > 30 and last_key:
            index[last_key] += "\n" + "\n".join(lines)
        else:
            last_key = None
    return index

def find_article(index, toc_title):
    search_key = toc_title.replace(" ", "")[:10]
    for k, v in index.items():
        if search_key in k: return v
    return ""

def extract_summary(body):
    if not body: return ""
    for line in body.split("\n"):
        if len(line) >= 20 and any(c in line for c in "，。"): return line[:300]
    return body.split("\n")[0][:300] if body else ""

# ── 3. CSS 設計 (Apple Design Language) ─────────────────────────────────

CSS = """
:root {
    --sf-bg: #ffffff;
    --sf-card: #f5f5f7;
    --sf-text: #1d1d1f;
    --sf-text-secondary: #86868b;
    --sf-accent: #0071e3;
    --sf-must: #ff3b30;
    --sf-watch: #ff9500;
    --sf-radius: 20px;
    --sf-blur: blur(20px);
}

* { box-sizing: border-box; -webkit-font-smoothing: antialiased; }
body { 
    margin: 0; background-color: var(--sf-bg); color: var(--sf-text);
    font-family: "SF Pro Display", "SF Pro Icons", "Helvetica Neue", "Helvetica", "Arial", "Noto Sans TC", sans-serif;
    line-height: 1.47; letter-spacing: -0.022em;
}

/* Nav Bar */
.nav {
    position: sticky; top: 0; z-index: 1000;
    background: rgba(255, 255, 255, 0.8); backdrop-filter: var(--sf-blur);
    border-bottom: 1px solid rgba(0,0,0,0.1);
    height: 52px; display: flex; align-items: center; justify-content: center;
}
.nav-content { width: 100%; max-width: 1000px; display: flex; justify-content: space-between; padding: 0 22px; font-size: 12px; font-weight: 600; }

/* Hero Section */
.hero { padding: 80px 22px; text-align: center; max-width: 980px; margin: 0 auto; }
.hero-kicker { font-size: 21px; font-weight: 600; color: var(--sf-text); margin-bottom: 8px; }
.hero-title { font-size: 72px; font-weight: 700; letter-spacing: -0.05em; line-height: 1.05; margin-bottom: 20px; }
.hero-stats { display: flex; justify-content: center; gap: 40px; margin-top: 40px; }
.stat-item { display: flex; flex-direction: column; }
.stat-value { font-size: 40px; font-weight: 700; }
.stat-label { font-size: 14px; color: var(--sf-text-secondary); }

/* Tabs Control */
.tabs-container { position: sticky; top: 52px; z-index: 999; background: rgba(255,255,255,0.8); backdrop-filter: var(--sf-blur); padding: 12px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
.tabs { display: flex; justify-content: center; gap: 30px; }
.tab-btn { background: none; border: none; font-size: 14px; color: var(--sf-text-secondary); cursor: pointer; transition: color 0.3s; font-weight: 400; }
.tab-btn.active { color: var(--sf-text); font-weight: 600; }

/* Grid & Cards */
.main-content { max-width: 1000px; margin: 0 auto; padding: 40px 22px; }
.card { 
    background: var(--sf-card); border-radius: var(--sf-radius); 
    padding: 30px; margin-bottom: 20px; transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer; overflow: hidden; position: relative;
}
.card:hover { transform: scale(1.01); }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; }
.priority-tag { font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 999px; margin-bottom: 16px; display: inline-block; }
.tag-must { background: #ffebeb; color: var(--sf-must); }
.tag-watch { background: #fff4e5; color: var(--sf-watch); }
.tag-normal { background: #e8e8ed; color: var(--sf-text-secondary); }

.card-title { font-size: 28px; font-weight: 700; margin-bottom: 12px; max-width: 80%; }
.card-lead { font-size: 19px; color: var(--sf-text-secondary); margin-bottom: 20px; }
.card-footer { font-size: 12px; color: var(--sf-text-secondary); display: flex; gap: 10px; }

/* Expanded Content */
.expand-content { max-height: 0; opacity: 0; transition: all 0.5s ease; padding-top: 0; border-top: 0 solid rgba(0,0,0,0.05); margin-top: 0; }
.card.open .expand-content { max-height: 2000px; opacity: 1; padding-top: 24px; border-top-width: 1px; margin-top: 24px; }
.content-section { margin-bottom: 30px; }
.section-label { font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--sf-text-secondary); margin-bottom: 8px; }
.summary-text { font-size: 19px; line-height: 1.6; font-weight: 400; color: var(--sf-text); }

/* Animation */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
.card { animation: fadeInUp 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) both; }

@media (max-width: 734px) {
    .hero-title { font-size: 48px; }
    .card-title { font-size: 22px; }
}
"""

# ── 4. 主程式與 HTML 生成 ──────────────────────────────────────────────

def run_dashboard():
    if not os.path.exists("data"): os.makedirs("data")
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files: return
    
    pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join("data", x)))
    latest_pdf = os.path.join("data", pdf_files[-1])

    with pdfplumber.open(latest_pdf) as pdf:
        article_index = build_article_index(pdf)
        items_by_cat = {cat: [] for cat in DEPARTMENTS.keys()}
        
        for page in pdf.pages[:5]: # 通常目錄在前面
            table = page.extract_table()
            if not table: continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]: continue
                title = str(row[1]).replace("\n", "").strip()
                if len(title) < 5: continue
                
                found_cat = "總體數據"
                for cat, info in DEPARTMENTS.items():
                    if any(k in title for k in info["keywords"]):
                        found_cat = cat
                        break
                
                full_text = find_article(article_index, title)
                items_by_cat[found_cat].append({
                    "title": title,
                    "source": str(row[2]).replace("\n", " ") if len(row)>2 else "未知",
                    "priority": get_priority(title),
                    "lead": get_lead(title, found_cat),
                    "summary": extract_summary(full_text),
                    "full_text": full_text
                })

    # 生成 HTML
    data_json = json.dumps(items_by_cat, ensure_ascii=False)
    
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Economic Intelligence</title>
        <style>{CSS}</style>
    </head>
    <body>
        <nav class="nav">
            <div class="nav-content">
                <span>經濟規劃科 Intelligence</span>
                <span style="color:var(--sf-text-secondary)">Internal Only</span>
            </div>
        </nav>

        <header class="hero">
            <div class="hero-kicker" id="hero-date"></div>
            <h1 class="hero-title">今日經濟訊號</h1>
            <div class="hero-stats">
                <div class="stat-item"><span class="stat-value" id="count-must">0</span><span class="stat-label">必看</span></div>
                <div class="stat-item"><span class="stat-value" id="count-watch">0</span><span class="stat-label">關注</span></div>
                <div class="stat-item"><span class="stat-value" id="count-total">0</span><span class="stat-label">總計</span></div>
            </div>
        </header>

        <div class="tabs-container">
            <div class="tabs" id="tabs-bar">
                <button class="tab-btn active" onclick="switchTab('all')">全部</button>
            </div>
        </div>

        <main class="main-content" id="main-list"></main>

        <script>
            const DATA = {data_json};
            let currentCat = 'all';

            function init() {{
                const d = new Date();
                document.getElementById('hero-date').textContent = `民國 ${{d.getFullYear()-1911}} 年 ${{d.getMonth()+1}} 月 ${{d.getDate()}} 日`;
                
                const tabsBar = document.getElementById('tabs-bar');
                let total = 0, must = 0, watch = 0;

                Object.keys(DATA).forEach(cat => {{
                    const btn = document.createElement('button');
                    btn.className = 'tab-btn';
                    btn.textContent = cat;
                    btn.onclick = () => switchTab(cat);
                    tabsBar.appendChild(btn);
                    
                    DATA[cat].forEach(item => {{
                        total++;
                        if(item.priority === 'must') must++;
                        if(item.priority === 'watch') watch++;
                    }});
                }});

                document.getElementById('count-total').textContent = total;
                document.getElementById('count-must').textContent = must;
                document.getElementById('count-watch').textContent = watch;

                render();
            }}

            function switchTab(cat) {{
                currentCat = cat;
                document.querySelectorAll('.tab-btn').forEach(b => {{
                    b.classList.toggle('active', b.textContent === cat || (cat === 'all' && b.textContent === '全部'));
                }});
                render();
            }}

            function render() {{
                const container = document.getElementById('main-list');
                container.innerHTML = '';
                
                Object.keys(DATA).forEach(cat => {{
                    if (currentCat !== 'all' && currentCat !== cat) return;
                    
                    DATA[cat].forEach((item, idx) => {{
                        const card = document.createElement('div');
                        card.className = 'card';
                        card.style.animationDelay = `${{idx * 0.1}}s`;
                        
                        const prioLabel = item.priority === 'must' ? '必看' : (item.priority === 'watch' ? '關注' : '一般');
                        
                        card.innerHTML = `
                            <div class="card-header">
                                <span class="priority-tag tag-${{item.priority}}">${{prioLabel}}</span>
                            </div>
                            <h2 class="card-title">${{item.title}}</h2>
                            <p class="card-lead">${{item.lead}}</p>
                            <div class="card-footer">
                                <span>${{item.source}}</span>
                                <span>•</span>
                                <span>${{cat}}</span>
                            </div>
                            <div class="expand-content">
                                <div class="content-section">
                                    <div class="section-label">重點分析</div>
                                    <div class="summary-text">${{item.summary || '暫無摘要'}}</div>
                                </div>
                                <div class="content-section">
                                    <div class="section-label">新聞原文</div>
                                    <div class="summary-text" style="font-size:16px; color:#515154; white-space:pre-wrap;">${{item.full_text || '未擷取到全文'}}</div>
                                </div>
                            </div>
                        `;
                        
                        card.onclick = (e) => {{
                            card.classList.toggle('open');
                        }};
                        
                        container.appendChild(card);
                    }});
                }});
            }}

            init();
        </script>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ 已生成 Apple 風格儀表板：index.html")

if __name__ == "__main__":
    run_dashboard()
