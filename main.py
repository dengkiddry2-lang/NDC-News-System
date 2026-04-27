import pdfplumber
import os
import json
import re

# ── 1. 核心邏輯 (保持穩定) ──────────────────────────────────────────
DEPARTMENTS = {
    "社論觀點": {"icon": "📝", "keywords": ["社論", "時評", "專欄"]},
    "國際智庫": {"icon": "📘", "keywords": ["IMF", "OECD", "智庫"]},
    "地緣政治": {"icon": "🌏", "keywords": ["戰爭", "衝突", "俄烏"]},
    "金融政策": {"icon": "🌐", "keywords": ["Fed", "利率", "通膨"]},
    "台灣總體": {"icon": "📊", "keywords": ["GDP", "景氣", "出口"]},
    "產業投資": {"icon": "🏭", "keywords": ["AI", "半導體", "台積電"]},
    "政府政策": {"icon": "🏛️", "keywords": ["國發會", "政策", "法案"]},
}

# ── 2. Apple 風格 CSS ──────────────────────────────────────────────
# 重點：加入漸層背景、側邊欄、以及更細緻的卡片陰影
APPLE_STYLE_CSS = """
:root {
  --app-bg: #f5f5f7;
  --app-white: #ffffff;
  --app-gray: #86868b;
  --app-black: #1d1d1f;
  --app-blue: #0066cc;
  --app-blur: rgba(251, 251, 253, 0.72);
}

* { box-sizing: border-box; -webkit-font-smoothing: antialiased; }

body {
  font-family: "SF Pro Display", "SF Pro Text", "Helvetica Neue", "Noto Sans TC", sans-serif;
  background-color: var(--app-bg);
  color: var(--app-black);
  margin: 0; padding: 0;
  line-height: 1.5;
}

/* 頂部毛玻璃導航 */
.nav-glass {
  background: var(--app-blur);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  position: fixed; top: 0; width: 100%; height: 44px;
  z-index: 1000; border-bottom: 1px solid rgba(0,0,0,0.08);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 500;
}

/* Hero 沉浸區 */
.hero-section {
  padding: 120px 20px 60px;
  text-align: center;
  background: #fff;
}
.hero-tag { color: #f56300; font-size: 19px; font-weight: 600; margin-bottom: 10px; }
.hero-title { 
  font-size: 64px; font-weight: 700; letter-spacing: -0.015em; 
  background: linear-gradient(180deg, #1d1d1f 0%, #434344 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}

/* 佈局架構：側邊欄 + 主內容 */
.main-content {
  max-width: 1200px; margin: 40px auto;
  display: flex; gap: 40px; padding: 0 40px;
}

.sidebar {
  width: 240px; position: sticky; top: 80px; height: fit-content;
}
.sidebar-title { font-size: 12px; font-weight: 600; color: var(--app-gray); margin-bottom: 20px; }
.filter-item {
  padding: 12px 0; font-size: 14px; border-bottom: 1px solid rgba(0,0,0,0.05);
  cursor: pointer; transition: all 0.2s; display: flex; align-items: center;
}
.filter-item:hover { color: var(--app-blue); }
.filter-item.active { color: var(--app-blue); font-weight: 600; }

/* Apple 風格網格卡片 */
.grid-container { flex: 1; display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }

.news-card {
  background: var(--app-white);
  border-radius: 20px; padding: 30px;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  display: flex; flex-direction: column; cursor: pointer;
}
.news-card:hover { transform: scale(1.02); box-shadow: 0 15px 30px rgba(0,0,0,0.08); }
.news-card.must-read { border-left: 5px solid #d70015; }

.card-cat { font-size: 12px; color: var(--app-gray); font-weight: 600; margin-bottom: 12px; }
.card-title { font-size: 22px; font-weight: 700; margin-bottom: 15px; line-height: 1.2; }
.card-desc { font-size: 16px; color: var(--app-gray); line-height: 1.5; margin-bottom: 20px; }

/* 彈窗優化 */
.apple-modal {
  display:none; position:fixed; inset:0; z-index:9999;
  background: rgba(255,255,255,0.8); backdrop-filter: blur(20px);
  animation: fadeIn 0.3s ease;
}
.modal-body {
  max-width: 800px; margin: 100px auto; background: #fff;
  border-radius: 30px; padding: 60px; box-shadow: 0 40px 100px rgba(0,0,0,0.1);
  position: relative; max-height: 80vh; overflow-y: auto;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

@media (max-width: 900px) {
  .main-content { flex-direction: column; padding: 0 20px; }
  .grid-container { grid-template-columns: 1fr; }
  .hero-title { font-size: 40px; }
}
"""

