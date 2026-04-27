import pdfplumber
import os
import json
import re

# ── 1. 分類定義（修正版）──────────────────────────────────────────────
# 核心原則：
#   - 不用「美國/中國/日本」等國名當關鍵字（幾乎每篇都有）
#   - 地緣政治獨立一類，不混入金融情勢
#   - 台積/聯電等縮寫補進產業類
#   - 政府政策類補強機構名

DEPARTMENTS = {
    "社論與評論觀點": {
        "icon": "📝",
        "keywords": ["社論", "時評", "社評", "專欄", "論壇", "觀點", "評論", "名家", "經濟教室", "縱橫天下", "自由廣場"]
    },
    "國際機構與智庫報告": {
        "icon": "📘",
        "keywords": ["IMF", "OECD", "World Bank", "WTO", "智庫", "Brookings", "PIIE", "BIS", "ADB", "WEF", "聯合國", "世界銀行", "國際貨幣"]
    },
    "地緣政治與國際衝突": {
        "icon": "🌏",
        "keywords": [
            "戰爭", "衝突", "制裁", "美伊", "俄烏", "荷莫茲", "伊朗", "烏克蘭",
            "關稅", "川普", "貿易戰", "地緣", "槍響", "槍擊", "遇襲", "外交"
        ]
    },
    "國際金融與貨幣政策": {
        "icon": "🌐",
        "keywords": [
            "Fed", "FOMC", "聯準會", "利率決策", "升息", "降息", "鮑爾",
            "ECB", "BOJ", "英格蘭銀行", "央行週", "超級央行",
            "美債", "美元指數", "非農", "CPI", "核心通膨", "PMI", "ISM",
            "人民幣", "日圓", "歐元", "英鎊", "匯率"
        ]
    },
    "台灣總體經濟與數據": {
        "icon": "📊",
        "keywords": [
            "主計", "主計總處", "GDP", "景氣燈號", "景氣", "物價", "通膨",
            "失業率", "薪資", "外銷訂單", "出口統計", "進口統計", "海關",
            "貿易統計", "稅收", "超徵", "出生率", "少子化", "高齡化", "人口統計",
            "消費者信心", "製造業PMI", "非製造業"
        ]
    },
    "台灣產業與投資動向": {
        "icon": "🏭",
        "keywords": [
            "AI", "半導體", "台積電", "台積", "聯發科", "聯電", "鴻海",
            "台達電", "廣達", "緯創", "英業達", "資本支出", "供應鏈",
            "算力", "伺服器", "CoWoS", "先進封裝", "製程", "晶片",
            "離岸風電", "綠能", "電動車", "ASIC", "TPU", "GPU"
        ]
    },
    "台灣政府與政策訊息": {
        "icon": "🏛️",
        "keywords": [
            "國發會", "行政院", "總統府", "經濟部", "財政部", "金管會",
            "國科會", "央行", "衛福部", "內政部", "院會", "政院",
            "法案", "預算", "補助", "政策", "施政", "法規", "條例",
            "立法院", "立委", "修法"
        ]
    },
}

CATEGORY_ORDER = [
    "社論與評論觀點",
    "國際機構與智庫報告",
    "地緣政治與國際衝突",
    "國際金融與貨幣政策",
    "台灣總體經濟與數據",
    "台灣政府與政策訊息",
    "台灣產業與投資動向",
]

MUST_READ_KEYS = [
    "Fed", "FOMC", "鮑爾", "主計", "GDP", "景氣燈號",
    "衝突", "戰爭", "利率決議", "升息", "降息",
    "外銷訂單", "超徵", "荷莫茲"
]

# 非經濟版面關鍵字：這些版面的新聞若標題無任何經濟關鍵字，直接略過
NON_ECON_SECTIONS = [
    "焦點新聞", "社會", "地方", "體育", "娛樂", "影視",
    "生活", "健康", "農業", "司法", "法庭"
]

# 標題有這些詞 → 判定為非經濟，直接略過
NON_ECON_TITLE_KEYS = [
    "大麻", "毒品", "農業", "旱情", "春雨", "廚餘", "豬",
    "失智", "長照", "安樂死", "安寧", "防癌", "保險理賠",
    "農業旱", "觀光", "甘肅翻車", "金門", "禁團令旅遊",
    "信用卡月費", "房價指數"
]

