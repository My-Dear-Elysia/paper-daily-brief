# Paper Daily Brief / 论文日报

Daily medical AI paper briefing system.  
Searches PubMed → fetches full text → DeepSeek analysis → structured daily/weekly/monthly/quarterly/yearly reports.

Also includes a **learning recommendation module** that tracks your course progress and suggests what to study next.

## Architecture

```
PubMed (4 queries)
    │
    ▼
Fetch details + abstracts
    │
    ├── Check PMC free full text
    │
    ▼
DeepSeek structured analysis
    │
    ▼
Markdown report (daily_YYYY-MM-DD.md)
    │
    ▼
  01_时间链/
  ├── 日报/       ← daily briefs
  └── 汇总/       ← weekly / monthly / quarterly / yearly summaries
```

## Features

- **Daily brief**: 12 papers/day from 4 PubMed queries, DeepSeek-analyzed
- **Journal IF filtering**: Built-in IF dictionary (~80 journals)
- **PMC full text**: Auto-downloads and analyzes PMC open-access papers
- **Weekly/Monthly/Quarterly/Yearly summaries**: Trend analysis + industry news (Tavily)
- **Learning recommendation**: Tracks your course progress, suggests what to study today
- **PubMed ⚠️ labels**: Warns about CAPTCHA on PubMed links, prioritizes DOI

## Requirements

- Python 3.10+
- DeepSeek API key
- Tavily API key (for news in summaries)
- (Optional) DashScope/Qwen API key for OCR pipeline

## Setup

```bash
# 1. Clone
git clone git@github.com:WentaoLi-Med/paper-daily-brief.git
cd paper-daily-brief

# 2. Install dependencies
pip install openai

# 3. Set up environment
export DEEPSEEK_API_KEY="sk-..."
export TAVILY_API_KEY="tvly-..."

# 4. Create output directories
mkdir -p output/daily output/summaries output/planning

# 5. Run
python3 daily_brief_v02.py
```

## Usage

### Daily brief (cron: 0 7 * * *)
```bash
python3 daily_brief_v02.py
```

### Summaries (cron: weekly Mon / monthly 1st / quarterly / yearly)
```bash
python3 daily_brief_summary.py weekly
python3 daily_brief_summary.py monthly
python3 daily_brief_summary.py quarterly
python3 daily_brief_summary.py yearly
```

## Configuration

### Journal IF Dictionary
Edit `JOURNAL_IF` in `daily_brief_v02.py` to add/update journal impact factors.

### PubMed Queries
Edit `QUERIES` in `daily_brief_v02.py` to customize search topics.

### Learning Tracker
Edit `learning_tracker.json` to update your course progress:
```json
{
  "current_course": "Course Name",
  "current_chapter": 1,
  "total_chapters": 10,
  "progress_pct": 10
}
```

## Output Example

```
━━━ 今日简报 (2026-07-19) ━━━━━━━━━━━━━━━━━━━━
📄 新论文 12 篇（PMC全文: 6篇）
📌 最高IF: Cancer Cell (31.7) — A context-augmented LLM...
📖 当前学习: CS231n — CNN架构（进度0%）
⏭ 下一步：CS229 机器学习讲义
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Privacy

- No data leaves your server except PubMed/Tavily API calls
- DeepSeek API calls send paper abstracts only (no patient data)
- All reports stored locally as Markdown files
- API keys configured via environment variables, not hardcoded

## Customization

- Add more PubMed queries: edit `QUERIES` list
- Add journal IFs: extend `JOURNAL_IF` dictionary
- Change output directory: set `BASE` path
- Add more learning courses: edit `learning_tracker.json`

## License

MIT
