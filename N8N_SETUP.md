# n8n Workflow Setup for Gradio Frontend

This guide explains how to modify your n8n workflow so the Gradio UI can connect to it as a frontend. The workflow remains the backend—data comes from CSV + 2 RSS feeds; Gradio triggers it and displays results.

## Architecture

```
[CSV] + [RSS 1] + [RSS 2] → n8n Workflow (sentiment + responses) → Respond to Webhook
                                                                    ↓
Gradio UI ← HTTP POST ←─────────────────────────────────────────────┘
```

## Step 1: Replace Manual Trigger with Webhook

1. Open your workflow in n8n
2. **Delete** the "When clicking 'Test workflow'" (Manual Trigger) node
3. Add a **Webhook** node:
   - Drag it to the canvas
   - Set **HTTP Method**: POST
   - Set **Path**: `meta-sentiment` (or any path you prefer)
   - Set **Respond**: "Using 'Respond to Webhook' node"
4. Connect the Webhook node to the same three nodes the manual trigger was connected to:
   - Read/Write Files from Disk
   - RSS Read
   - RSS Read1

## Step 2: Add Merge Node for Gradio Output

1. Add a **Merge** node
2. Set **Mode**: "Append"
3. Connect **Input 1** to: **Code in JavaScript2** (the node that outputs sentiment report data)
4. Connect **Input 2** to: **Code in JavaScript4** (the node that outputs personalized responses)

## Step 3: Add Code Node "Format for Gradio"

1. Add a **Code** node after the Merge node
2. Name it: `Format for Gradio`
3. Use this JavaScript:

```javascript
const items = $input.all();
if (items.length === 0) {
  return [{ json: { sentiment: {}, responses: [], error: "No data" } }];
}

// First item = sentiment aggregate from Code in JavaScript2
const sentimentItem = items[0].json;
// Rest = personalized response items from Code in JavaScript4
const responseItems = items.slice(1).map(i => i.json);

const output = {
  sentiment: {
    totalItems: sentimentItem.totalItems ?? 0,
    positiveCount: sentimentItem.positiveCount ?? 0,
    neutralCount: sentimentItem.neutralCount ?? 0,
    negativeCount: sentimentItem.negativeCount ?? 0,
    positivePercent: sentimentItem.positivePercent ?? 0,
    neutralPercent: sentimentItem.neutralPercent ?? 0,
    negativePercent: sentimentItem.negativePercent ?? 0,
    avgScore: sentimentItem.avgScore ?? 0,
    topThemes: sentimentItem.topThemes ?? {},
    topConcerns: sentimentItem.topConcerns ?? {},
    sourceBreakdown: sentimentItem.sourceBreakdown ?? {}
  },
  responses: responseItems.map(r => ({
    headline: r.headline,
    summary: r.summary ?? r.content_clean,
    source: r.source,
    ai_sentiment: r.ai_sentiment,
    ai_sentiment_score: r.ai_sentiment_score,
    ai_themes: r.ai_themes ?? [],
    ai_concerns: r.ai_concerns ?? [],
    personalized_response: r.personalized_response
  }))
};

return [{ json: output }];
```

4. Connect the Merge node output to this Code node

## Step 4: Add Respond to Webhook Node

1. Add a **Respond to Webhook** node
2. Set **Respond With**: "First Incoming Item"
3. Connect the "Format for Gradio" Code node to this node

## Step 5: Get Your Webhook URL

After saving and activating the workflow:

- **Local n8n**: `http://localhost:5678/webhook/meta-sentiment` (or your path)
- **n8n Cloud**: `https://your-instance.app.n8n.cloud/webhook/meta-sentiment`
- **Self-hosted**: `https://your-domain.com/webhook/meta-sentiment`

Paste this URL into the Gradio "n8n Webhook URL" field.

## Data Sources (Already Configured)

The workflow already uses:

- **CSV**: `/Users/ishaansamel/.n8n-files/Meta-Glasses-Reviews.csv` (Amazon reviews)
- **RSS 1**: Google News "Ray-Ban Meta"
- **RSS 2**: Google News "Ray-Ban Meta review OR Meta smart glasses review"

No changes needed—Gradio only displays the results; the workflow handles all data collection.
