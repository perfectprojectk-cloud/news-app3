#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ニュース取得スクリプト
GitHub Actionsから自動実行され、index.htmlを生成します
"""

import urllib.request
import re
import json
import os
from datetime import datetime

def fetch_rss(name, url):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'ja,en;q=0.9',
            'Cache-Control': 'no-cache',
        })
        with urllib.request.urlopen(req, timeout=10) as res:
            raw = res.read().decode('utf-8', errors='ignore')
        items = []
        entries = re.findall(r'<item>(.*?)</item>', raw, re.DOTALL)
        for entry in entries[:30]:
            title = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', entry)
            if not title:
                title = re.search(r'<title>(.*?)</title>', entry)
            link = re.search(r'<link>(.*?)</link>', entry)
            if not link:
                link = re.search(r'<guid>(.*?)</guid>', entry)
            desc = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>', entry)
            if not desc:
                desc = re.search(r'<description>(.*?)</description>', entry)
            if title:
                t = re.sub(r'<[^>]+>', '', title.group(1)).strip()
                l = link.group(1).strip() if link else '#'
                d = re.sub(r'<[^>]+>', '', desc.group(1) if desc else '').strip()[:300]
                if t and len(t) > 5:
                    items.append({'title': t, 'link': l, 'desc': d, 'source': name})
        print(f'  OK: {name} -> {len(items)}件')
        return items
    except Exception as e:
        print(f'  NG: {name} -> {e}')
        return []

def dedup(items, limit=15):
    seen = set()
    result = []
    for i in items:
        k = i['title'][:20]
        if k not in seen and len(i['title']) > 5:
            seen.add(k)
            result.append(i)
    return result[:limit]

def esc(s):
    return (s or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&#39;')

def make_cards(items):
    html = ''
    for i, item in enumerate(items):
        num   = str(i+1).zfill(2)
        title = esc(item['title'])
        link  = esc(item['link'])
        src   = esc(item['source'])
        desc  = item.get('desc','')
        if desc and len(desc) > 30:
            sents = re.split(r'[。！？]', desc)
            sents = [s.strip() for s in sents if len(s.strip()) > 10][:3]
        else:
            sents = []
        if not sents:
            sents = [item['title'], '詳細は元記事をご確認ください。']
        pts = ''
        for s in sents:
            s = esc(s)
            if not s.endswith(('。','！','？','」','）','.')):
                s += '。'
            pts += f'<li>{s}</li>'
        html += (
            f'<div class="card" onclick="tog(this)">'
            f'<div class="ch"><span class="cn">{num}</span>'
            f'<span class="ct">{title}</span>'
            f'<span class="ci">&#9662;</span></div>'
            f'<div class="cm"><span class="cs">&#128204; {src}</span></div>'
            f'<div class="sa"><ul class="sp">{pts}</ul>'
            f'<a href="{link}" class="rm">&#128214; 全文を読む &#8599;</a>'
            f'</div></div>\n'
        )
    return html

def main():
    print('=== ニュース取得開始 ===')
    now = datetime.utcnow()
    # 日本時間に変換（UTC+9）
    from datetime import timedelta
    jst = now + timedelta(hours=9)
    updated = jst.strftime('%Y年%m月%d日 %H:%M')

    print('--- 社会 ---')
    social = dedup(
        fetch_rss('Yahoo!国内',     'https://news.yahoo.co.jp/rss/topics/domestic.xml') +
        fetch_rss('Yahoo!国際',     'https://news.yahoo.co.jp/rss/topics/world.xml') +
        fetch_rss('Yahoo!エンタメ', 'https://news.yahoo.co.jp/rss/topics/entertainment.xml')
    )
    print('--- 経済 ---')
    economy = dedup(
        fetch_rss('Yahoo!経済',  'https://news.yahoo.co.jp/rss/topics/business.xml') +
        fetch_rss('Yahoo!IT',   'https://news.yahoo.co.jp/rss/topics/it.xml') +
        fetch_rss('ITmedia',    'https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml') +
        fetch_rss('Yahoo!科学', 'https://news.yahoo.co.jp/rss/topics/science.xml')
    )
    print('--- スポーツ ---')
    sports = dedup(
        fetch_rss('Yahoo!スポーツ', 'https://news.yahoo.co.jp/rss/topics/sports.xml')
    )
    print('--- 地域 ---')
    local = dedup(
        fetch_rss('Yahoo!地域', 'https://news.yahoo.co.jp/rss/topics/local.xml') +
        fetch_rss('NHK地域',    'https://www.nhk.or.jp/rss/news/cat4.xml') +
        fetch_rss('NHK社会',    'https://www.nhk.or.jp/rss/news/cat1.xml')
    )

    print(f'\n社会:{len(social)} 経済:{len(economy)} スポーツ:{len(sports)} 地域:{len(local)}')

    sh  = make_cards(social)
    eh  = make_cards(economy)
    sph = make_cards(sports)
    lh  = make_cards(local)

    sw_code = (
        "const C='nv4';\n"
        "self.addEventListener('install',()=>self.skipWaiting());\n"
        "self.addEventListener('activate',e=>{\n"
        "  e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))));\n"
        "  self.clients.claim();\n"
        "});\n"
        "self.addEventListener('fetch',e=>{\n"
        "  e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));\n"
        "});\n"
    )

    tabs_html = (
        '<div class="tab rs" id="t-social" onclick="sw(\'social\')">&#128478; 社会</div>\n'
        '<div class="tab" id="t-economy" onclick="sw(\'economy\')">&#128185; 経済</div>\n'
        '<div class="tab" id="t-sports" onclick="sw(\'sports\')">&#127942; スポーツ</div>\n'
        '<div class="tab" id="t-local" onclick="sw(\'local\')">&#127968; 地域</div>\n'
    )

    panels = {
        'social':  ('dr', '社会・国内外ニュース',    len(social),  sh),
        'economy': ('dg', '経済・ビジネスニュース',  len(economy), eh),
        'sports':  ('db', 'スポーツニュース',        len(sports),  sph),
        'local':   ('dy', '地域ニュース',            len(local),   lh),
    }
    panels_html = ''
    for i, (tid, (dcls, label, cnt, cards)) in enumerate(panels.items()):
        active = ' active' if i == 0 else ''
        panels_html += (
            f'<div class="panel{active}" id="{tid}">\n'
            f'<div class="sh"><div class="dot {dcls}"></div>'
            f'<span class="sl">{label}</span>'
            f'<span class="sc">{cnt}件</span></div>\n'
            f'<div class="nl">\n{cards}</div>\n</div>\n'
        )

    html = (
'<!DOCTYPE html>\n'
'<html lang="ja">\n'
'<head>\n'
'<meta charset="UTF-8">\n'
'<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">\n'
'<meta name="theme-color" content="#0d1117">\n'
'<meta name="apple-mobile-web-app-capable" content="yes">\n'
'<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
'<meta name="apple-mobile-web-app-title" content="今日のニュース">\n'
'<title>今日のニュース</title>\n'
'<style>\n'
'*{box-sizing:border-box;margin:0;padding:0}\n'
':root{--bg:#0d1117;--hd:#161b22;--bd:#21262d;'
'--red:#ff6b6b;--grn:#3fb950;--blu:#58a6ff;--yel:#d29922;'
'--tx:#e6edf3;--mt:#8b949e;--bdr:#30363d;'
'--cd:#1c2128;--cdh:#262c36;--r:12px;--sh:0 4px 20px rgba(0,0,0,.5)}\n'
'body{font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic UI",sans-serif;'
'background:var(--bg);color:var(--tx);min-height:100vh;overflow-x:hidden}\n'
'header{background:var(--hd);border-bottom:1px solid var(--bdr);'
'padding:14px 16px 0;position:sticky;top:0;z-index:100;'
'box-shadow:0 2px 16px rgba(0,0,0,.6)}\n'
'.ht{display:flex;align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap}\n'
'.logo{display:flex;align-items:center;gap:8px}\n'
'.logo-icon{font-size:22px}\n'
'.logo h1{font-size:17px;font-weight:700;'
'background:linear-gradient(90deg,var(--red),var(--grn));'
'-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}\n'
'.dt{font-size:10px;color:var(--mt);background:var(--bdr);'
'padding:3px 8px;border-radius:20px;white-space:nowrap;margin-left:auto}\n'
'.upd{font-size:10px;color:var(--mt)}\n'
'.tabs{display:flex;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}\n'
'.tabs::-webkit-scrollbar{display:none}\n'
'.tab{flex:1;min-width:72px;padding:10px 6px;text-align:center;cursor:pointer;'
'font-size:12px;font-weight:600;color:var(--mt);'
'border-bottom:2px solid transparent;transition:all .2s;user-select:none;white-space:nowrap}\n'
'.tab.rs{color:var(--red);border-color:var(--red)}\n'
'.tab.rg{color:var(--grn);border-color:var(--grn)}\n'
'.tab.rb{color:var(--blu);border-color:var(--blu)}\n'
'.tab.ry{color:var(--yel);border-color:var(--yel)}\n'
'main{padding:14px;max-width:760px;margin:0 auto}\n'
'.panel{display:none}.panel.active{display:block}\n'
'.sh{display:flex;align-items:center;gap:8px;margin-bottom:12px;'
'padding:10px 14px;background:var(--hd);border-radius:var(--r);border:1px solid var(--bdr)}\n'
'.dot{width:8px;height:8px;border-radius:50%}\n'
'.dr{background:var(--red);box-shadow:0 0 6px var(--red)}\n'
'.dg{background:var(--grn);box-shadow:0 0 6px var(--grn)}\n'
'.db{background:var(--blu);box-shadow:0 0 6px var(--blu)}\n'
'.dy{background:var(--yel);box-shadow:0 0 6px var(--yel)}\n'
'.sl{font-size:12px;font-weight:600;color:var(--mt)}\n'
'.sc{margin-left:auto;font-size:11px;color:var(--mt)}\n'
'.nl{display:flex;flex-direction:column;gap:8px}\n'
'.card{background:var(--cd);border:1px solid var(--bdr);border-radius:var(--r);'
'padding:13px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}\n'
'.card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;opacity:0;transition:opacity .2s}\n'
'#social .card::before{background:var(--red)}\n'
'#economy .card::before{background:var(--grn)}\n'
'#sports .card::before{background:var(--blu)}\n'
'#local .card::before{background:var(--yel)}\n'
'.card:hover{background:var(--cdh);transform:translateY(-1px);box-shadow:var(--sh)}\n'
'.card:hover::before,.card.open::before{opacity:1}\n'
'.card.open{background:var(--cdh)}\n'
'#social .card.open{border-color:var(--red)}\n'
'#economy .card.open{border-color:var(--grn)}\n'
'#sports .card.open{border-color:var(--blu)}\n'
'#local .card.open{border-color:var(--yel)}\n'
'.ch{display:flex;align-items:flex-start;gap:9px}\n'
'.cn{font-size:10px;font-weight:700;padding:2px 6px;border-radius:8px;'
'white-space:nowrap;margin-top:2px;flex-shrink:0}\n'
'#social .cn{color:var(--red);background:rgba(255,107,107,.12)}\n'
'#economy .cn{color:var(--grn);background:rgba(63,185,80,.12)}\n'
'#sports .cn{color:var(--blu);background:rgba(88,166,255,.12)}\n'
'#local .cn{color:var(--yel);background:rgba(210,153,34,.12)}\n'
'.ct{font-size:14px;font-weight:600;line-height:1.5;flex:1}\n'
'.ci{font-size:11px;color:var(--mt);margin-left:auto;transition:transform .2s;flex-shrink:0;margin-top:2px}\n'
'.card.open .ci{transform:rotate(180deg)}\n'
'.cm{display:flex;margin-top:6px;margin-left:33px}\n'
'.cs{font-size:11px;color:var(--mt)}\n'
'.sa{display:none;margin-top:11px;padding-top:11px;border-top:1px solid var(--bdr)}\n'
'.card.open .sa{display:block}\n'
'.sp{list-style:none;display:flex;flex-direction:column;gap:6px}\n'
'.sp li{display:flex;gap:7px;align-items:flex-start;font-size:13px;line-height:1.7}\n'
'.sp li::before{content:"\\25B8";flex-shrink:0;margin-top:2px}\n'
'#social .sp li::before{color:var(--red)}\n'
'#economy .sp li::before{color:var(--grn)}\n'
'#sports .sp li::before{color:var(--blu)}\n'
'#local .sp li::before{color:var(--yel)}\n'
'.rm{display:inline-flex;align-items:center;gap:5px;margin-top:9px;'
'font-size:12px;text-decoration:none;padding:5px 12px;border-radius:20px;transition:all .2s}\n'
'#social .rm{color:var(--red);border:1px solid rgba(255,107,107,.3)}\n'
'#economy .rm{color:var(--grn);border:1px solid rgba(63,185,80,.3)}\n'
'#sports .rm{color:var(--blu);border:1px solid rgba(88,166,255,.3)}\n'
'#local .rm{color:var(--yel);border:1px solid rgba(210,153,34,.3)}\n'
'#social .rm:hover{background:rgba(255,107,107,.1)}\n'
'#economy .rm:hover{background:rgba(63,185,80,.1)}\n'
'#sports .rm:hover{background:rgba(88,166,255,.1)}\n'
'#local .rm:hover{background:rgba(210,153,34,.1)}\n'
'.hint{display:none;position:fixed;bottom:0;left:0;right:0;'
'background:var(--hd);border-top:2px solid var(--blu);'
'padding:18px 20px;z-index:200;text-align:center}\n'
'.hint.show{display:block}\n'
'.hint h3{font-size:15px;margin-bottom:8px}\n'
'.hint p{font-size:13px;color:var(--mt);line-height:2;margin-bottom:12px}\n'
'.hint p strong{color:var(--tx)}\n'
'.hint button{background:var(--bdr);border:none;color:var(--mt);'
'padding:7px 22px;border-radius:20px;cursor:pointer;font-size:13px}\n'
'.footer{text-align:center;font-size:11px;color:var(--mt);padding:12px 0 24px}\n'
'@media(max-width:480px){.ct{font-size:13px}main{padding:10px}}\n'
'</style>\n'
'</head>\n'
'<body>\n'
'<header>\n'
'  <div class="ht">\n'
'    <div class="logo"><span class="logo-icon">&#128240;</span><h1>今日のニュース</h1></div>\n'
f'    <span class="dt" id="dt"></span>\n'
f'    <span class="upd">更新: {updated}</span>\n'
'  </div>\n'
'  <div class="tabs">\n'
+ tabs_html +
'  </div>\n'
'</header>\n'
'<main>\n'
+ panels_html +
f'  <div class="footer">ニュースソース: Yahoo!ニュース / ITmedia / NHK &nbsp;|&nbsp; 最終更新: {updated}</div>\n'
'</main>\n'
'<div class="hint" id="chint">\n'
'  <h3>&#128242; iPhoneにインストール</h3>\n'
'  <p>Chromeの右下 <strong>「&#8942;」</strong> をタップ<br>'
'  &#8594; <strong>「ホーム画面に追加」</strong><br>'
'  &#8594; <strong>「追加」</strong> &#8594; 完了！</p>\n'
'  <button onclick="closeHint()">閉じる</button>\n'
'</div>\n'
'<script>\n'
'document.getElementById("dt").textContent=\n'
'  new Date().toLocaleDateString("ja-JP",{year:"numeric",month:"long",day:"numeric",weekday:"short"});\n'
'function sw(tab){\n'
'  document.querySelectorAll(".panel").forEach(p=>p.classList.remove("active"));\n'
'  document.querySelectorAll(".tab").forEach(t=>t.classList.remove("rs","rg","rb","ry"));\n'
'  document.getElementById(tab).classList.add("active");\n'
'  const cls={social:"rs",economy:"rg",sports:"rb",local:"ry"};\n'
'  document.getElementById("t-"+tab).classList.add(cls[tab]);\n'
'}\n'
'function tog(card){\n'
'  const o=card.classList.contains("open");\n'
'  document.querySelectorAll(".card.open").forEach(c=>c.classList.remove("open"));\n'
'  if(!o) card.classList.add("open");\n'
'}\n'
'const isIOS=/iPad|iPhone|iPod/.test(navigator.userAgent)&&!window.MSStream;\n'
'if(isIOS&&!window.navigator.standalone&&!sessionStorage.getItem("ch")){\n'
'  setTimeout(()=>document.getElementById("chint").classList.add("show"),2000);\n'
'}\n'
'function closeHint(){\n'
'  document.getElementById("chint").classList.remove("show");\n'
'  sessionStorage.setItem("ch","1");\n'
'}\n'
'const md={name:"今日のニュース",short_name:"今日のニュース",\n'
'  start_url:"./",display:"standalone",\n'
'  background_color:"#0d1117",theme_color:"#0d1117",lang:"ja",\n'
'  icons:[{src:"data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 192 192\'%3E%3Crect width=\'192\' height=\'192\' rx=\'40\' fill=\'%230d1117\'/%3E%3Crect x=\'18\' y=\'18\' width=\'156\' height=\'20\' rx=\'10\' fill=\'%23ff6b6b\'/%3E%3Crect x=\'18\' y=\'58\' width=\'156\' height=\'13\' rx=\'6\' fill=\'%23e6edf3\' opacity=\'.9\'/%3E%3Ccircle cx=\'38\' cy=\'168\' r=\'14\' fill=\'%233fb950\'/%3E%3C/svg%3E",\n'
'    sizes:"192x192",type:"image/svg+xml"}]};\n'
'const mb=new Blob([JSON.stringify(md)],{type:"application/json"});\n'
'const ml=document.createElement("link");\n'
'ml.rel="manifest";ml.href=URL.createObjectURL(mb);\n'
'document.head.appendChild(ml);\n'
'if("serviceWorker" in navigator){\n'
f'  const swSrc=`{sw_code}`;\n'
'  const sb=new Blob([swSrc],{type:"application/javascript"});\n'
'  navigator.serviceWorker.register(URL.createObjectURL(sb),{scope:"./"})\n'
'    .catch(e=>console.warn("SW:",e));\n'
'}\n'
'</script>\n'
'</body>\n'
'</html>\n'
    )

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'index.html生成完了: {len(html):,}文字')

if __name__ == '__main__':
    main()