def generate_html(data):
    # 這裡將資料與 HTML 模板結合
    data_json = json.dumps(data, ensure_ascii=False)
    cats = list(DEPARTMENTS.keys())
    
    html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>EPC Intelligence | National Development Council</title>
    <style>{APPLE_STYLE_CSS}</style>
</head>
<body>
    <div class="nav-glass">EPC Intelligence Hub</div>

    <header class="hero-section">
        <div class="hero-tag">國家發展委員會</div>
        <h1 class="hero-title">今日經濟情報。</h1>
        <p style="font-size:24px; color:#86868b;" id="today-text"></p>
    </header>

    <main class="main-content">
        <aside class="sidebar">
            <div class="sidebar-title">分類瀏覽</div>
            <div class="filter-item active" onclick="render('all', this)">全部消息</div>
            {" ".join([f'<div class="filter-item" onclick="render(\'{c}\', this)">{c}</div>' for c in cats])}
        </aside>

        <section class="grid-container" id="main-grid"></section>
    </main>

    <div id="modal" class="apple-modal" onclick="closeModal()">
        <div class="modal-body" onclick="event.stopPropagation()">
            <div id="modal-content"></div>
        </div>
    </div>

    <script>
        const newsData = {data_json};
        
        function render(filter, el) {{
            // 更新 UI 狀態
            document.querySelectorAll('.filter-item').forEach(i => i.classList.remove('active'));
            if(el) el.classList.add('active');

            const grid = document.getElementById('main-grid');
            grid.innerHTML = '';
            
            const filtered = filter === 'all' ? newsData : newsData.filter(d => d.cat === filter);
            
            filtered.forEach(item => {{
                const card = document.createElement('div');
                card.className = `news-card ${{item.priority ? 'must-read' : ''}}`;
                card.onclick = () => showDetail(item);
                card.innerHTML = `
                    <div class="card-cat">${{item.cat}}</div>
                    <div class="card-title">${{item.title}}</div>
                    <div class="card-desc">${{item.summary}}</div>
                    <div style="margin-top:auto; font-size:14px; font-weight:600; color:#0066cc;">深入閱讀 →</div>
                `;
                grid.appendChild(card);
            }});
        }}

        function showDetail(item) {{
            const modal = document.getElementById('modal');
            const content = document.getElementById('modal-content');
            content.innerHTML = `
                <div style="font-size:14px; color:#0066cc; font-weight:600; margin-bottom:10px;">${{item.cat}}</div>
                <h2 style="font-size:36px; margin-bottom:30px;">${{item.title}}</h2>
                <div style="font-size:18px; line-height:1.6; color:#1d1d1f;">
                    ${{item.full_text.split('\\n\\n').map(p => `<p>${{p}}</p>`).join('')}}
                </div>
            `;
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden';
        }}

        function closeModal() {{
            document.getElementById('modal').style.display = 'none';
            document.body.style.overflow = 'auto';
        }}

        document.getElementById('today-text').textContent = new Date().toLocaleDateString('zh-TW', {{ year:'numeric', month:'long', day:'numeric', weekday:'long' }});
        render('all');
    </script>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def run_dashboard():
    # 這裡與您原有的數據處理 logic 銜接
    # (省略部分重複的 PDF 解析 logic，確保執行時會產出 data 給 generate_html)
    # 範例數據測試
    test_data = [
        {"title": "聯準會維持利率不變，鮑爾釋放降息訊號", "cat": "金融政策", "priority": 1, "summary": "Fed 主席鮑爾在會後記者會表示...", "full_text": "內文第一段。\\n\\n內文第二段。"},
        {"title": "台積電先進封裝擴產，供應鏈全面啟動", "cat": "產業投資", "priority": 0, "summary": "隨著 AI 需求暴增，台積電決定...", "full_text": "內文內容。"}
    ]
    generate_html(test_data)
    print("Apple 風格網頁已重新設計完成。")

if __name__ == "__main__":
    run_dashboard()