# 所有分類的經濟關鍵字合集（用於判斷非經濟版面的新聞是否值得保留）
ALL_ECON_KEYS = set()
for dept in DEPARTMENTS.values():
    ALL_ECON_KEYS.update(dept["keywords"])
ALL_ECON_KEYS.update(MUST_READ_KEYS)


# ── 2. 過濾非經濟新聞 ──────────────────────────────────────────────

def should_skip(title, source):
    """判斷這則新聞是否應略過（非經濟情報相關）"""
    # 標題有明確非經濟詞彙
    if any(k in title for k in NON_ECON_TITLE_KEYS):
        return True
    # 非經濟版面 + 標題無任何經濟關鍵字
    if any(sec in source for sec in NON_ECON_SECTIONS):
        if not any(k in title for k in ALL_ECON_KEYS):
            return True
    return False


# ── 3. 文本解析邏輯 ────────────────────────────────────────────────────

def is_noise_line(line):
    noise = ["回到目錄", "來源:", "來源：", "版面", "作者", "日期", "頁次", "新聞議題", "報導媒體"]
    if line.isdigit():
        return True
    return any(k in line for k in noise)

def clean_text_blocks(text_list):
    if not text_list:
        return ""
    combined_text = ""
    for line in text_list:
        line = line.strip()
        if not line or is_noise_line(line):
            continue
        if combined_text and not combined_text.endswith(("。", "！", "？", "；", "」", "\u201d")):
            combined_text += line
        else:
            combined_text += "\n" + line
    combined_text = combined_text.strip()
    sentences = re.split(r'(?<=[。！？；])', combined_text)
    paragraphs = []
    current_para = ""
    count = 0
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        current_para += s
        count += 1
        if (count >= 3 and s.endswith(("。", "！", "？", "；"))) or s.endswith(("」", "\u201d")):
            paragraphs.append(current_para.strip())
            current_para = ""
            count = 0
    if current_para:
        paragraphs.append(current_para.strip())
    return "\n\n".join(paragraphs)

def find_article(article_index, title):
    key = title.replace(" ", "")
    best_content = ""
    best_score = 0
    for art_key, content in article_index.items():
        for n in [14, 12, 10, 8, 6]:
            if key[:n] and key[:n] in art_key:
                if n > best_score:
                    best_score = n
                    best_content = content
                break
    return best_content if best_score >= 6 else ""

def extract_summary(content, limit=220):
    if not content:
        return "尚未擷取到內文摘要"
    parts = [p.strip() for p in content.split("\n\n") if p.strip()]
    if parts:
        return parts[0][:limit] + ("..." if len(parts[0]) > limit else "")
    return content[:limit] + ("..." if len(content) > limit else "")

def build_article_index(pdf):
    index = {}
    last_key = None
    raw_content_map = {}
    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue
        has_source = any(l.startswith("來源:") or l.startswith("來源：") for l in lines[:8])
        if has_source:
            src_idx = next(
                i for i, l in enumerate(lines)
                if l.startswith("來源:") or l.startswith("來源：")
            )
            title_key = "".join(lines[:src_idx]).replace(" ", "")
            raw_content_map[title_key] = lines[src_idx + 1:]
            last_key = title_key
        elif (
            last_key
            and len("".join(lines)) > 50
            and not page.extract_table()
            and not any("回到目錄" in l for l in lines[:5])
        ):
            if last_key in raw_content_map:
                raw_content_map[last_key].extend(lines)
        else:
            last_key = None
    for key, text_list in raw_content_map.items():
        index[key] = clean_text_blocks(text_list)
    return index


# ── 4. 執行解析 ──────────────────────────────────────────────────────

