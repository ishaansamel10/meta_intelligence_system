"""
Meta Sentiment Intelligence System - Streamlit Frontend
View reviews, analysis, generated responses; extract keywords; graphs & visualizations.
"""

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import urllib.request
import urllib.error

st.set_page_config(
    page_title="Meta Sentiment Intelligence",
    page_icon="🛸",
    layout="wide",
)

# Default webhook URL
def _load_default_webhook_url() -> str:
    url = os.environ.get("N8N_WEBHOOK_URL", "").strip()
    if url:
        return url
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
                return (data.get("webhook_url") or "").strip()
        except Exception:
            pass
    return ""

DEFAULT_WEBHOOK_URL = _load_default_webhook_url()

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "is", "was", "are", "were", "been", "be", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
    "can", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they",
    "my", "your", "his", "her", "its", "our", "their", "me", "him", "us", "them",
    "so", "if", "than", "when", "while", "where", "because", "just", "very", "also"
}

THEME_FILTER_OPTIONS = [
    ("All themes", ""), ("Camera quality", "camera_quality"), ("Design", "design"),
    ("Battery life", "battery_life"), ("Comfort", "comfort"), ("Features", "features"),
    ("Connectivity", "connectivity"), ("Audio", "audio"), ("Privacy", "privacy"),
    ("Price", "price"), ("AI Assistant", "ai_assistant"),
]
SENTIMENT_FILTER_OPTIONS = [
    ("All sentiments", ""), ("Positive", "positive"), ("Negative", "negative"), ("Neutral", "neutral"),
]
CHART_COLORS = {
    "positive": "#22c55e", "neutral": "#f59e0b", "negative": "#ef4444",
    "themes": "#6366f1", "concerns": "#ec4899",
    "sources": ["#3b82f6", "#8b5cf6", "#06b6d4", "#10b981"],
}


def _validate_webhook_url(url: str) -> Optional[str]:
    if not url or not url.strip():
        return "Webhook URL is required."
    u = url.strip().rstrip("/")
    if not u.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"
    if "webhook" not in u.lower() and "n8n" not in u.lower():
        return "URL should contain 'webhook' (e.g. /webhook/meta-sentiment)."
    return None


def call_n8n_webhook(webhook_url: str) -> tuple[Optional[dict], Optional[str]]:
    err = _validate_webhook_url(webhook_url)
    if err:
        return None, err
    url = webhook_url.strip().rstrip("/")
    try:
        req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"}, data=json.dumps({}).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}, None
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        return None, f"n8n returned {e.code}: {err_body[:200]}"
    except urllib.error.URLError as e:
        return None, f"Cannot reach n8n: {e.reason}. Is n8n running and the workflow active?"
    except json.JSONDecodeError as e:
        return None, f"n8n returned invalid JSON: {e}"
    except Exception as e:
        return None, str(e)


def parse_workflow_response(data: dict) -> tuple[dict, list]:
    sentiment = {}
    responses = []
    if isinstance(data, dict):
        sentiment = data.get("sentiment", {})
        responses = data.get("responses", [])
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            sentiment = first.get("sentiment", first)
            responses = first.get("responses", [first] if "headline" in first or "personalized_response" in first else [])
    if isinstance(sentiment, dict):
        sentiment.setdefault("totalItems", len(responses))
        sentiment.setdefault("positiveCount", 0)
        sentiment.setdefault("neutralCount", 0)
        sentiment.setdefault("negativeCount", 0)
        sentiment.setdefault("positivePercent", 0)
        sentiment.setdefault("neutralPercent", 0)
        sentiment.setdefault("negativePercent", 0)
        sentiment.setdefault("avgScore", 0.0)
        sentiment.setdefault("topThemes", {})
        sentiment.setdefault("topConcerns", {})
        sentiment.setdefault("sourceBreakdown", {})
    if not isinstance(responses, list):
        responses = [responses] if isinstance(responses, dict) else []
    return sentiment, responses


def _filter_responses(responses: list, sentiment_filter: str, theme_filter: str) -> list:
    if not responses:
        return []
    filtered = responses
    if sentiment_filter and sentiment_filter.strip():
        sent = sentiment_filter.strip().lower()
        filtered = [r for r in filtered if isinstance(r, dict) and str(r.get("ai_sentiment", "")).lower() == sent]
    if theme_filter and theme_filter.strip():
        theme_key = theme_filter.strip().lower()
        filtered = [r for r in filtered if isinstance(r, dict) and theme_key in [str(t).lower() for t in (r.get("ai_themes") or [])]]
    return filtered


