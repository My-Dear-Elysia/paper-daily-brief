#!/usr/bin/env python3
"""
汇总脚本：周报/月报/季报/年报
PubMed独立搜索 + 新闻（Tavily）→ DeepSeek 综合分析
"""
import sys, os, json, re, time, calendar, urllib.request, urllib.parse
from datetime import datetime, timedelta, date
from openai import OpenAI

SUMMARY_DIR = "output/summaries"
os.makedirs(SUMMARY_DIR, exist_ok=True)

Llm = None
tavily_key = ""

JOURNAL_IF = {
    "Nature": 50.5, "Science": 44.8, "Cell": 45.5, "N Engl J Med": 96.2,
    "Lancet": 98.4, "JAMA": 63.1, "BMJ": 93.6, "Nat Commun": 14.7,
    "PLoS One": 2.9, "Sci Rep": 3.8, "PNAS": 9.4, "Elife": 6.4,
    "Nat Med": 58.7, "Sci Transl Med": 15.8,
    "Nat Genet": 31.7, "Nat Methods": 36.1, "Genome Biol": 10.1,
    "Nat Rev Genet": 42.8, "Nucleic Acids Res": 16.6,
    "Nat Immunol": 27.7, "Immunity": 25.5, "J Exp Med": 12.6,
    "J Immunol": 4.4, "Front Immunol": 5.7, "Autophagy": 13.3,
    "JAMA Netw Open": 10.5, "JAMA Intern Med": 22.5,
    "Lancet Digit Health": 23.8, "Lancet Infect Dis": 25.4,
    "Nat Rev Drug Discov": 120.1, "Clin Infect Dis": 8.2,
    "Am J Respir Crit Care Med": 19.3, "Thorax": 9.2,
    "Chest": 9.6, "Eur Respir J": 16.6, "Cancer Cell": 31.7,
    "Nat Neurosci": 25.0, "Neuron": 14.7, "Brain": 10.6,
    "J Am Med Inform Assoc": 6.4, "Int J Med Inform": 5.5,
    "JMIR Med Inform": 3.1, "JMIR": 5.8, "J Med Internet Res": 5.8,
    "NPJ Digit Med": 12.4, "NPJ Digit. Med.": 12.4,
    "Med Image Anal": 10.6, "IEEE Trans Med Imaging": 8.9,
    "Artif Intell Med": 5.1, "Interdiscip Sci": 2.5,
    "Front Med (Lausanne)": 3.1, "Clin Imaging": 1.5,
    "Ophthalmol Sci": 3.2, "Cancers (Basel)": 4.5, "Cancers": 4.5,
    "Surv Ophthalmol": 4.2,
    "Med Teach": 4.1, "Acad Med": 5.1,
    "Int J Surg": 6.6, "Ann Transl Med": 3.6,
    "Radiology": 12.1, "Br J Radiol": 2.0, "J Nucl Med": 7.4,
    "Eur J Nucl Med Mol Imaging": 8.6,
    "Gastroenterology": 25.7, "Gut": 19.8, "Gastrointest Endosc": 7.7,
    "IEEE J Biomed Health Inform": 7.5,
    "Int J Mol Sci": 4.9, "BMC Health Serv Res": 2.0,
    "Eur J Cancer": 7.6, "Digit Health": 23.8,
    "Radiol Artif Intell": 8.0, "Nat Biomed Eng": 25.8,
    "Magn Reson Med Sci": 2.0,
    "Eur Heart J": 39.3, "Comput Biol Med": 6.5,
    "Biotechnol Adv": 12.1, "Circ Res": 20.1, "Clin Cancer Res": 10.0,
}

NEWS_QUERIES = [
    "medical AI FDA approval",
    "healthcare artificial intelligence industry",
    "Google DeepMind medical AI",
    "OpenAI healthcare clinical AI",
    "AI drug discovery clinical trial",
    "digital health startup funding",
]

UNRELIABLE_DOMAINS = [
    'precedenceresearch.com', 'grandviewresearch.com',
    'marketresearchfuture.com', 'marketresearch.biz',
    'marketsandmarkets.com', 'alliedmarketresearch.com',
    'gminsights.com', 'reportlinker.com',
]

BLOCK_JOURNALS = ["bioRxiv", "medRxiv", "arXiv"]

# === Helpers ===
def log_err(msg): print(f"[ERROR] {msg}", file=sys.stderr)

def init():
    global Llm, tavily_key
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key: return False
    Llm = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    return True

def lookup_if(j):
    j = j.strip().rstrip('.')
    if j in JOURNAL_IF: return JOURNAL_IF[j]
    for key in sorted(JOURNAL_IF.keys(), key=len, reverse=True):
        if key in j or j in key: return JOURNAL_IF[key]
    return None

