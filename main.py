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
    if any(k in title for k in MUST_READ):
        return "must"
    if any(k in title for k in WATCH):
        return "watch"
    return "normal"

def get_lead(title, cat):
    if any(k in title for k in ["資本支出", "AI", "設備", "伺服器"]):
        return "民間投資（I）上行動能，支撐 GDP 成長"
    if any(k in title for k in ["出口", "訂單", "外銷"]):
        return "外需動能指標，影響淨出口（X-M）貢獻度"
    if any(k in title for k in ["通膨", "油價", "物價", "CPI"]):
        return "供給端成本壓力，制約民間消費（C）空間"
    if any(k in title for k in ["川普", "戰爭", "地緣", "衝突", "制裁"]):
        return "系統性風險訊號，需調高不確定性溢價"
    if any(k in title for k in ["Fed", "利率", "央行", "升息", "降息"]):
        return "貨幣政策路徑，影響台美利差與資金流向"
    if any(k in title for k in ["政策", "計畫", "預算", "國發會"]):
        return "政府支出（G）結構調整，牽動公共投資預期"
    if any(k in title for k in ["台積電", "半導體", "CoWoS", "封裝"]):
        return "供應鏈核心動向，影響出口與民間投資預測"
    if any(k in title for k in ["景氣", "GDP", "成長"]):
        return "總體景氣指標，影響整體成長預測校準"
    return "一般經濟資訊，建議持續觀察後續數據"


# ── 2. PDF 解析 ──────────────────────────────────────────────
#
# 通式判斷邏輯（不依賴固定字串）：
#   has_source → 內文首頁 (start)
#   has_table  → 目錄頁 (toc)
#   char < 30  → 分隔頁 (sep)，如「回到目錄」＋頁碼
#   其餘       → 內文續頁 (cont)，合併到前一篇

def build_article_index(pdf):
    results = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        has_source = any(l.startswith("來源:") for l in lines[:8])
        has_table = page.extract_table() is not None
        char_count = len("".join(lines))

        if has_source:
            cat = "start"
        elif has_table:
            cat = "toc"
        elif char_count < 30:
            cat = "sep"
        else:
            cat = "cont"
        results.append((cat, lines))

    index = {}
    last_key = None

    for cat, lines in results:
        if cat == "start":
            src_idx = next((j for j, l in enumerate(lines) if l.startswith("來源:")), None)
            if src_idx is None:
                last_key = None
                continue
            title_key = "".join(lines[:src_idx]).replace(" ", "")
            title_key = title_key.encode("utf-8", errors="replace").decode("utf-8")
            body_lines = [l for l in lines[src_idx + 1:] if not l.strip().isdigit()]
            body = "\n".join(body_lines).encode("utf-8", errors="replace").decode("utf-8")
            if title_key:
                index[title_key] = body
                last_key = title_key
        elif cat == "cont" and last_key:
            extra_lines = [l for l in lines if not l.strip().isdigit()]
            extra = "\n".join(extra_lines).encode("utf-8", errors="replace").decode("utf-8")
            if extra:
                index[last_key] = index[last_key] + "\n" + extra
        else:
            last_key = None

    return index


def find_article(index, toc_title):
    search_key = toc_title.replace(" ", "")[:10]
    for art_key, body in index.items():
        if search_key in art_key:
            return body
    return ""


def extract_summary(body, limit=280):
    if not body:
        return ""
    for line in body.split("\n"):
        line = line.strip()
        if len(line) >= 20 and ("，" in line or "。" in line or "、" in line):
            return line[:limit]
    first = body.split("\n")[0].strip()
    return first[:limit]


# ── 3. 主程式 ──────────────────────────────────────────────