def run_dashboard():
    data_folder = "data"
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
    pdf_files = [f for f in os.listdir(data_folder) if f.lower().endswith(".pdf")]

    all_items = []
    skipped = 0
    if pdf_files:
        pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join(data_folder, x)))
        latest_pdf = os.path.join(data_folder, pdf_files[-1])
        print(f"處理檔案: {latest_pdf}")

        with pdfplumber.open(latest_pdf) as pdf:
            article_index = build_article_index(pdf)
            for page in pdf.pages[:15]:
                table = page.extract_table()
                if not table:
                    continue
                for row in table[1:]:
                    if not row or len(row) < 2 or not row[1]:
                        continue
                    title = str(row[1]).replace("\n", "").strip()
                    source = str(row[2]).replace("\n", " ").strip() if len(row) > 2 and row[2] else "EPC彙整"
                    if len(title) < 5 or any(k in title for k in ["新聞議題", "報導媒體", "目錄", "頁次"]):
                        continue

                    # 過濾非經濟新聞
                    if should_skip(title, source):
                        skipped += 1
                        continue

                    classify_text = title + " " + source
                    found_cat = None
                    for cat in CATEGORY_ORDER:
                        if any(k in classify_text for k in DEPARTMENTS[cat]["keywords"]):
                            found_cat = cat
                            break
                    # 略過無法分類的（其他雜項不顯示）
                    if not found_cat:
                        skipped += 1
                        continue

                    content = find_article(article_index, title)
                    all_items.append({
                        "title": title,
                        "source": source,
                        "cat": found_cat,
                        "priority": 1 if any(k in title for k in MUST_READ_KEYS) else 0,
                        "summary": extract_summary(content),
                        "full_text": content
                    })

    print(f"保留 {len(all_items)} 則，略過 {skipped} 則非經濟新聞")
    generate_html(all_items)
    print("✅ 已產生 index.html")


# ── 5. HTML 生成 ──────────────────────────────────────────────