def search_pubmed(query, retmax=20, mindate=None, maxdate=None):
    params = urllib.parse.urlencode({'db': 'pubmed', 'term': query, 'retmax': retmax, 'sort': 'relevance', 'retmode': 'json'})
    if mindate and maxdate:
        params += '&mindate=' + mindate + '&maxdate=' + maxdate + '&datetype=pdat'
    try:
        resp = urllib.request.urlopen(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}", timeout=15)
        return json.loads(resp.read()).get('esearchresult', {}).get('idlist', [])
    except Exception as e:
        log_err(f"search_pubmed: {e}")
        return []

def fetch_details(pmids):
    papers = []
    for i in range(0, len(pmids), 15):
        batch = pmids[i:i+15]
        params = urllib.parse.urlencode({'db': 'pubmed', 'id': ','.join(batch), 'retmode': 'json', 'retmax': 15})
        try:
            resp = urllib.request.urlopen(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{params}", timeout=15)
            data = json.loads(resp.read())
            for uid in data.get('result', {}).get('uids', []):
                try:
                    info = data['result'][uid]
                    eid = info.get('elocationid', '')
                    doi = ''
                    m = re.search(r'10\.\d{4,}/[^\s]+', eid)
                    if m: doi = m.group(0)
                    papers.append({
                        'pmid': uid, 'doi': doi, 'title': info.get('title', ''),
                        'journal': info.get('source', ''), 'pubdate': info.get('pubdate', ''),
                        'IF': lookup_if(info.get('source', '')) or 'N/A',
                    })
                except: pass
        except Exception as e:
            log_err(f"fetch_details: {e}")
        time.sleep(0.3)
    return papers

def collect_papers(start_date, end_date):
    date_range = f"{start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}[dp]"
    queries = [
        f'(large language model OR LLM) AND (medical OR clinical) AND {date_range}',
        f'(artificial intelligence OR machine learning) AND (clinical decision OR diagnosis) AND {date_range}',
        f'(RAG OR retrieval augmented generation) AND (medical OR clinical) AND {date_range}',
        f'(AI agent OR autonomous AI) AND (medicine OR healthcare) AND {date_range}',
    ]
    all_ids = set()
    for q in queries:
        ids = search_pubmed(q, retmax=30, mindate=start_date.strftime('%Y/%m/%d'), maxdate=end_date.strftime('%Y/%m/%d'))
        all_ids.update(ids)
        time.sleep(0.3)
    ids = list(all_ids)[:80]
    if not ids: return []
    papers = fetch_details(ids)
    # Blocklist
    papers = [p for p in papers if not any(b in (p.get('journal','') or '') for b in BLOCK_JOURNALS)]
    papers = [p for p in papers if not p.get('journal','').strip().startswith("Front")]
    # IF > 5
    papers = [p for p in papers if isinstance(p.get('IF'), (int, float)) and p['IF'] >= 5.0]
    papers.sort(key=lambda p: p.get('pubdate', ''), reverse=True)
    return papers[:60]

def search_news(days_back):
    if not tavily_key: return []
    all_news, seen_urls = [], set()
    for query in NEWS_QUERIES:
        try:
            data = json.dumps({"api_key": tavily_key, "query": query, "search_depth": "advanced", "max_results": 5, "days": days_back}).encode()
            req = urllib.request.Request("https://api.tavily.com/search", data=data, headers={"Content-Type": "application/json"}, method="POST")
            resp = urllib.request.urlopen(req, timeout=15)
            for r in json.loads(resp.read()).get('results', []):
                url = r.get('url', '').strip()
                if not url or url in seen_urls: continue
                if url.lower().endswith('.pdf') or '/pdf/' in url: continue
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower().removeprefix('www.').removeprefix('blog.')
                if any(d in domain for d in UNRELIABLE_DOMAINS): continue
                seen_urls.add(url)
                all_news.append({'title': r.get('title',''), 'url': url, 'content': r.get('content','')[:200], 'source': r.get('source','')})
            time.sleep(0.5)
        except Exception as e:
            log_err(f"search_news '{query[:40]}': {e}")
    return all_news

def generate_report(label, start, end, out_path, news_days):
    print(f"=== {label} [{start} ~ {end}] ===")
    papers = collect_papers(start, end)
    news = search_news(news_days)
    print(f"论文: {len(papers)} 篇, 新闻: {len(news)} 条")

    prompt = f"""你是医学AI行业分析师。对以下{label}的论文和行业新闻进行综合分析。
【论文】（{len(papers)}篇）
{"".join(f"{i+1}. [{p['journal']}(IF:{p['IF']})] {p['title']}\n" for i,p in enumerate(papers[:15]))}
【行业新闻】（{len(news)}条）
{"".join(f"N{i+1}. {n['title']}\n" for i,n in enumerate(news[:10]))}
输出JSON：{{"paper_summary":"", "industry_summary":"", "clusters":[{{"topic":"", count:0, "trend":""}}], "key_papers":[{{"index":1, "title":"", "why":""}}], "key_news":[{{"title":"", "why":""}}], "outlook":""}}"""
    for _ in range(3):
        try:
            resp = Llm.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.1, response_format={"type": "json_object"})
            analysis = json.loads(resp.choices[0].message.content)
            break
        except: pass
        time.sleep(3)
    else:
        print("分析失败")
        return

    # Build markdown
    md = f"""# 医学AI {label}
**期间:** {start} ~ {end}
**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**论文总数:** {len(papers)} | **行业新闻:** {len(news)} 条

---

## 一、本期概览

### 📄 论文动态
{analysis.get('paper_summary','')}

### 🏭 行业动态
{analysis.get('industry_summary','')}

"""
    # TOP10 journal table
    from collections import Counter
    jcount = Counter(p['journal'] + '||' + str(p['IF']) for p in papers)
    top10 = jcount.most_common(10)
    md += "### 📊 高频期刊 TOP10\n| 期刊 | IF | 篇数 |\n|:---|---:|---:|\n"
    for entry, count in top10:
        jname, jif = entry.split('||')
        md += f"| {jname} | {jif} | {count} |\n"

    if analysis.get('clusters'):
        md += "\n## 二、研究主题聚类\n"
        for c in analysis['clusters']:
            md += f"\n### {c['topic']}（{c.get('count',0)}篇）\n**趋势:** {c.get('trend','')}\n"

    if analysis.get('key_papers'):
        md += "\n## 三、重点推荐论文\n"
        for kp in analysis['key_papers']:
            idx = kp.get('index', 0)
            if 1 <= idx <= len(papers):
                p = papers[idx-1]
                doi_link = f" | [DOI](https://doi.org/{p['doi']})" if p.get('doi') else ''
                md += f"\n### {p['title']}\n**{p['journal']}** (IF:{p['IF']}) | [PubMed ⚠️](https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/){doi_link}\n\n**推荐理由:** {kp.get('why','')}\n"

    if analysis.get('key_news'):
        md += "\n## 四、行业动态\n"
        for kn in analysis['key_news']:
            matched = [n for n in news if n['title'] == kn.get('title','')]
            if matched:
                n = matched[0]
                md += f"\n### {kn['title']}\n**来源:** {n.get('source','')} | [链接]({n.get('url','#')})\n{n.get('content','')[:400]}\n"

    if analysis.get('outlook'):
        md += f"\n## 五、展望\n{analysis['outlook']}\n---\n*由 Hermes Agent 自动生成*\n"

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"✅ {out_path} ({len(papers)}篇论文 + {len(news)}条新闻)")