def run_dashboard():
    if not os.path.exists("data"):
        os.makedirs("data")
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("data 資料夾內找不到 PDF")
        return

    pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join("data", x)))
    latest_pdf = os.path.join("data", pdf_files[-1])
    print(f"正在分析: {latest_pdf}")

    organized_data = {cat: {} for cat in DEPARTMENTS.keys()}
    organized_data["其他資訊"] = {}

    with pdfplumber.open(latest_pdf) as pdf:
        print("建立文章索引中...")
        article_index = build_article_index(pdf)
        print(f"找到 {len(article_index)} 篇內文頁")

        for page in pdf.pages[:10]:
            table = page.extract_table()
            if not table:
                continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]:
                    continue
                title = str(row[1]).replace("\n", "").strip()
                source = str(row[2]).replace("\n", " ").strip() if len(row) > 2 else "未知"
                if len(title) < 5 or "新聞議題" in title:
                    continue

                found_cat = "其他資訊"
                for cat, info in DEPARTMENTS.items():
                    if any(k in title for k in info["keywords"]):
                        found_cat = cat
                        break

                full_text = find_article(article_index, title)
                summary = extract_summary(full_text)
                priority = get_priority(title)
                lead = get_lead(title, found_cat)
                theme_key = title[:8]

                if theme_key not in organized_data[found_cat]:
                    organized_data[found_cat][theme_key] = {
                        "main_title": title,
                        "related_titles": [],
                        "sources": [source],
                        "full_text": full_text,
                        "summary": summary,
                        "priority": priority,
                        "lead": lead,
                    }
                else:
                    p_rank = {"must": 0, "watch": 1, "normal": 2}
                    existing = organized_data[found_cat][theme_key]
                    if p_rank[priority] < p_rank[existing["priority"]]:
                        existing["priority"] = priority
                    if title != existing["main_title"]:
                        existing["related_titles"].append({"title": title, "source": source})
                    if source not in existing["sources"]:
                        existing["sources"].append(source)

    generate_html(organized_data)
    print("✅ 已產生 index.html")


# ── 4. HTML 產生 ──────────────────────────────────────────────
# JS 部分完全用 Python 字串產生，不放進 f-string，避免換行問題

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #fafaf9;
  --white: #ffffff;
  --border: rgba(0,0,0,0.08);
  --border-md: rgba(0,0,0,0.13);
  --text-p: #111110;
  --text-s: #6b6966;
  --text-m: #a8a5a2;
  --accent: #1a56db;

  --must-left: #dc2626;
  --must-bg: #fff5f5;
  --must-tag-bg: #fee2e2;
  --must-tag-text: #991b1b;

  --watch-left: #d97706;
  --watch-bg: #fffbf0;
  --watch-tag-bg: #fef3c7;
  --watch-tag-text: #92400e;

  --radius-sm: 6px;
  --radius: 10px;
}

body {
  background: var(--bg);
  color: var(--text-p);
  font-family: 'Noto Sans TC', -apple-system, BlinkMacSystemFont, sans-serif;
  min-height: 100vh;
  font-size: 14px;
  line-height: 1.6;
}