def _get_review_text(r: dict) -> str:
    parts = []
    for key in ["summary", "content_clean", "headline", "full_title", "personalized_response"]:
        val = r.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
        elif isinstance(val, list):
            parts.extend(str(x) for x in val if x)
    return " ".join(parts)


def extract_keywords_from_reviews(responses: list, top_n: int = 25) -> list[tuple[str, int]]:
    words = []
    for r in responses:
        if isinstance(r, dict):
            text = _get_review_text(r)
            if not text:
                continue
            text = text.lower()
            tokens = re.findall(r"\b[a-z]{3,}\b", text)
            words.extend(t for t in tokens if t not in STOPWORDS)
    return Counter(words).most_common(top_n)


def build_reviews_display(responses: list) -> str:
    md = "## 📋 Reviews with Analysis & Generated Responses\n\n"
    for i, r in enumerate(responses):
        if not isinstance(r, dict):
            continue
        headline = r.get("headline", "Untitled") or "Untitled"
        summary = r.get("summary", "") or r.get("content_clean", "") or "—"
        source = r.get("source", "—")
        sentiment = str(r.get("ai_sentiment", "N/A")).upper()
        score = r.get("ai_sentiment_score", "—")
        themes = (r.get("ai_themes") or [])
        concerns = (r.get("ai_concerns") or [])
        response = r.get("personalized_response", "—")
        sentiment_color = {"POSITIVE": "🟢", "NEGATIVE": "🔴", "NEUTRAL": "🟡"}.get(sentiment, "⚪")
        md += f"""---
### {sentiment_color} Review #{i+1}: {headline}

| Field | Value |
|-------|-------|
| **Source** | {source} |
| **Sentiment** | {sentiment} (score: {score}) |
| **Themes** | {", ".join(t.replace("_", " ") for t in themes) if themes else "—"} |
| **Concerns** | {", ".join(str(c).replace("_", " ") for c in concerns) if concerns else "—"} |

**📝 Review:**\n> {summary[:400]}{"..." if len(summary) > 400 else ""}

**💬 AI-Generated Response:**\n> {response}

"""
    return md


def _derive_source_breakdown(responses: list) -> list[tuple[str, int]]:
    counts = {}
    for r in responses:
        if not isinstance(r, dict):
            continue
        src = r.get("feed_type") or r.get("source") or "Other"
        name = "Amazon Reviews" if "amazon" in str(src).lower() else "Google News"
        counts[name] = counts.get(name, 0) + 1
    return list(counts.items())


def _truncate_label(text: str, max_len: int = 30) -> str:
    s = str(text).replace("_", " ").title().strip()
    if len(s) <= max_len:
        return s
    part = s[: max_len - 1].rsplit(" ", 1)[0] if " " in s[:max_len] else s[: max_len - 1]
    return part + "…"


