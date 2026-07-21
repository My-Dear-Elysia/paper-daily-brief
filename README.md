# Paper Daily Brief / 论文日报

Automated medical AI paper digest system.  
PubMed search → quality filtering → PMC full text → DeepSeek structured analysis → daily/weekly/monthly/quarterly/yearly reports.

Built by a medical student (MD) for medical AI workflow automation.

## Features

- **PubMed search** — 4 query groups, medical AI topic matching
- **Journal IF filter** — built-in IF dictionary (~90 journals), IF > 5 only
- **Journal blacklist** — Frontiers series, bioRxiv/medRxiv blocked
- **PMC full text priority** — full text available → use full text, not abstract
- **PubPeer integrity check** — auto-skip papers with integrity concerns
- **Deduplication** — skip papers covered in the last 7 days
- **Structured analysis** — domain / method / findings / limitations / relevance
- **Multi-level summaries** — weekly → monthly → quarterly → yearly with trend analysis
- **Industry news** — Tavily search for AI healthcare news
- **Learning recommendation** — tracks course progress, suggests what to study

## Requirements

- Python 3.10+
- DeepSeek API key
- Tavily API key (for weekly/monthly summaries)

## Quick Start

```bash
git clone git@github.com:WentaoLi-Med/paper-daily-brief.git
cd paper-daily-brief

# Optional: use uv for faster dependency management
# uv venv --python /usr/bin/python3 --system-site-packages && source .venv/bin/activate

pip install openai

export DEEPSEEK_API_KEY="sk-..."
export TAVILY_API_KEY="tvly-..."

# Daily brief
python3 daily_brief_v02.py

# Weekly / Monthly / Quarterly / Yearly summary
python3 daily_brief_summary.py weekly
python3 daily_brief_summary.py monthly
python3 daily_brief_summary.py quarterly
python3 daily_brief_summary.py yearly
```

## Output

```
daily_2026-07-20.md
├── Paper 1: A context-augmented LLM for precision oncology (Cancer Cell, IF:31.7)
│   ├── Domain: precision oncology / RAG / LLM
│   ├── Method: RAG framework with MOAlmanac knowledge base
│   ├── Finding: 93% accuracy on real-world queries
│   └── Relevance: High — deployable RAG solution for clinical LLM
├── Paper 2: General-purpose LLMs outperform specialized clinical AI tools (Nat Med, IF:58.7)
...
weekly_2026-07-13.md  (trend clusters + industry news)
monthly_2026-06.md     (aggregated monthly trends)
quarterly_2026Q2.md     (quarterly landscape)
yearly_2025.md          (annual review)
```

## Pipeline

```
PubMed (4 queries, 30 IDs)
  │
  ├── Journal blacklist  → discard Front*/bioRxiv/medRxiv
  ├── IF > 5 filter
  ├── 7-day dedup
  ├── Topic relevance (medical AI keywords)
  └── PubPeer integrity check
  │
  ▼
PMC full text check  →  DeepSeek structured analysis
  │
  ▼
Markdown report → daily_YYYY-MM-DD.md
  │
  ▼
Aggregator → weekly / monthly / quarterly / yearly summaries
```

## File Structure

```
├── daily_brief_v02.py        # Daily brief pipeline
├── daily_brief_summary.py    # Multi-level summary aggregator
├── pyproject.toml            # Project config (uv compatible)
├── learning_tracker.json     # Course progress tracker
└── example/
    └── daily_2026-07-20.md   # Sample output
```

## Configuration

Edit these in the scripts:
- `JOURNAL_IF` — add/update journal impact factors
- `QUERIES` — customize PubMed search queries
- `J_BLOCK` / `UNRELIABLE_DOMAINS` — extend blocklists
- `BRIEF_DIR` / `SUMMARY_DIR` — change output paths

## License

MIT