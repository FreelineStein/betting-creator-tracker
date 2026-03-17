# Pick Receipts — How to Submit Picks

Step-by-step instructions for adding picks to the Pick Receipts app.

---

## Prerequisites

- **Backend URL:** `https://believable-mindfulness-production-12eb.up.railway.app`
- **Admin API Key:** `Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo`
- All write endpoints require the admin key in the `Authorization: Bearer <key>` header.

---

## Step 1: Get Creator IDs

First, look up the creator you want to submit picks for:

```bash
curl https://believable-mindfulness-production-12eb.up.railway.app/api/v1/creators/
```

This returns a list of all creators. Find the `creator_id` for the creator you need. Current featured creators:

| Creator      | creator_id                             |
|-------------|----------------------------------------|
| Trent       | `3140d455-39ca-453c-bc36-dbbb4cb8772b` |
| DanAI       | `8b889814-f34d-4ff2-b377-173aa012095a` |
| Harry Locks | `254eb711-ba38-41e9-9aea-fa699892b100` |
| Gavin       | `5e27ae57-cd6b-4179-8485-acb6c914c5d8` |

---

## Step 2: Submit Picks from Tweets (Automatic Parsing)

If the creator posted picks in a tweet, use the tweet scraping endpoint. It will fetch the tweet text and use AI to automatically extract the picks.

```bash
curl -X POST https://believable-mindfulness-production-12eb.up.railway.app/api/v1/scrape/tweets \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo" \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "CREATOR_ID_HERE",
    "urls": [
      "https://x.com/username/status/1234567890"
    ]
  }'
```

**Notes:**
- You can submit up to 20 tweet URLs at once in the `urls` array.
- The endpoint fetches the tweet text via Twitter's oEmbed API, then uses Claude Haiku to parse out individual picks (spreads, moneylines, over/unders, props).
- Each parsed pick is stored with status `pending`.
- The response will show you what picks were extracted from each tweet.

**Example with a real tweet:**
```bash
curl -X POST https://believable-mindfulness-production-12eb.up.railway.app/api/v1/scrape/tweets \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo" \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "5e27ae57-cd6b-4179-8485-acb6c914c5d8",
    "urls": [
      "https://x.com/gavinmchughh/status/2032477572576202870"
    ]
  }'
```

---

## Step 3 (Alternative): Manually Create a Pick

If you want to enter a pick directly without a tweet URL:

```bash
curl -X POST https://believable-mindfulness-production-12eb.up.railway.app/api/v1/picks/ \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo" \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "CREATOR_ID_HERE",
    "sport": "NBA",
    "event": "Lakers vs Celtics",
    "event_date": "2026-03-17T00:00:00Z",
    "pick_type": "spread",
    "pick_detail": {
      "team": "Lakers",
      "line": "-3.5"
    },
    "odds": "-110",
    "units": 1.0,
    "status": "pending",
    "raw_text": "Lakers -3.5 tonight 🔒"
  }'
```

**Pick types and their `pick_detail` formats:**

| pick_type    | pick_detail fields                              | Example                                          |
|-------------|------------------------------------------------|--------------------------------------------------|
| `spread`     | `team`, `line`                                  | `{"team": "Lakers", "line": "-3.5"}`             |
| `moneyline`  | `team`                                          | `{"team": "Yankees"}`                            |
| `over_under` | `direction`, `total`                            | `{"direction": "Over", "total": "215.5"}`        |
| `prop`       | `player`, `prop`, `line`                        | `{"player": "LeBron", "prop": "points", "line": "27.5"}` |

**Status options:** `pending`, `won`, `lost`, `push`, `void`

---

## Step 4: Resolve Picks (Mark as Won/Lost)

Once a game is over, update the pick's status. This is the preferred method — it's instant and doesn't use any API credits.

**Mark a single pick as won:**
```bash
curl -X PATCH https://believable-mindfulness-production-12eb.up.railway.app/api/v1/picks/PICK_ID_HERE \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo" \
  -H "Content-Type: application/json" \
  -d '{"status": "won"}'
```

**Mark a pick as lost:**
```bash
curl -X PATCH https://believable-mindfulness-production-12eb.up.railway.app/api/v1/picks/PICK_ID_HERE \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo" \
  -H "Content-Type: application/json" \
  -d '{"status": "lost"}'
```

**Status options:** `won`, `lost`, `push`, `void`

You can also update other fields like `event`, `event_date`, `odds`, or `pick_detail` in the same request.

**After resolving picks, always recalculate the creator's record (Step 6).**

---

## Step 5: View Picks

To see all picks for a creator:

```bash
curl https://believable-mindfulness-production-12eb.up.railway.app/api/v1/picks/?creator_id=CREATOR_ID_HERE
```

You can also filter by sport or status:

```bash
curl "https://believable-mindfulness-production-12eb.up.railway.app/api/v1/picks/?creator_id=CREATOR_ID_HERE&sport=NBA&status=pending"
```

---

## Step 6: Recalculate a Creator's Record

After picks are resolved (status changed from `pending` to `won`/`lost`/`push`), recalculate the creator's W/L record:

```bash
curl -X POST https://believable-mindfulness-production-12eb.up.railway.app/api/v1/creators/CREATOR_ID_HERE/record/recalculate \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo"
```

---

## Typical Workflow

1. Find a tweet where a creator posted their picks
2. Copy the tweet URL
3. Use Step 2 to submit the tweet — picks are auto-extracted with status `pending`
4. Check the frontend at https://pick-receipts.vercel.app to see the picks appear
5. Once the game is over, use Step 4 to resolve each pick as `won`, `lost`, or `push`
6. Use Step 5 to find pick IDs if needed (filter by `status=pending` to see unresolved picks)
7. Use Step 6 to recalculate the creator's W/L record
8. The frontend updates automatically on next page load

### Quick Reference: Resolve All Pending Picks for a Creator

```bash
# 1. List pending picks
curl "https://believable-mindfulness-production-12eb.up.railway.app/api/v1/picks/?creator_id=CREATOR_ID_HERE&status=pending"

# 2. For each pick_id, resolve it
curl -X PATCH https://believable-mindfulness-production-12eb.up.railway.app/api/v1/picks/PICK_ID \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo" \
  -H "Content-Type: application/json" \
  -d '{"status": "won"}'

# 3. Recalculate the record
curl -X POST https://believable-mindfulness-production-12eb.up.railway.app/api/v1/creators/CREATOR_ID_HERE/record/recalculate \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo"
```

---

## Troubleshooting

- **401 Unauthorized:** Check that the `Authorization: Bearer` header has the correct admin key
- **404 Creator not found:** Run Step 1 to get the correct creator_id
- **oEmbed failed:** The tweet URL may be invalid or the tweet may be deleted/private
- **No picks extracted:** The LLM couldn't parse picks from the tweet text — try the manual method (Step 3) instead
- **Picks stuck on pending:** The auto-resolver requires `event_date` to be set and Odds API credits to be available. Use Step 4 to manually resolve instead — it's faster and free

---

## Deleting Picks or Creators

**Delete a pick:**
```bash
curl -X DELETE https://believable-mindfulness-production-12eb.up.railway.app/api/v1/picks/PICK_ID_HERE \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo"
```

**Delete a creator (and all their picks/records):**
```bash
curl -X DELETE https://believable-mindfulness-production-12eb.up.railway.app/api/v1/creators/CREATOR_ID_HERE \
  -H "Authorization: Bearer Bh6UnqBDMiPbD9YxSk8tx2yftYCmCsStWbUEYuwQzvo"
```