def build_all_charts(sentiment: dict, responses: list) -> go.Figure:
    total = sentiment.get("totalItems", len(responses)) or 1
    pos = sentiment.get("positiveCount", 0)
    neu = sentiment.get("neutralCount", 0)
    neg = sentiment.get("negativeCount", 0)
    if pos + neu + neg == 0:
        pos, neu, neg = 1, 1, 1
    top_themes = sentiment.get("topThemes", {})
    top_concerns = sentiment.get("topConcerns", {})
    source_breakdown = sentiment.get("sourceBreakdown", {})
    if isinstance(top_themes, dict):
        top_themes = sorted(top_themes.items(), key=lambda x: -x[1])[:8]
    if isinstance(top_concerns, dict):
        top_concerns = sorted(top_concerns.items(), key=lambda x: -x[1])[:6]
    if isinstance(source_breakdown, dict):
        source_breakdown = list(source_breakdown.items())[:5]
    if not source_breakdown and responses:
        source_breakdown = _derive_source_breakdown(responses)

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=["<b>Sentiment Distribution</b>", "<b>Top Themes</b>", "<b>Top Concerns</b>", "<b>By Source</b>"],
        specs=[[{"type": "pie"}, {"type": "bar"}], [{"type": "bar"}, {"type": "bar"}]],
        vertical_spacing=0.18, horizontal_spacing=0.12,
    )
    fig.add_trace(
        go.Pie(
            labels=["Positive", "Neutral", "Negative"], values=[pos, neu, neg],
            marker=dict(colors=[CHART_COLORS["positive"], CHART_COLORS["neutral"], CHART_COLORS["negative"]], line=dict(width=2, color="white")),
            hole=0.55, textinfo="label+percent", textposition="outside", textfont=dict(size=13), hoverinfo="label+percent+value",
        ), row=1, col=1,
    )
    if top_themes:
        fig.add_trace(
            go.Bar(x=[t[1] for t in top_themes], y=[_truncate_label(t[0]) for t in top_themes], orientation="h",
                   marker=dict(color=CHART_COLORS["themes"], line=dict(width=0)), text=[t[1] for t in top_themes], textposition="outside"),
            row=1, col=2,
        )
    if top_concerns:
        fig.add_trace(
            go.Bar(x=[c[1] for c in top_concerns], y=[_truncate_label(c[0]) for c in top_concerns], orientation="h",
                   marker=dict(color=CHART_COLORS["concerns"], line=dict(width=0)), text=[c[1] for c in top_concerns], textposition="outside"),
            row=2, col=1,
        )
    if source_breakdown:
        labels, values = [], []
        for item in source_breakdown:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                src, stats = item[0], item[1]
                name = "Amazon Reviews" if "amazon" in str(src).lower() else str(src).replace("_", " ").title()
                if "google" in str(src).lower() or "rss" in str(src).lower() or "news" in str(src).lower():
                    name = "Google News"
                labels.append(name)
                if isinstance(stats, dict):
                    values.append(stats.get("total", stats.get("positive", 0) + stats.get("neutral", 0) + stats.get("negative", 0)))
                elif isinstance(stats, (int, float)):
                    values.append(int(stats))
                else:
                    values.append(1)
        if labels and values:
            fig.add_trace(
                go.Bar(x=labels, y=values, marker=dict(color=CHART_COLORS["sources"][:len(labels)], line=dict(width=0)), text=values, textposition="outside"),
                row=2, col=2,
            )
    fig.update_yaxes(autorange="reversed", row=1, col=2, tickfont=dict(size=12))
    if top_concerns:
        fig.update_yaxes(autorange="reversed", row=2, col=1, tickfont=dict(size=12))
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#f0f0f0")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#f0f0f0")
    fig.update_layout(height=680, showlegend=False, margin=dict(t=80, b=60, l=100, r=60), paper_bgcolor="white", plot_bgcolor="#fafafa", font=dict(size=12), hovermode="closest")
    return fig


def build_table(responses: list, max_disp: int = 50) -> pd.DataFrame:
    table_data = []
    for i, r in enumerate(responses[:max_disp]):
        if isinstance(r, dict):
            h = str(r.get("headline", "") or "")[:60]
            if len(str(r.get("headline", "") or "")) > 60:
                h += "..."
            table_data.append({
                "#": i + 1, "Review": h,
                "Sentiment": str(r.get("ai_sentiment", "N/A")).upper(),
                "Score": r.get("ai_sentiment_score", "-"),
                "Themes": ", ".join((r.get("ai_themes") or [])[:3]).replace("_", " "),
                "Response Preview": (str(r.get("personalized_response", "")) or "")[:80] + ("..." if len(str(r.get("personalized_response", "")) or "") > 80 else ""),
            })
    return pd.DataFrame(table_data) if table_data else pd.DataFrame(columns=["#", "Review", "Sentiment", "Score", "Themes", "Response Preview"])


# ---- UI ----

if "workflow_data" not in st.session_state:
    st.session_state.workflow_data = None

st.title("🛸 Meta Sentiment Intelligence System")
st.markdown("**Tool name:** Meta Sentiment Intelligence (temporary)  \n**Description:** Automates sentiment analysis and personalized response generation for Ray-Ban Meta Smart Glasses feedback—transforming hours of manual work into actionable insights in minutes.")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📋 Reviews & Analysis", "🔑 Extract Keywords", "ℹ️ About"])