.header {
  background: var(--white);
  border-bottom: 1px solid var(--border);
  padding: 0 48px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-brand { display: flex; align-items: baseline; gap: 12px; }
.header-title {
  font-family: 'Noto Serif TC', serif;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.03em;
}
.header-sub { font-size: 11px; color: var(--text-m); letter-spacing: 0.06em; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.header-date { font-size: 13px; color: var(--text-s); margin-right: 8px; }

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--border-md);
  transition: background 0.12s, color 0.12s;
  white-space: nowrap;
}
.btn-primary { background: var(--text-p); color: #fff; border-color: var(--text-p); }
.btn-primary:hover { background: #2a2927; }
.btn-primary.success { background: #16a34a; border-color: #16a34a; }
.btn-ghost { background: transparent; color: var(--text-s); }
.btn-ghost:hover { background: var(--bg); color: var(--text-p); }

.main { padding: 32px 48px 64px; max-width: 900px; margin: 0 auto; }

.legend { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; font-size: 12px; color: var(--text-m); }
.leg { display: flex; align-items: center; gap: 5px; }
.leg-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.leg-dot.must { background: var(--must-left); }
.leg-dot.watch { background: var(--watch-left); }
.leg-dot.normal { background: #d1d5db; }

.tabs { display: flex; gap: 2px; margin-bottom: 24px; border-bottom: 1.5px solid var(--border); }
.tab-btn {
  padding: 10px 18px;
  border: none;
  background: transparent;
  font-size: 13px;
  font-family: inherit;
  font-weight: 500;
  color: var(--text-m);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1.5px;
  transition: color 0.12s, border-color 0.12s;
  white-space: nowrap;
}
.tab-btn:hover { color: var(--text-p); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

.news-list { display: flex; flex-direction: column; gap: 6px; }

.news-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-left: 3px solid transparent;
  border-radius: var(--radius);
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.news-card:hover { border-color: var(--border-md); box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.news-card.priority-must { border-left-color: var(--must-left); background: var(--must-bg); }
.news-card.priority-watch { border-left-color: var(--watch-left); background: var(--watch-bg); }

.card-top {
  padding: 16px 20px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  cursor: pointer;
  user-select: none;
}
.card-top:hover .card-title { color: var(--accent); }

.prio-col { flex-shrink: 0; padding-top: 1px; }
.prio-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
  text-transform: uppercase;
}
.prio-badge.must { background: var(--must-tag-bg); color: var(--must-tag-text); }
.prio-badge.watch { background: var(--watch-tag-bg); color: var(--watch-tag-text); }
.prio-badge.normal { background: transparent; color: var(--text-m); border: 1px solid var(--border-md); font-weight: 500; }

.card-info { flex: 1; min-width: 0; }
.card-title {
  font-family: 'Noto Serif TC', serif;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.55;
  color: var(--text-p);
  margin-bottom: 5px;
  transition: color 0.12s;
}
.card-lead { font-size: 12px; color: var(--text-s); margin-bottom: 8px; }
.card-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; }
.src-tag { font-size: 11px; color: var(--text-m); background: rgba(0,0,0,0.04); padding: 2px 8px; border-radius: 4px; }
.related-badge { font-size: 11px; color: var(--text-m); }

.toggle-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-m);
  font-size: 14px;
  transition: transform 0.22s ease, color 0.15s;
  margin-top: 1px;
}
.news-card.open .toggle-icon { transform: rotate(90deg); color: var(--accent); }

.card-expand { display: none; border-top: 1px solid var(--border); }
.news-card.open .card-expand { display: block; }

.inner-tabs { display: flex; background: var(--bg); border-bottom: 1px solid var(--border); padding: 0 20px; }
.inner-tab {
  padding: 8px 14px;
  border: none;
  background: transparent;
  font-size: 12px;
  font-family: inherit;
  font-weight: 500;
  color: var(--text-m);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.12s, border-color 0.12s;
}
.inner-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.inner-tab:hover:not(.active) { color: var(--text-p); }

.inner-panel { display: none; padding: 20px; }
.inner-panel.active { display: block; animation: panelIn 0.16s ease; }
@keyframes panelIn { from{opacity:0;transform:translateY(-4px)} to{opacity:1;transform:translateY(0)} }

.summary-block {
  font-size: 14px;
  color: var(--text-s);
  line-height: 1.9;
  font-family: 'Noto Serif TC', serif;
  border-left: 2px solid var(--accent);
  padding-left: 16px;
  outline: none;
  white-space: pre-wrap;
}
.summary-block:focus { background: #fffef9; border-radius: 0 6px 6px 0; }
.summary-empty { font-size: 13px; color: var(--text-m); font-style: italic; padding: 14px 16px; background: var(--bg); border-radius: var(--radius-sm); border: 1px dashed var(--border-md); }

.fulltext-body { font-size: 13.5px; color: var(--text-s); line-height: 1.95; font-family: 'Noto Serif TC', serif; white-space: pre-wrap; outline: none; }
.fulltext-body:focus { background: #fffef9; padding: 4px 6px; margin: -4px -6px; border-radius: var(--radius-sm); }
.fulltext-paste { width: 100%; min-height: 120px; padding: 12px 14px; border: 1px dashed var(--border-md); border-radius: var(--radius-sm); font-family: 'Noto Serif TC', serif; font-size: 13.5px; color: var(--text-s); background: var(--bg); resize: vertical; outline: none; line-height: 1.9; transition: border-color 0.12s, background 0.12s; }
.fulltext-paste:focus { border-color: var(--accent); background: var(--white); }
.fulltext-hint { font-size: 12px; color: var(--text-m); margin-bottom: 10px; }

.related-row { display: flex; align-items: flex-start; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--border); font-size: 13px; color: var(--text-s); }
.related-row:last-child { border-bottom: none; }
.related-bullet { color: var(--text-m); flex-shrink: 0; margin-top: 1px; font-size: 10px; }
.related-src { font-size: 11px; color: var(--text-m); flex-shrink: 0; margin-left: auto; }

.empty-state { text-align: center; padding: 64px 20px; color: var(--text-m); font-size: 14px; }

@media print {
  .header{position:static;}
  .btn,.tabs,.inner-tabs,.fulltext-paste,.fulltext-hint{display:none!important}
  .news-card{break-inside:avoid;border-left-width:3px}
  .card-expand{display:block!important}
  .inner-panel{display:block!important;padding:12px 20px}
  .inner-panel+.inner-panel{border-top:1px solid var(--border)}
}
@media(max-width:640px){
  .header{padding:0 20px} .main{padding:20px 16px 48px}
  .header-sub,.header-date{display:none}
}
"""


def build_js(data_json, sep_double, sep_single):
    # 完全用 Python 字串建構 JS，不用 f-string，避免換行問題
    lines = [
        "const DATA = " + data_json + ";",
        "const CATS = Object.keys(DATA);",
        "let currentTab = 'all';",
        "const pasteStore = {};",
        "const PRIO_LABEL = {must:'必看',watch:'關注',normal:'一般'};",
        "",
        "function renderTabs(){",
        "  const el=document.getElementById('tabs');",
        "  el.innerHTML='';",
        "  el.appendChild(mkTab('全部','all',true));",
        "  CATS.forEach(cat=>{",
        "    const d=DATA[cat];",
        "    const mustN=d.items.filter(i=>i.priority==='must').length;",
        "    const label=d.icon+' '+cat+(mustN?' \u2691'+mustN:'');",
        "    el.appendChild(mkTab(label,cat,false));",
        "  });",
        "}",
        "function mkTab(label,id,active){",
        "  const b=document.createElement('button');",
        "  b.className='tab-btn'+(active?' active':'');",
        "  b.dataset.id=id;",
        "  b.textContent=label;",
        "  b.onclick=()=>switchTab(id);",
        "  return b;",
        "}",
        "function switchTab(id){",
        "  currentTab=id;",
        "  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',b.dataset.id===id));",
        "  renderList();",
        "}",
        "function renderList(){",
        "  const list=document.getElementById('news-list');",
        "  list.innerHTML='';",
        "  const targets=currentTab==='all'?CATS:[currentTab];",
        "  let n=0;",
        "  targets.forEach(cat=>DATA[cat].items.forEach(item=>{list.appendChild(makeCard(item,cat));n++;}));",
        "  if(!n){const e=document.createElement('div');e.className='empty-state';e.textContent='\u76ee\u524d\u7121\u76f8\u95dc\u65b0\u8a0a\u8cc7\u6599';list.appendChild(e);}",
        "}",
        "function makeCard(item,cat){",
        "  const card=document.createElement('div');",
        "  card.className='news-card priority-'+item.priority;",
        "  const srcHtml=item.sources.map(s=>'<span class=\"src-tag\">'+s+'</span>').join('');",
        "  const relN=item.related_count||0;",
        "  card.innerHTML=",
        "    '<div class=\"card-top\">'+",
        "      '<div class=\"prio-col\"><span class=\"prio-badge '+item.priority+'\">'+PRIO_LABEL[item.priority]+'</span></div>'+",
        "      '<div class=\"card-info\">'+",
        "        '<div class=\"card-title\">'+item.main_title+'</div>'+",
        "        '<div class=\"card-lead\">\u2192 '+item.lead+'</div>'+",
        "        '<div class=\"card-meta\">'+srcHtml+(relN?'<span class=\"related-badge\">\uff0b'+relN+' \u5247\u76f8\u95dc</span>':'')+'</div>'+",
        "      '</div>'+",
        "      '<span class=\"toggle-icon\">\u203a</span>'+",
        "    '</div>'+",
        "    '<div class=\"card-expand\"></div>';",
        "  card.querySelector('.card-top').addEventListener('click',()=>{",
        "    const isOpen=card.classList.contains('open');",
        "    if(!isOpen)buildExpand(card,item);",
        "    card.classList.toggle('open');",
        "  });",
        "  return card;",
        "}",
        "function buildExpand(card,item){",
        "  const expand=card.querySelector('.card-expand');",
        "  if(expand.dataset.ready)return;",
        "  expand.dataset.ready='1';",
        "  const tabBar=document.createElement('div');",
        "  tabBar.className='inner-tabs';",
        "  expand.appendChild(tabBar);",
        "  const panels=[];",
        "  function addInnerTab(label,active){",
        "    const t=document.createElement('button');",
        "    t.className='inner-tab'+(active?' active':'');",
        "    t.textContent=label;",
        "    const idx=panels.length;",
        "    t.onclick=()=>{",
        "      tabBar.querySelectorAll('.inner-tab').forEach((x,i)=>x.classList.toggle('active',i===idx));",
        "      panels.forEach((p,i)=>p.classList.toggle('active',i===idx));",
        "    };",
        "    tabBar.appendChild(t);",
        "    const p=document.createElement('div');",
        "    p.className='inner-panel'+(active?' active':'');",
        "    expand.appendChild(p);",
        "    panels.push(p);",
        "    return p;",
        "  }",
        "  const p1=addInnerTab('\u65b0\u8a0a\u91cd\u9ede',true);",
        "  if(item.summary){",
        "    const div=document.createElement('div');",
        "    div.className='summary-block';",
        "    div.contentEditable='true';",
        "    div.textContent=item.summary;",
        "    p1.appendChild(div);",
        "  }else{",
        "    p1.innerHTML='<div class=\"summary-empty\">\u26a0\ufe0f \u81ea\u52d5\u6293\u53d6\u5931\u6557\uff0c\u8acb\u5207\u63db\u81f3\u300c\u65b0\u8a0a\u5168\u6587\u300d\u624b\u52d5\u8cbc\u5165</div>';",
        "  }",
        "  const p2=addInnerTab('\u65b0\u8a0a\u5168\u6587',false);",
        "  const storeKey=item.main_title;",
        "  if(item.full_text){",
        "    const div=document.createElement('div');",
        "    div.className='fulltext-body';",
        "    div.contentEditable='true';",
        "    div.textContent=item.full_text;",
        "    div.addEventListener('input',e=>{pasteStore[storeKey]=e.target.innerText;});",
        "    p2.appendChild(div);",
        "  }else{",
        "    const saved=pasteStore[storeKey]||'';",
        "    p2.innerHTML='<div class=\"fulltext-hint\">\ud83d\udccb \u672a\u80fd\u81ea\u52d5\u64f7\u53d6\uff0c\u8acb\u624b\u52d5\u8cbc\u5165\uff1a</div>'+'<textarea class=\"fulltext-paste\">'+saved+'</textarea>';",
        "    p2.querySelector('textarea').addEventListener('input',e=>{pasteStore[storeKey]=e.target.value;});",
        "  }",
        "  if(item.related_titles&&item.related_titles.length>0){",
        "    const p3=addInnerTab('\u76f8\u95dc\u5831\u5c0e ('+item.related_titles.length+')',false);",
        "    item.related_titles.forEach(r=>{",
        "      const row=document.createElement('div');",
        "      row.className='related-row';",
        "      const t=typeof r==='object'?r.title:r;",
        "      const s=typeof r==='object'?r.source:'';",
        "      row.innerHTML='<span class=\"related-bullet\">\u25b8</span><span style=\"flex:1\">'+t+'</span>'+(s?'<span class=\"related-src\">'+s+'</span>':'');",
        "      p3.appendChild(row);",
        "    });",
        "  }",
        "}",
        "document.getElementById('btn-copy').addEventListener('click',()=>{",
        "  const now=new Date();",
        "  const roc=now.getFullYear()-1911;",
        "  const mm=String(now.getMonth()+1).padStart(2,'0');",
        "  const dd=String(now.getDate()).padStart(2,'0');",
        "  const dateStr=roc+'.'+mm+'.'+dd;",
        "  let text='\u3010'+dateStr+' \u7d93\u6fdf\u898f\u5283\u79d1 \u30b7 \u6bcf\u65e5\u65b0\u8a0a\u91cd\u9ede\u3011\\n'+'"+sep_double+"'+'\\n\\n';",
        "  const targets=currentTab==='all'?CATS:[currentTab];",
        "  targets.forEach(cat=>{",
        "    const d=DATA[cat];",
        "    text+=d.icon+' '+cat+'\\n'+'"+sep_single+"'+'\\n';",
        "    d.items.forEach(item=>{",
        "      text+='\u258c ['+PRIO_LABEL[item.priority]+'] '+item.main_title+'\\n';",
        "      text+='   \u4f86\u6e90\uff1a'+item.sources.join('\u3001')+'\\n';",
        "      text+='   \u2192 '+item.lead+'\\n';",
        "      if(item.summary)text+='   \u91cd\u9ede\uff1a'+item.summary+'\\n';",
        "      if(item.related_titles&&item.related_titles.length>0){",
        "        const rel=item.related_titles.map(r=>typeof r==='object'?r.title:r);",
        "        text+='   \u76f8\u95dc\uff1a'+rel.join('\uff1b')+'\\n';",
        "      }",
        "      text+='\\n';",
        "    });",
        "    text+='\\n';",
        "  });",
        "  navigator.clipboard.writeText(text).then(()=>{",
        "    const btn=document.getElementById('btn-copy');",
        "    btn.classList.add('success');",
        "    btn.innerHTML='\u2713 \u5df2\u8907\u88fd';",
        "    setTimeout(()=>{btn.classList.remove('success');btn.innerHTML='\ud83d\udccb \u8907\u88fd\u4eca\u65e5\u6458\u8981';},2000);",
        "  });",
        "});",
        "const now=new Date();",
        "const roc=now.getFullYear()-1911;",
        "document.getElementById('date-label').textContent='\u6c11\u570b '+roc+' \u5e74 '+(now.getMonth()+1)+' \u6708 '+now.getDate()+' \u65e5';",
        "renderTabs();",
        "renderList();",
    ]
    return "\n".join(lines)


def generate_html(data):
    js_data = {}
    p_rank = {"must": 0, "watch": 1, "normal": 2}
    for cat, items in data.items():
        if cat == "其他資訊":
            continue
        dept = DEPARTMENTS[cat]
        item_list = sorted(items.values(), key=lambda x: p_rank[x["priority"]])
        for item in item_list:
            item["related_count"] = len(item["related_titles"])
        js_data[cat] = {
            "icon": dept["icon"],
            "label": dept["label"],
            "items": item_list
        }

    data_json = json.dumps(js_data, ensure_ascii=False).replace("</", "<\\/")
    sep_double = "\u2550" * 36
    sep_single = "\u2500" * 30
    js_code = build_js(data_json, sep_double, sep_single)

    html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-TW">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>\u570b\u767c\u6703\u7d93\u6fdf\u898f\u5283\u79d1 \u00b7 \u6bcf\u65e5\u65b0\u8a0a\u91cd\u9ede</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;600;700&family=Noto+Sans+TC:wght@300;400;500&display=swap" rel="stylesheet">\n'
        '<style>\n' + CSS + '\n</style>\n'
        '</head>\n'
        '<body>\n'
        '<header class="header">\n'
        '  <div class="header-brand">\n'
        '    <span class="header-title">\u570b\u5bb6\u767c\u5c55\u59d4\u54e1\u6703 \u00b7 \u7d93\u6fdf\u898f\u5283\u79d1</span>\n'
        '    <span class="header-sub">\u6bcf\u65e5\u65b0\u8a0a\u91cd\u9ede\u6574\u7406 \u00b7 INTERNAL USE ONLY</span>\n'
        '  </div>\n'
        '  <div class="header-actions">\n'
        '    <span class="header-date" id="date-label"></span>\n'
        '    <button class="btn btn-ghost" onclick="window.print()">\ud83d\udda8 \u5217\u5370\uff0fPDF</button>\n'
        '    <button class="btn btn-primary" id="btn-copy">\ud83d\udccb \u8907\u88fd\u4eca\u65e5\u6458\u8981</button>\n'
        '  </div>\n'
        '</header>\n'
        '<main class="main">\n'
        '  <div class="legend">\n'
        '    <span>\u512a\u5148\u7d1a\uff1a</span>\n'
        '    <div class="leg"><span class="leg-dot must"></span>\u5fc5\u770b</div>\n'
        '    <div class="leg"><span class="leg-dot watch"></span>\u95dc\u6ce8</div>\n'
        '    <div class="leg"><span class="leg-dot normal"></span>\u4e00\u822c</div>\n'
        '  </div>\n'
        '  <div class="tabs" id="tabs"></div>\n'
        '  <div class="news-list" id="news-list"></div>\n'
        '</main>\n'
        '<script>\n' + js_code + '\n</script>\n'
        '</body>\n'
        '</html>\n'
    )

    with open("index.html", "w", encoding="utf-8", errors="replace") as f:
        f.write(html)


if __name__ == "__main__":
    run_dashboard()
