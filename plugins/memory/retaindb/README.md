# RetainDB Memory Provider

Cloud memory API with hybrid search (Vector + BM25 + Reranking) and 7 memory types.

## Requirements

- RetainDB account ($20/month) from [retaindb.com](https://www.retaindb.com)
- `requests` is part of VAEL's core dependencies; no separate SDK install is needed. For damaged dependencies, use `vael pm repair` and restart VAEL.

## Setup

```bash
vael memory setup    # select "retaindb"
```

Or manually:
```bash
vael config set memory.provider retaindb
echo "RETAINDB_API_KEY=your-key" >> ~/.vael/.env
```

## Config

All config via environment variables in `.env`:

| Env Var | Default | Description |
|---------|---------|-------------|
| `RETAINDB_API_KEY` | (required) | API key |
| `RETAINDB_BASE_URL` | `https://api.retaindb.com` | API endpoint |
| `RETAINDB_PROJECT` | auto (profile-scoped) | Project identifier |

## Tools

| Tool | Description |
|------|-------------|
| `retaindb_profile` | User's stable profile |
| `retaindb_search` | Semantic search |
| `retaindb_context` | Task-relevant context |
| `retaindb_remember` | Store a fact with type + importance |
| `retaindb_forget` | Delete a memory by ID |