def run_weekly():
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    out = os.path.join(SUMMARY_DIR, f"weekly_{last_monday.strftime('%Y-%m-%d')}.md")
    generate_report("周报", last_monday, last_sunday, out, news_days=7)

def run_monthly():
    today = date.today()
    first = today.replace(day=1)
    last_end = first - timedelta(days=1)
    last_start = last_end.replace(day=1)
    out = os.path.join(SUMMARY_DIR, f"monthly_{last_start.strftime('%Y-%m')}.md")
    generate_report("月报", last_start, last_end, out, news_days=31)

def run_quarterly():
    today = date.today()
    q = (today.month - 1) // 3
    if q == 0:
        y, m = today.year - 1, 10
    else:
        y, m = today.year, (q - 1) * 3 + 1
    start = date(y, m, 1)
    end = date(y, m + 2, calendar.monthrange(y, m + 2)[1])
    qn = (m - 1) // 3 + 1
    out = os.path.join(SUMMARY_DIR, f"quarterly_{y}Q{qn}.md")
    generate_report(f"季报（{y}Q{qn}）", start, end, out, news_days=92)

def run_yearly():
    today = date.today()
    y = today.year - 1
    start = date(y, 1, 1)
    end = date(y, 12, 31)
    out = os.path.join(SUMMARY_DIR, f"yearly_{y}.md")
    generate_report(f"年报（{y}）", start, end, out, news_days=365)

if __name__ == "__main__":
    if not init(): print("需设置 DEEPSEEK_API_KEY"); sys.exit(1)
    if len(sys.argv) < 2:
        print("用法: python3 daily_brief_summary.py weekly|monthly|quarterly|yearly")
        sys.exit(1)
    {
        'weekly': run_weekly, 'monthly': run_monthly,
        'quarterly': run_quarterly, 'yearly': run_yearly
    }[sys.argv[1]]()