def build_js(data_json, dept_json, cat_order_json):
    lines = [
        "const DATA = " + data_json + ";",
        "const DEPTS = " + dept_json + ";",
        "const CAT_ORDER = " + cat_order_json + ";",
        "",
        "function esc(s){",
        "  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');",
        "}",
        "",
        "function init(){",
        "  const yr=new Date().getFullYear();",
        "  document.getElementById('roc-year').textContent='\u6c11\u570b '+(yr-1911)+' \u5e74';",
        "  document.getElementById('today-date').textContent=new Date().toLocaleDateString('zh-TW',{year:'numeric',month:'long',day:'numeric'});",
        "  const nav=document.getElementById('nav-bar');",
        "  CAT_ORDER.forEach(cat=>{",
        "    const div=document.createElement('div');",
        "    div.className='nav-item';",
        "    const icon=DEPTS[cat]?DEPTS[cat].icon:'';",
        "    div.textContent=icon+' '+cat;",
        "    div.onclick=function(){filterFeed(cat,this);};",
        "    nav.appendChild(div);",
        "  });",
        "  renderCarousel();",
        "  renderFeed('all');",
        "}",
        "",
        "function renderCarousel(){",
        "  const area=document.getElementById('carousel-area');",
        "  if(DATA.length===0){area.innerHTML='<div class=\"carousel-slide active\" style=\"display:flex;\"><h2>\u4eca\u65e5\u5c1a\u7121\u8cc7\u6599</h2></div>';return;}",
        "  const featured=DATA.filter(i=>i.priority===1).slice(0,5);",
        "  if(featured.length===0)featured.push(...DATA.slice(0,5));",
        "  featured.forEach((item,idx)=>{",
        "    const slide=document.createElement('div');",
        "    slide.className='carousel-slide'+(idx===0?' active':'');",
        "    if(idx===0)slide.style.display='flex';",
        "    const dataIdx=DATA.indexOf(item);",
        "    slide.innerHTML=",
        "      '<span class=\"carousel-eye\">\u24c2 '+esc(item.cat)+'</span>'+",
        "      '<h2 class=\"carousel-title\" onclick=\"showFull('+dataIdx+')\">'+esc(item.title)+'</h2>'+",
        "      '<p class=\"carousel-summary\">'+esc(item.summary)+'</p>'+",
        "      '<button class=\"carousel-btn\" onclick=\"showFull('+dataIdx+')\">'+",
        "        '\u95b1\u8b80\u5168\u6587 \u2192'+'</button>';",
        "    area.appendChild(slide);",
        "  });",
        "  let cur=0;",
        "  setInterval(()=>{",
        "    const s=document.querySelectorAll('.carousel-slide');",
        "    if(s.length<=1)return;",
        "    s[cur].classList.remove('active');",
        "    s[cur].style.display='none';",
        "    cur=(cur+1)%s.length;",
        "    s[cur].classList.add('active');",
        "    s[cur].style.display='flex';",
        "  },5000);",
        "}",
        "",
        "function renderFeed(cat){",
        "  const list=document.getElementById('news-feed');",
        "  list.innerHTML='';",
        "  const f=cat==='all'?DATA:DATA.filter(i=>i.cat===cat);",
        "  if(f.length===0){",
        "    list.innerHTML='<div style=\"padding:40px 0;color:#999;text-align:center;\">\u76ee\u524d\u7121\u8cc7\u6599</div>';",
        "    return;",
        "  }",
        "  f.forEach((item,i)=>{",
        "    const div=document.createElement('div');",
        "    div.className='news-item'+(item.priority===1?' must':'');",
        "    const dataIdx=DATA.indexOf(item);",
        "    div.innerHTML=",
        "      '<div class=\"news-meta\">'+",
        "        '<span class=\"news-cat-tag\">'+esc(item.cat)+'</span>'+",
        "        (item.priority===1?'<span class=\"must-badge\">\u5fc5\u770b</span>':'')+",
        "        '<span class=\"news-source\">'+esc(item.source)+'</span>'+",
        "      '</div>'+",
        "      '<h3 class=\"news-title\" onclick=\"showFull('+dataIdx+')\">'+esc(item.title)+'</h3>'+",
        "      '<p class=\"news-summary\">'+esc(item.summary)+'</p>'+",
        "      '<button class=\"read-more\" onclick=\"showFull('+dataIdx+')\">'+",
        "        '\u95b1\u8b80\u5168\u6587 \u2192'+'</button>';",
        "    list.appendChild(div);",
        "  });",
        "}",
        "",
        "function filterFeed(cat,el){",
        "  document.querySelectorAll('.nav-item').forEach(x=>x.classList.remove('active'));",
        "  if(el)el.classList.add('active');",
        "  document.getElementById('current-view-title').textContent=cat==='all'?'TODAY\\'S INTELLIGENCE':cat;",
        "  renderFeed(cat);",
        "  window.scrollTo({top:document.querySelector('.main-layout').offsetTop-60,behavior:'smooth'});",
        "}",
        "",
        "function showFull(idx){",
        "  const item=DATA[idx];",
        "  const contentHtml=item.full_text?esc(item.full_text):'\u5c1a\u672a\u64f7\u53d6\u5230\u5167\u6587\u5167\u5bb9';",
        "  document.getElementById('modal-content').innerHTML=",
        "    '<div class=\"modal-article\">'+",
        "      '<div class=\"modal-cat\">'+esc(item.cat)+'</div>'+",
        "      '<h1 class=\"modal-title\">'+esc(item.title)+'</h1>'+",
        "      '<div class=\"modal-source\">\u4f86\u6e90\uff1a'+esc(item.source)+'</div>'+",
        "      '<div class=\"article-content\">'+contentHtml+'</div>'+",
        "    '</div>';",
        "  document.getElementById('modal').style.display='block';",
        "  document.body.style.overflow='hidden';",
        "}",
        "",
        "function closeModal(){",
        "  document.getElementById('modal').style.display='none';",
        "  document.body.style.overflow='auto';",
        "}",
        "",
        "document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});",
        "init();",
    ]
    return "\n".join(lines)


CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --navy: #00335e;
  --accent: #0076d6;
  --accent2: #00a3e0;
  --bg: #f8f9fb;
  --white: #ffffff;
  --border: rgba(0,0,0,0.08);
  --text-p: #1a1a2e;
  --text-s: #4a5568;
  --text-m: #8a94a6;
  --must: #e53e3e;
  --must-bg: #fff5f5;
  --radius: 12px;
}

body {
  font-family: 'Public Sans', 'Noto Sans TC', -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text-p);
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}