with tab1:
    st.subheader("Inputs")
    col1, col2 = st.columns([1, 2])
    with col1:
        webhook_url = st.text_input(
            "n8n Webhook URL",
            value=DEFAULT_WEBHOOK_URL,
            placeholder="e.g. http://localhost:5678/webhook/meta-sentiment or https://your-instance.app.n8n.cloud/webhook/meta-sentiment",
            help="Paste your workflow's Production webhook URL. Pre-filled from config.json if set.",
        )
        max_display = st.slider("Max reviews to display in table", 5, 100, 50, 5, help="Limit how many reviews show in the Results table (5–100)")
        if st.button("🚀 Run Analysis (Load from Workflow)", type="primary"):
            val_err = _validate_webhook_url(webhook_url or "")
            if val_err:
                st.error(f"⚠️ **Validation Error:** {val_err}")
            else:
                with st.spinner("Calling n8n workflow..."):
                    data, err = call_n8n_webhook(webhook_url)
                if err:
                    st.error(f"⚠️ **Workflow Error:** {err}")
                else:
                    try:
                        sentiment, responses = parse_workflow_response(data)
                        st.session_state.workflow_data = {"sentiment": sentiment, "responses": responses}
                        st.success("Data loaded successfully!")
                    except Exception as e:
                        st.error(f"⚠️ **Parse Error:** {e}")
        st.caption("**Data sources (in n8n):** CSV + 2 RSS feeds. Click Run Analysis to trigger the workflow.")
    with col2:
        if st.session_state.workflow_data:
            sentiment = st.session_state.workflow_data["sentiment"]
            responses = st.session_state.workflow_data["responses"]
            total = sentiment.get("totalItems", len(responses)) or 1
            pos = sentiment.get("positiveCount", 0)
            neu = sentiment.get("neutralCount", 0)
            neg = sentiment.get("negativeCount", 0)
            pos_pct = sentiment.get("positivePercent", round(100 * pos / total) if total else 0)
            neu_pct = sentiment.get("neutralPercent", round(100 * neu / total) if total else 0)
            neg_pct = sentiment.get("negativePercent", round(100 * neg / total) if total else 0)
            avg_score = float(sentiment.get("avgScore", 0))
            top_themes = sentiment.get("topThemes", {})
            top_concerns = sentiment.get("topConcerns", {})
            if isinstance(top_themes, dict):
                top_themes = list(top_themes.items())[:8]
            if isinstance(top_concerns, dict):
                top_concerns = list(top_concerns.items())[:5]
            top_theme_str = ", ".join(str(t).replace("_", " ").title() for t, _ in top_themes[:5]) if top_themes else "—"
            top_concern_str = ", ".join(str(c).replace("_", " ").title() for c, _ in top_concerns[:3]) if top_concerns else "—"
            reception = "strong overall reception" if pos_pct >= 40 else "mixed reception" if pos_pct >= 20 else "areas for improvement"
            st.markdown(f"""## 📊 Sentiment Overview
| Metric | Value |
|--------|-------|
| **Total Analyzed** | {total} |
| **Positive** | {pos} ({pos_pct}%) |
| **Neutral** | {neu} ({neu_pct}%) |
| **Negative** | {neg} ({neg_pct}%) |
| **Avg. Sentiment Score** | {avg_score:.2f} |

---
## 📈 Key Insights
- **Overall reception:** {pos_pct}% positive sentiment suggests **{reception}**.
- **Top themes mentioned:** {top_theme_str}
- **Top concerns:** {top_concern_str}
- **Data source:** CSV + 2 RSS feeds via n8n workflow (Amazon reviews, Google News)
""")
            st.plotly_chart(build_all_charts(sentiment, responses), use_container_width=True)
        else:
            st.info("Enter the webhook URL and click **Run Analysis** to load data.")

with tab2:
    st.subheader("Filters")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        rev_sent = st.selectbox("Filter by sentiment", [o[0] for o in SENTIMENT_FILTER_OPTIONS], key="rev_sent")
    with col2:
        rev_theme = st.selectbox("Filter by theme", [o[0] for o in THEME_FILTER_OPTIONS], key="rev_theme")
    with col3:
        st.write("")
        st.write("")
    if st.session_state.workflow_data:
        sent_val = next((o[1] for o in SENTIMENT_FILTER_OPTIONS if o[0] == rev_sent), "")
        theme_val = next((o[1] for o in THEME_FILTER_OPTIONS if o[0] == rev_theme), "")
        filtered = _filter_responses(st.session_state.workflow_data["responses"], sent_val, theme_val)
        if filtered:
            st.markdown(build_reviews_display(filtered))
            st.dataframe(build_table(filtered, 100), use_container_width=True)
        else:
            st.warning("No reviews match the selected filters. Try different filters.")
    else:
        st.info("Run **Run Analysis** in the Dashboard tab first to load reviews.")

