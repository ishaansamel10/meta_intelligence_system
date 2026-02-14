---
title: Meta Sentiment Intelligence
emoji: 🛸
colorFrom: purple
colorTo: indigo
sdk: streamlit
sdk_version: "1.28.0"
app_file: streamlit_app.py
pinned: false
---

# Meta Sentiment Intelligence System

**Architecture:** Gradio = frontend, n8n workflow = backend. Data comes from CSV + 2 RSS feeds (configured in n8n).

## Quick Start

1. **Set up n8n workflow** – Follow [N8N_SETUP.md](N8N_SETUP.md), then **Publish** the workflow in n8n
2. **Pre-configure webhook URL** (so users don't have to paste it):
   - Copy `config.example.json` to `config.json`
   - Set `webhook_url` to your n8n webhook URL (e.g. `http://localhost:5678/webhook/meta-sentiment`)
   - Or set env var: `export N8N_WEBHOOK_URL=http://localhost:5678/webhook/meta-sentiment`
3. **Run Streamlit:**
   ```bash
   pip install -r requirements.txt
   streamlit run streamlit_app.py
   ```
4. Users just click **Run Analysis** — no need to paste the URL or press Execute in n8n

## Flow

```
[CSV] + [RSS 1] + [RSS 2] → n8n Workflow (sentiment + responses) → Respond to Webhook
                                                                    ↓
Gradio UI ← HTTP POST ←─────────────────────────────────────────────┘
```

## Data Sources (in n8n)

- **CSV:** Meta-Glasses-Reviews.csv (Amazon reviews)
- **RSS 1:** Google News "Ray-Ban Meta"
- **RSS 2:** Google News "Meta smart glasses review"

Gradio only displays results; the workflow handles all data collection and processing.