/* ── TOP BAR ── */
.top-bar {
  background: var(--navy);
  color: rgba(255,255,255,0.55);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 10px 60px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.top-bar-right { display: flex; gap: 24px; }

/* ── HEADER ── */
.site-header {
  background: var(--white);
  border-bottom: 1px solid var(--border);
  padding: 20px 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.brand h1 {
  font-size: 24px;
  font-weight: 800;
  color: var(--navy);
  letter-spacing: -0.02em;
  border-left: 4px solid var(--accent);
  padding-left: 14px;
  line-height: 1.2;
}
.brand p {
  font-size: 12px;
  color: var(--text-m);
  padding-left: 18px;
  margin-top: 3px;
  letter-spacing: 0.05em;
}
.header-date {
  font-size: 15px;
  font-weight: 700;
  color: var(--navy);
  text-align: right;
}

/* ── STICKY NAV ── */
.imf-nav {
  background: var(--navy);
  display: flex;
  padding: 0 60px;
  position: sticky;
  top: 0;
  z-index: 100;
  overflow-x: auto;
  scrollbar-width: none;
  gap: 2px;
}
.imf-nav::-webkit-scrollbar { display: none; }
.nav-item {
  color: rgba(255,255,255,0.7);
  padding: 16px 22px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  letter-spacing: 0.02em;
  border-bottom: 3px solid transparent;
}
.nav-item:hover { color: #fff; background: rgba(255,255,255,0.06); }
.nav-item.active { color: #fff; border-bottom-color: var(--accent2); background: rgba(255,255,255,0.08); }

/* ── HERO CAROUSEL ── */
.carousel-container {
  background: linear-gradient(135deg, #0a1628 0%, #00335e 60%, #004a8f 100%);
  position: relative;
  overflow: hidden;
  padding: 60px 0;
}

/* Animated orbs */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  animation: orbFloat linear infinite;
  pointer-events: none;
}
.orb1 { width:400px; height:400px; background:radial-gradient(circle,rgba(0,118,214,0.4) 0%,transparent 70%); top:-100px; right:8%; animation-duration:20s; }
.orb2 { width:280px; height:280px; background:radial-gradient(circle,rgba(0,163,224,0.25) 0%,transparent 70%); bottom:-80px; right:30%; animation-duration:28s; animation-delay:-10s; }
.orb3 { width:200px; height:200px; background:radial-gradient(circle,rgba(94,92,230,0.2) 0%,transparent 70%); top:30px; left:20%; animation-duration:16s; animation-delay:-5s; }
@keyframes orbFloat {
  0% { transform:translate(0,0) scale(1); }
  33% { transform:translate(-25px,18px) scale(1.04); }
  66% { transform:translate(18px,-12px) scale(0.96); }
  100% { transform:translate(0,0) scale(1); }
}

/* Rotating ring */
.dot-ring {
  position:absolute; right:60px; top:50%; transform:translateY(-50%);
  width:200px; height:200px; opacity:0.7;
}
.dot-ring svg { animation:ringRotate 40s linear infinite; }
@keyframes ringRotate { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }

/* Grid overlay */
.hero-grid {
  position:absolute; inset:0;
  background-image:linear-gradient(rgba(255,255,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.03) 1px,transparent 1px);
  background-size:52px 52px;
}

.carousel-inner { max-width:1200px; margin:0 auto; padding:0 60px; position:relative; min-height:240px; }
.carousel-slide {
  position:absolute; inset:0 60px;
  display:none; flex-direction:column; justify-content:center;
  animation:slideIn 0.6s ease;
}
.carousel-slide.active { display:flex; }
@keyframes slideIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
.carousel-eye {
  font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase;
  color:var(--accent2); margin-bottom:14px;
}
.carousel-title {
  font-size:32px; font-weight:800; color:#fff; line-height:1.25;
  letter-spacing:-0.02em; margin-bottom:14px; cursor:pointer;
  max-width:680px;
}
.carousel-title:hover { color:var(--accent2); }
.carousel-summary { font-size:15px; color:rgba(255,255,255,0.55); max-width:600px; margin-bottom:24px; line-height:1.7; }
.carousel-btn {
  display:inline-block; background:var(--accent); color:#fff;
  border:none; padding:11px 24px; font-size:14px; font-weight:700;
  cursor:pointer; letter-spacing:0.02em; transition:background 0.2s;
  width:fit-content;
}
.carousel-btn:hover { background:var(--accent2); }

/* Carousel dots */
.carousel-dots { display:flex; justify-content:center; gap:8px; margin-top:24px; position:relative; z-index:5; }
.carousel-dot { width:6px; height:6px; border-radius:50%; background:rgba(255,255,255,0.3); transition:all 0.3s; cursor:pointer; }
.carousel-dot.active { background:#fff; width:24px; border-radius:3px; }

/* Stats strip */
.stats-strip {
  background:var(--white);
  border-bottom:1px solid var(--border);
  display:flex;
}
.stat-cell {
  flex:1; padding:20px 28px; border-right:1px solid var(--border);
  transition:background 0.15s;
}
.stat-cell:last-child { border-right:none; }
.stat-cell:hover { background:#f4f6f9; }
.stat-num { font-size:28px; font-weight:800; letter-spacing:-0.03em; line-height:1; margin-bottom:4px; }
.stat-num.c-must { color:var(--must); }
.stat-num.c-accent { color:var(--accent); }
.stat-num.c-navy { color:var(--navy); }
.stat-label { font-size:12px; color:var(--text-m); font-weight:600; letter-spacing:0.04em; text-transform:uppercase; }

/* ── MAIN LAYOUT ── */
.main-layout {
  max-width:1200px; margin:48px auto; padding:0 60px;
  display:grid; grid-template-columns:1fr 300px; gap:60px;
}

.feed-header {
  display:flex; align-items:baseline; justify-content:space-between;
  border-bottom:2px solid var(--navy); padding-bottom:14px; margin-bottom:28px;
}
.feed-title { font-size:14px; font-weight:800; letter-spacing:0.08em; color:var(--navy); text-transform:uppercase; }
.feed-count { font-size:13px; color:var(--text-m); font-weight:500; }

/* News item */
.news-item {
  padding:24px 0; border-bottom:1px solid var(--border);
  transition:all 0.15s;
  opacity:0; transform:translateY(12px);
  animation:itemReveal 0.4s ease forwards;
}
.news-item.must { border-left:3px solid var(--must); padding-left:18px; }
@keyframes itemReveal { to{opacity:1;transform:translateY(0)} }

.news-meta { display:flex; align-items:center; gap:8px; margin-bottom:8px; flex-wrap:wrap; }
.news-cat-tag {
  font-size:11px; font-weight:700; letter-spacing:0.06em;
  color:var(--accent); text-transform:uppercase;
}
.must-badge {
  font-size:10px; font-weight:700; background:var(--must);
  color:#fff; padding:2px 7px; letter-spacing:0.05em;
}
.news-source { font-size:11px; color:var(--text-m); margin-left:auto; }

.news-title {
  font-size:19px; font-weight:700; color:var(--navy); line-height:1.45;
  letter-spacing:-0.02em; margin-bottom:10px; cursor:pointer;
  transition:color 0.15s;
  font-family:'Noto Serif TC','Georgia',serif;
}
.news-title:hover { color:var(--accent); }
.news-item.must .news-title { color:#c53030; }
.news-item.must .news-title:hover { color:var(--accent); }

.news-summary { font-size:14px; color:var(--text-s); line-height:1.75; margin-bottom:12px; }

.read-more {
  background:none; border:1px solid var(--border); color:var(--accent);
  font-size:12px; font-weight:700; padding:6px 14px; cursor:pointer;
  letter-spacing:0.04em; transition:all 0.15s;
}
.read-more:hover { background:var(--accent); color:#fff; border-color:var(--accent); }

/* Sidebar */
.sidebar-box {
  background:var(--white); border:1px solid var(--border);
  padding:24px; border-top:4px solid var(--navy);
}
.sidebar-box h3 {
  font-size:13px; font-weight:800; letter-spacing:0.08em;
  text-transform:uppercase; color:var(--navy); margin-bottom:14px;
}
.sidebar-box p { font-size:13px; color:var(--text-s); line-height:1.7; }
.sidebar-cat-list { margin-top:20px; }
.sidebar-cat-item {
  display:flex; align-items:center; justify-content:space-between;
  padding:8px 0; border-bottom:1px solid var(--border);
  font-size:13px;
}
.sidebar-cat-item:last-child { border-bottom:none; }
.sidebar-cat-name { color:var(--text-s); }
.sidebar-cat-count { font-weight:700; color:var(--navy); }

/* ── MODAL ── */
.modal {
  display:none; position:fixed; inset:0;
  background:rgba(0,0,0,0.5); z-index:1000;
  overflow-y:auto; padding:40px 20px;
}
.modal-inner {
  background:var(--white); max-width:800px;
  margin:0 auto; position:relative;
}
.modal-header {
  padding:16px 32px; background:var(--navy);
  display:flex; justify-content:space-between; align-items:center;
  position:sticky; top:0;
}
.modal-header-brand { font-size:12px; font-weight:700; letter-spacing:0.1em; color:rgba(255,255,255,0.6); }
.modal-close {
  background:rgba(255,255,255,0.15); color:#fff; border:none;
  padding:7px 18px; font-size:13px; font-weight:600; cursor:pointer;
  letter-spacing:0.04em; transition:background 0.15s;
}
.modal-close:hover { background:rgba(255,255,255,0.25); }
.modal-article { padding:48px; }
.modal-cat { font-size:11px; font-weight:700; letter-spacing:0.1em; color:var(--accent); text-transform:uppercase; margin-bottom:12px; }
.modal-title {
  font-size:34px; font-weight:800; color:var(--navy); line-height:1.25;
  letter-spacing:-0.02em; margin-bottom:16px;
  font-family:'Noto Serif TC','Georgia',serif;
}
.modal-source { font-size:13px; color:var(--text-m); font-weight:600; padding-bottom:24px; border-bottom:1px solid var(--border); margin-bottom:32px; }
.article-content { font-size:17px; line-height:2.0; color:var(--text-s); white-space:pre-line; text-align:justify; }

@media(max-width:900px){
  .main-layout{grid-template-columns:1fr;padding:0 24px;}
  .imf-nav,.top-bar,.site-header{padding-left:24px;padding-right:24px;}
  .carousel-inner{padding:0 24px;}
  .dot-ring{display:none;}
  .modal-article{padding:28px;}
  .modal-title{font-size:24px;}
  .article-content{font-size:15px;}
}
"""


def generate_html(data):
    # 計算各分類數量供側邊欄用
    cat_counts = {}
    must_count = sum(1 for i in data if i["priority"] == 1)
    for item in data:
        cat_counts[item["cat"]] = cat_counts.get(item["cat"], 0) + 1

    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    dept_json = json.dumps(
        {k: {"icon": v["icon"]} for k, v in DEPARTMENTS.items()},
        ensure_ascii=False
    ).replace("</", "<\\/")
    cat_order_json = json.dumps(CATEGORY_ORDER, ensure_ascii=False)

    # 側邊欄 HTML
    sidebar_cats_html = ""
    for cat in CATEGORY_ORDER:
        cnt = cat_counts.get(cat, 0)
        icon = DEPARTMENTS[cat]["icon"]
        sidebar_cats_html += (
            f'<div class="sidebar-cat-item">'
            f'<span class="sidebar-cat-name">{icon} {cat}</span>'
            f'<span class="sidebar-cat-count">{cnt}</span>'
            f'</div>'
        )

    js_code = build_js(data_json, dept_json, cat_order_json)

    html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-TW">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>\u7d93\u6fdf\u898f\u5283\u79d1 Intelligence Hub</title>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@700;900&family=Public+Sans:wght@400;600;700;800&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">\n'
        '<style>\n' + CSS + '\n</style>\n'
        '</head>\n'
        '<body>\n'

        # Top bar
        '<div class="top-bar">'
        '<span>EPC INTELLIGENCE NETWORK &nbsp;&middot;&nbsp; <span id="roc-year"></span></span>'
        '<div class="top-bar-right">'
        '<span>INTERNAL USE ONLY</span>'
        '</div>'
        '</div>\n'

        # Header
        '<header class="site-header">'
        '<div class="brand">'
        '<h1>\u7d93\u6fdf\u898f\u5283\u79d1 Intelligence Hub</h1>'
        '<p>National Development Council &middot; Economic Planning Division</p>'
        '</div>'
        '<div class="header-date" id="today-date"></div>'
        '</header>\n'

        # Sticky nav
        '<nav class="imf-nav" id="nav-bar">'
        '<div class="nav-item active" onclick="filterFeed(\'all\', this)">\U0001f3e0 \u6700\u65b0\u9996\u9801</div>'
        '</nav>\n'

        # Hero carousel
        '<section class="carousel-container">'
        '<div class="hero-grid"></div>'
        '<div class="orb orb1"></div>'
        '<div class="orb orb2"></div>'
        '<div class="orb orb3"></div>'
        '<div class="dot-ring">'
        '<svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="100" cy="100" r="90" stroke="rgba(255,255,255,0.07)" stroke-width="1"/>'
        '<circle cx="100" cy="100" r="65" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>'
        '<circle cx="100" cy="100" r="40" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>'
        '<circle cx="100" cy="10" r="4" fill="rgba(0,118,214,0.9)"/>'
        '<circle cx="178" cy="55" r="3" fill="rgba(255,255,255,0.5)"/>'
        '<circle cx="178" cy="145" r="2.5" fill="rgba(255,255,255,0.3)"/>'
        '<circle cx="100" cy="190" r="4" fill="rgba(0,163,224,0.8)"/>'
        '<circle cx="22" cy="145" r="2.5" fill="rgba(255,255,255,0.3)"/>'
        '<circle cx="22" cy="55" r="3" fill="rgba(255,149,0,0.7)"/>'
        '<path d="M100 10 A90 90 0 0 1 178 55" stroke="rgba(0,163,224,0.7)" stroke-width="2.5" stroke-linecap="round"/>'
        '</svg>'
        '</div>'
        '<div class="carousel-inner" id="carousel-area"></div>'
        '</section>\n'

        # Stats strip
        '<div class="stats-strip">'
        f'<div class="stat-cell"><div class="stat-num c-must">{must_count}</div><div class="stat-label">Must Read</div></div>'
        f'<div class="stat-cell"><div class="stat-num c-accent">{len(data)}</div><div class="stat-label">Today\'s Total</div></div>'
        f'<div class="stat-cell"><div class="stat-num c-navy">{len(cat_counts)}</div><div class="stat-label">Categories</div></div>'
        '<div class="stat-cell"><div class="stat-num c-navy" style="font-size:18px;" id="stat-date"></div><div class="stat-label">Report Date</div></div>'
        '</div>\n'

        # Main layout
        '<div class="main-layout">'
        '<section>'
        '<div class="feed-header">'
        '<span class="feed-title" id="current-view-title">TODAY\'S INTELLIGENCE</span>'
        f'<span class="feed-count">{len(data)} articles</span>'
        '</div>'
        '<div id="news-feed"></div>'
        '</section>'

        # Sidebar
        '<aside>'
        '<div class="sidebar-box">'
        '<h3>EPC \u5206\u985e\u6982\u89bd</h3>'
        f'<div class="sidebar-cat-list">{sidebar_cats_html}</div>'
        '</div>'
        '<div class="sidebar-box" style="margin-top:24px;">'
        '<h3>\u653f\u7b56\u63d0\u793a</h3>'
        '<p style="font-size:13px;color:#666;">\u672c\u8cc7\u8a0a\u4f9b\u5167\u90e8\u53c3\u8003\uff0c\u8acb\u6ce8\u610f\u8cc7\u5b89\u898f\u7bc4\u3002</p>'
        '</div>'
        '</aside>'
        '</div>\n'

        # Modal
        '<div id="modal" class="modal">'
        '<div class="modal-inner">'
        '<div class="modal-header">'
        '<span class="modal-header-brand">EPC INTELLIGENCE REPORT</span>'
        '<button class="modal-close" onclick="closeModal()">\u95dc\u9589 &times;</button>'
        '</div>'
        '<div id="modal-content"></div>'
        '</div>'
        '</div>\n'

        '<script>\n' + js_code + '\n'
        # stat-date 額外設定
        'document.getElementById("stat-date").textContent=new Date().toLocaleDateString("zh-TW",{month:"short",day:"numeric"});\n'
        '</script>\n'
        '</body>\n'
        '</html>\n'
    )

    with open("index.html", "w", encoding="utf-8", errors="replace") as f:
        f.write(html)


if __name__ == "__main__":
    run_dashboard()
