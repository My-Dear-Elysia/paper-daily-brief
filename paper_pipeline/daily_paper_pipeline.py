"""
每日医学AI论文抓取管线
流程：PubMed搜索 → 筛选 → PMC全文抓取 → 入库 → 生成简报
"""
import sys, os, re, json, time, urllib.request
from datetime import datetime, timedelta

KB_BASE = "/root/Hermes/knowledge_base"
DAILY_DIR = os.path.join(KB_BASE, "daily_arxiv")
os.makedirs(DAILY_DIR, exist_ok=True)

# ========= 1. PubMed 搜索 =========
# 医学AI相关搜索词
QUERIES = [
    '"large language model" AND medical AND (2025[dp] OR 2026[dp])',
    '"clinical AI" OR "medical agent" OR "healthcare agent" AND (2025[dp] OR 2026[dp])',
    '"clinical reasoning" AND "large language model" AND (2025[dp] OR 2026[dp])',
    '"medical AI" AND ("deep learning" OR "foundation model") AND (2025[dp] OR 2026[dp])',
    'RAG AND (clinical OR medical) AND (2025[dp] OR 2026[dp])',
]

def search_pubmed(query, retmax=10):
    """搜索PubMed返回论文列表"""
    import urllib.parse
    
    # ESearch
    params = urllib.parse.urlencode({
        'db': 'pubmed',
        'term': query,
        'retmax': retmax,
        'sort': 'relevance',
        'retmode': 'json'
    })
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Hermes'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        ids = data.get('esearchresult', {}).get('idlist', [])
        return ids
    except Exception as e:
        print(f"  PubMed搜索失败: {e}")
        return []

def fetch_details(pmids):
    """获取论文详细信息"""
    if not pmids:
        return []
    
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = urllib.parse.urlencode({
        'db': 'pubmed', 'id': ','.join(pmids),
        'retmode': 'json', 'retmax': 50
    })
    
    try:
        req = urllib.request.Request(f"{url}?{params}", headers={'User-Agent': 'Hermes'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        
        papers = []
        result = data.get('result', {})
        uids = result.get('uids', [])
        for uid in uids:
            info = result.get(uid, {})
            papers.append({
                'pmid': uid,
                'title': info.get('title', ''),
                'source': info.get('source', ''),
                'pubdate': info.get('pubdate', ''),
                'authors': ', '.join(a.get('name','') for a in info.get('authors', [])[:5]),
                'doi': info.get('elocationid', '').replace('doi: ', '') if 'doi' in info.get('elocationid', '') else '',
                'pmc_id': '',
            })
        return papers
    except Exception as e:
        print(f"  获取详情失败: {e}")
        return []

def check_pmc(pmid):
    """检查是否有PMC免费全文"""
    url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Hermes'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        records = data.get('records', [])
        if records and 'pmcid' in records[0]:
            return records[0]['pmcid']
    except:
        pass
    return ''

def fetch_abstract(pmid):
    """获取摘要"""
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml&rettype=abstract"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Hermes'})
        resp = urllib.request.urlopen(req, timeout=15)
        xml = resp.read().decode('utf-8')
        # 简单提取AbstractText
        abstract = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>', xml, re.DOTALL)
        return abstract.group(1).strip() if abstract else ''
    except:
        return ''

# ========= 主流程 =========
today = datetime.now().strftime("%Y-%m-%d")
print(f"=== 每日医学AI论文抓取 [{today}] ===\n")

all_pmids = set()
for i, q in enumerate(QUERIES):
    print(f"搜索 {i+1}/{len(QUERIES)}...", end=" ", flush=True)
    ids = search_pubmed(q, retmax=10)
    all_pmids.update(ids)
    print(f"找到 {len(ids)} 篇")

print(f"\n去重后共 {len(all_pmids)} 篇")
all_pmids = list(all_pmids)[:20]  # 最多20篇

papers = fetch_details(all_pmids)
if not papers:
    print("未获取到论文信息")
    sys.exit(0)

# 检查PMC全文
print(f"\n检查PMC全文可用性...")
for p in papers:
    pmc = check_pmc(p['pmid'])
    if pmc:
        p['pmc_id'] = pmc
        print(f"  ✅ {p['title'][:60]}... PMC全文可用")

# 获取摘要
print(f"\n获取摘要...")
for p in papers[:10]:
    if not p.get('abstract'):
        p['abstract'] = fetch_abstract(p['pmid'])
    time.sleep(0.3)

# 生成日报
date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
report = f"""# 每日医学AI论文简报
**日期:** {date_str}
**来源:** PubMed
**搜索关键词:** 医学LLM / Clinical Agent / Medical AI / Clinical Reasoning / RAG

---

"""
for p in papers[:15]:
    report += f"""## {p['title']}

**期刊:** {p['source']} | **日期:** {p['pubdate']}
**作者:** {p['authors'][:100]}
**PMID:** {p['pmid']}
**DOI:** {p['doi']}
**PMC:** {'✅ ' + p['pmc_id'] if p['pmc_id'] else '❌ 无免费全文'}

**摘要:**
{p.get('abstract', '（无摘要）')[:800]}

---

"""

# 保存
out = os.path.join(DAILY_DIR, f"daily_{today}.md")
with open(out, 'w', encoding='utf-8') as f:
    f.write(report)

print(f"\n✅ 日报已保存: {out}")
print(f"共 {len(papers)} 篇论文, {len([p for p in papers if p['pmc_id']])} 篇免费全文")

# 打印简报预览
print("\n=== 今日论文速览 ===")
for i, p in enumerate(papers[:10], 1):
    pmc_flag = "📄" if p['pmc_id'] else "🔒"
    print(f"{i:2d}. {pmc_flag} {p['title'][:80]}")
    print(f"     {p['source']} | {p['pubdate']}")
