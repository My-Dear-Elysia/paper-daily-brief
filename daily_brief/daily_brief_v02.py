#!/usr/bin/env python3
"""
v0.2 — 每日医学AI论文简报
改动：期刊IF + PMC全文分析（有全文时不用摘要）
"""
import sys, os, json, time, urllib.request, urllib.parse, re
from datetime import datetime, timedelta
from openai import OpenAI

BRIEF_DIR = "output/daily"
os.makedirs(BRIEF_DIR, exist_ok=True)

# === 期刊影响因子字典（2024-2025 JCR） ===
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
    "Ophthalmol Sci": 3.2,
    "Cancers (Basel)": 4.5, "Cancers": 4.5,
    "Surv Ophthalmol": 4.2,
    "Med Teach": 4.1, "Acad Med": 5.1,
    "Int J Surg": 6.6, "Ann Transl Med": 3.6,
    "Radiology": 12.1, "Br J Radiol": 2.0, "J Nucl Med": 7.4,
    "Eur J Nucl Med Mol Imaging": 8.6,
    "Gastroenterology": 25.7, "Gut": 19.8, "Gastrointest Endosc": 7.7,
    "IEEE J Biomed Health Inform": 7.5,
    "Eur J Cancer": 7.6,
    "Int J Mol Sci": 4.9,
    "BMC Health Serv Res": 2.0,
    "Digit Health": 23.8,
    "Radiol Artif Intell": 8.0,
    "Nat Biomed Eng": 25.8,
    "Magn Reson Med Sci": 2.0,
    "Eur Heart J": 39.3,
    "Comput Biol Med": 6.5,
    "Biotechnol Adv": 12.1,
    "Circ Res": 20.1,
    "Clin Cancer Res": 10.0,
}

QUERIES = [
    '"large language model" AND medical AND 2026[dp]',
    '"clinical AI" OR "medical agent" AND 2026[dp]',
    '"clinical reasoning" AND "large language model" AND 2026[dp]',
    'RAG AND (clinical OR medical) AND 2026[dp]',
]

Llm = None  # lazy init

# === Helper ===
def log_err(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)

def get_if(journal_name):
    j = journal_name.strip()
    if j in JOURNAL_IF: return JOURNAL_IF[j]
    if j.endswith('.'):
        j2 = j[:-1].strip()
        if j2 in JOURNAL_IF: return JOURNAL_IF[j2]
    for key in sorted(JOURNAL_IF.keys(), key=len, reverse=True):
        if key in j or j in key: return JOURNAL_IF[key]
    return None

def _pass_if_filter(p, min_if=5.0):
    journal = p.get('journal', '')
    j = journal.strip()
    J_BLOCK = ["bioRxiv", "medRxiv", "arXiv"]
    if any(b in j for b in J_BLOCK): return False
    if j.startswith("Front") or j.startswith("Frontiers"): return False
    jif = get_if(journal)
    if jif is None: return False
    return float(jif) >= min_if

def search_pubmed(query, retmax=8):
    params = urllib.parse.urlencode({'db': 'pubmed', 'term': query, 'retmax': retmax, 'sort': 'relevance', 'retmode': 'json'})
    try:
        resp = urllib.request.urlopen(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}", timeout=15)
        return json.loads(resp.read()).get('esearchresult', {}).get('idlist', [])
    except Exception as e:
        log_err(f"search_pubmed: {e}")
        return []

def fetch_details(pmids):
    if not pmids: return []
    params = urllib.parse.urlencode({'db': 'pubmed', 'id': ','.join(pmids[:15]), 'retmode': 'json', 'retmax': 15})
    try:
        resp = urllib.request.urlopen(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{params}", timeout=15)
        data = json.loads(resp.read())
    except:
        data = None
    papers = []
    if data and 'result' in data:
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
                })
            except: pass
    return papers

def get_abstract(pmid):
    try:
        resp = urllib.request.urlopen(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml&rettype=abstract", timeout=15)
        xml = resp.read().decode('utf-8')
        parts = []
        for m in re.finditer(r'<AbstractText[^>]*>(.*?)</AbstractText>', xml, re.DOTALL):
            text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if text: parts.append(text)
        return '\n'.join(parts)[:3000]
    except:
        return ''

def check_pmc(pmid):
    try:
        resp = urllib.request.urlopen(f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json", timeout=10)
        data = json.loads(resp.read())
        if data.get('records') and 'pmcid' in data['records'][0]:
            return data['records'][0]['pmcid']
    except: pass
    return None

def fetch_pmc_text(pmcid):
    try:
        req = urllib.request.Request(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmcid}&retmode=xml")
        resp = urllib.request.urlopen(req, timeout=10)
        xml = resp.read().decode('utf-8', errors='replace')
        text = re.sub(r'<[^>]+>', ' ', xml)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:5000]
    except:
        return None

def analyze(p, llm):
    if p.get('_has_pmc') and p.get('_fulltext'):
        content, source = p['_fulltext'], "PMC全文"
    else:
        content, source = p.get('abstract', ''), "摘要"
    prompt = f"""分析以下医学论文，输出结构化摘要。分析基于{source}。
标题: {p['title']}
期刊: {p['journal']}
{source}: {content[:5000]}
格式：
**分析来源:** {source}
**领域:** 
**方法:** 
**核心发现:** 
**相关度（医学AI研究者）:** 
**一句话:** """
    for _ in range(2):
        try:
            resp = llm.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.1)
            content = resp.choices[0].message.content
            if content and content.strip(): return content
        except: pass
        time.sleep(2)
    return "**分析失败**"