with tab3:
    st.subheader("Inputs")
    col1, col2, col3 = st.columns(3)
    with col1:
        top_kw = st.slider("Number of top keywords", 10, 50, 25, 5)
        kw_sent = st.selectbox("Filter by sentiment", [o[0] for o in SENTIMENT_FILTER_OPTIONS], key="kw_sent")
    with col2:
        kw_theme = st.selectbox("Filter by theme", [o[0] for o in THEME_FILTER_OPTIONS], key="kw_theme")
        sort_kw = st.selectbox("Sort keywords by", ["Frequency (most common first)", "Alphabetical"])
    if st.button("Extract Keywords"):
        if not st.session_state.workflow_data or not st.session_state.workflow_data.get("responses"):
            st.warning("Run **Run Analysis** in the Dashboard first.")
        else:
            sent_val = next((o[1] for o in SENTIMENT_FILTER_OPTIONS if o[0] == kw_sent), "")
            theme_val = next((o[1] for o in THEME_FILTER_OPTIONS if o[0] == kw_theme), "")
            filtered = _filter_responses(st.session_state.workflow_data["responses"], sent_val, theme_val)
            if not filtered:
                st.warning("No reviews match the filters.")
            else:
                n = max(10, min(50, top_kw))
                keywords = extract_keywords_from_reviews(filtered, top_n=n)
                if not keywords:
                    theme_counts = {}
                    for r in filtered:
                        if isinstance(r, dict):
                            for t in (r.get("ai_themes") or []):
                                if t:
                                    key = str(t).replace("_", " ").title()
                                    theme_counts[key] = theme_counts.get(key, 0) + 1
                            for c in (r.get("ai_concerns") or []):
                                if c:
                                    key = str(c).replace("_", " ").title()
                                    theme_counts[key] = theme_counts.get(key, 0) + 1
                    keywords = sorted(theme_counts.items(), key=lambda x: -x[1])[:n]
                if keywords:
                    if sort_kw and "Alphabetical" in sort_kw:
                        keywords = sorted(keywords, key=lambda x: x[0].lower())
                    kw_fig = go.Figure(
                        data=[go.Bar(x=[k[1] for k in keywords], y=[k[0] for k in keywords], orientation="h", marker=dict(color="#06b6d4", line=dict(width=0)), text=[k[1] for k in keywords], textposition="outside")],
                        layout=dict(title=dict(text="<b>Extracted Keywords</b>", font=dict(size=18)), xaxis=dict(title="Frequency", showgrid=True, gridcolor="#f0f0f0"), yaxis=dict(autorange="reversed", showgrid=True, gridcolor="#f0f0f0"), height=550, paper_bgcolor="white", plot_bgcolor="#fafafa", margin=dict(l=120), font=dict(size=12), hovermode="closest"),
                    )
                    st.plotly_chart(kw_fig, use_container_width=True)
                    kw_md = "| Rank | Keyword | Count |\n|------|--------|------|\n"
                    for i, (word, count) in enumerate(keywords, 1):
                        kw_md += f"| {i} | **{word}** | {count} |\n"
                    st.markdown(f"## 🔑 Extracted Keywords\n\n{kw_md}\n*From {len(filtered)} reviews (stopwords removed).*")
                else:
                    st.info("No keywords extracted.")

with tab4:
    st.markdown("""
## 🛸 Meta Sentiment Intelligence System

**Tool name:** Meta Sentiment Intelligence (temporary)

**Description:** Automates sentiment analysis and personalized response generation for Ray-Ban Meta Smart Glasses feedback—transforming hours of manual work into actionable insights in minutes.

---

### What it does
- Collects reviews from CSV (Amazon) and 2 RSS feeds (Google News)
- Runs sentiment analysis (Claude AI) to detect positive, negative, neutral
- Extracts themes (camera quality, design, battery life, etc.) and concerns
- Generates personalized customer service responses for each review
- Provides interactive dashboards, keyword extraction, and filters by sentiment/theme

### Who it's for
Brand managers, customer success teams, and product teams monitoring Ray-Ban Meta Smart Glasses feedback.

### Tech stack
- **Backend:** n8n, Claude AI (Anthropic), CSV + RSS
- **Frontend:** Streamlit, Plotly, Pandas
- **Data sources:** Meta-Glasses-Reviews.csv, Google News RSS feeds

---

**Creator:** Ishaan Samel  
**Email:** [ishaansamel@gmail.com](mailto:ishaansamel@gmail.com)
""")
