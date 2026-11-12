# Tech & Media Intelligence Cloud Engine ⚡

Autonomous high-throughput cloud harvester operating 100% on GitHub Actions (0% local disk/RAM). Streams and archives complete historical articles from top tech and Indian startup publications into partitioned private vaults.

---

## 🏛️ Storage Topology

| Publication | Scope | Total Volume | Target Vault | Format |
|---|---|---|---|---|
| **TechCrunch** | Global Tech & Silicon Valley (2005–2026) | ~2,63,300 articles | `parshant65-lang/tech-media-vault-1` (Private) | Compressed `.json.gz` |
| **Inc42** | Indian Startup Ecosystem & Tech VC | ~56,400 articles | `parshant65-lang/tech-media-vault-2` (Private) | Compressed `.json.gz` |
| **MediaNama** | Indian Digital Policy, Telecom & Tech | ~35,900 articles | `parshant65-lang/tech-media-vault-2` (Private) | Compressed `.json.gz` |

---

## ⚙️ Architecture & Features

1. **Parallel Execution Matrix**:
   - `harvest-techcrunch` job processes 5,000 articles per run into Vault 1.
   - `harvest-india-media` job processes Inc42 and MediaNama in parallel into Vault 2.
2. **Zero Local Resources**:
   - Runs in GitHub Azure Datacenter runners.
   - Local PC CPU / RAM usage: **0%**.
3. **Continuous Auto-Chain Loop**:
   - Automatically dispatches consecutive batches back-to-back until all ~3,55,000 articles are fully ingested.
   - Fallback cron triggers every 15 minutes to guarantee uninterrupted progress.
4. **Structured Schema**:
   - `id`: Unique post ID
   - `date` / `date_gmt`: ISO timestamp
   - `link`: Original URL
   - `title`: Clean rendered headline
   - `excerpt`: Summary
   - `content`: Complete full-text body