def run():
    global Llm
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("❌ DEEPSEEK_API_KEY not set")
        return
    Llm = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"=== v0.2 医学AI日报 [{today}] ===\n")

    MEDAI_KEYWORDS = [
        'large language model', 'LLM', 'artificial intelligence', 'machine learning',
        'deep learning', 'RAG', 'retrieval augmented', 'clinical decision',
        'medical image', 'foundation model', 'GPT', 'ChatGPT', 'agent',
        'multimodal', 'vision-language', 'clinical reasoning', 'diagnostic',
    ]
    def _topic_match(p):
        title = (p.get('title', '') + ' ' + p.get('journal', '')).lower()
        return any(kw in title for kw in MEDAI_KEYWORDS)

    all_ids = set()
    for q in QUERIES:
        ids = search_pubmed(q)
        all_ids.update(ids)
        time.sleep(0.3)
    ids = list(all_ids)[:30]
    print(f"搜索 {len(ids)} 篇")

    papers = fetch_details(ids)
    if not papers: print("无结果"); return

    papers = [p for p in papers if _pass_if_filter(p)]
    print(f"期刊过滤后: {len(papers)} 篇")

    # 7-day dedup
    def load_recent_pmids(days=7):
        seen = set()
        for i in range(1, days+1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            fp = os.path.join(BRIEF_DIR, f"daily_{d}.md")
            if os.path.exists(fp):
                for m in re.finditer(r'PubMed ⚠️\]\(https://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/', open(fp).read()):
                    seen.add(m.group(1))
        return seen
    recent = load_recent_pmids(7)
    papers = [p for p in papers if p['pmid'] not in recent]
    if len(papers) != len(recent): print(f"去重后: {len(papers)} 篇")

    papers = [p for p in papers if _topic_match(p)]
    print(f"主题过滤后: {len(papers)} 篇")
    if not papers: print("无符合条件论文"); return

    papers = papers[:min(len(papers), 15)]

    # PubPeer
    for p in papers:
        p['_pubpeer_flag'] = False
        if not p.get('doi'): continue
        try:
            resp = urllib.request.urlopen(f"https://pubpeer.com/api/search?doi={p['doi']}", timeout=8)
            data = json.loads(resp.read())
            if data.get('status') == 'ok':
                for r in data.get('results', []):
                    if r.get('comments_total', 0) + r.get('concerns_total', 0) > 0:
                        p['_pubpeer_flag'] = True
                        break
        except: pass
        time.sleep(0.3)

    # Fetch abstracts + PMC
    for p in papers:
        p['abstract'] = get_abstract(p['pmid'])
        pmcid = check_pmc(p['pmid'])
        p['_pmcid'] = pmcid
        if pmcid:
            ft = fetch_pmc_text(pmcid)
            if ft:
                p['_fulltext'], p['_has_pmc'] = ft, True
        time.sleep(0.3)

    # DeepSeek analysis
    analyses = []
    for i, p in enumerate(papers):
        if p.get('_pubpeer_flag'):
            analyses.append("**⚠️ PubPeer有相关评论，已跳过自动分析。**")
        else:
            analyses.append(analyze(p, Llm))
        print(f"  [{i+1}/{len(papers)}] {'PMC' if p.get('_has_pmc') else '摘要'}")

    md = f"""# 每日医学AI论文简报 v0.2
**日期:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**来源:** PubMed | **分析:** DeepSeek
**期刊IF:** 2024-2025 JCR

---

"""
    for i, p in enumerate(papers):
        doi_link = f' | [DOI](https://doi.org/{p["doi"]})' if p.get('doi') else ''
        jif = get_if(p['journal'])
        jif_str = f" (IF: {jif})" if jif else " (IF: N/A)"
        pmc_tag = " 📄全文" if p.get('_has_pmc') else ""
        pubpeer_tag = " ⚠️PubPeer" if p.get('_pubpeer_flag') else ""
        md += f"""
## {i+1}. {p['title']}
**{p['journal']}{jif_str}** | {p['pubdate']} | [PubMed ⚠️](https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/){doi_link}{pmc_tag}{pubpeer_tag}
{analyses[i]}
---
"""

    out = os.path.join(BRIEF_DIR, f"daily_{today}.md")
    with open(out, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"\n✅ {out} ({len(papers)} 篇)")

if __name__ == "__main__":
    run()