# Edge Cases & Corner Scenarios

Edge-case catalog for the HDFC Mutual Fund FAQ Assistant, organized by **eleven implementation phases (Phase 0 → Phase 10)** per [implementation-plan.md](./implementation-plan.md).

**References:** [implementation-plan.md](./implementation-plan.md) · [architecture.md](./architecture.md) · [problemStatement.md](./problemStatement.md)

---

## Legend

| Column | Meaning |
|--------|---------|
| **Severity** | **S0** = must fix before release; **S1** = should fix; **S2** = acceptable with clear messaging |
| **Phase** | Implementation phase **0–10** when the scenario must be handled and tested |

---

## Quick index — 11 phases (0–10)

| Phase | Name | Plan |
|-------|------|------|
| **0** | Project bootstrap & config | [Phase 0](./implementation-plan.md#phase-0--project-bootstrap--configuration) |
| **1** | Corpus parsing, sectioning & chunking | [Phase 1](./implementation-plan.md#phase-1--corpus-parsing-sectioning--chunking) |
| **2** | Embedding & vector index | [Phase 2](./implementation-plan.md#phase-2--embedding--vector-index) |
| **3** | Query classifier & compliance | [Phase 3](./implementation-plan.md#phase-3--query-classifier--compliance) |
| **4** | Retriever & context | [Phase 4](./implementation-plan.md#phase-4--retriever--context-assembly) |
| **5** | RAG backend, generator, validator & API | [Phase 5](./implementation-plan.md#phase-5--rag-backend-generator-validator--chat-api) |
| **6** | Minimal chat UI | [Phase 6](./implementation-plan.md#phase-6--minimal-chat-ui) |
| **7** | Daily ingestion pipeline | [Phase 7](./implementation-plan.md#phase-7--daily-ingestion-pipeline) |
| **8** | Daily scheduler | [Phase 8](./implementation-plan.md#phase-8--daily-scheduler) |
| **9** | Tests | [Phase 9](./implementation-plan.md#phase-9--tests) |
| **10** | Documentation & deployment | [Phase 10](./implementation-plan.md#phase-10--documentation--deployment) |

---

## Phase 0 — Project Bootstrap

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| SE-06 | `.env` committed to git | Block/warn in docs | S1 | 0 |
| SC-02 | Alias “silver fund” in config | → `hdfc-silver-etf-fof` | S0 | 0 |
| SC-03 | Alias “gold FoF” | → `hdfc-gold-etf-fof` | S0 | 0 |
| SC-04 | Alias “Nifty 50 index” | → `hdfc-nifty-50-index` | S0 | 0 |
| SC-11 | ETF vs FoF in registry | FoF scheme only in allowlist | S1 | 0 |
| PH0-01 | Only 4 URLs in config | Fail phase exit gate | S0 | 0 |
| PH0-02 | Duplicate `scheme_id` | Config validation error | S0 | 0 |
| PH0-03 | Missing AMFI/SEBI URLs | Refusal links break later | S1 | 0 |
| PH0-04 | Alias missing “mid cap” | Add → `hdfc-mid-cap` | S0 | 0 |

---

## Phase 1 — Parsing & Chunking

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| IG-05 | Nav/calculator noise | Stripped from parsed output | S1 | 1 |
| IG-06 | Duplicate exit-load history | One canonical section per scheme | S1 | 1 |
| IG-07 | Import missing `Source URL` | Map filename → `scheme_id` | S0 | 1 |
| IG-12 | UTF-8 corruption | Normalize or skip with log | S2 | 1 |
| RT-04 | Conflicting exit-load text | Single canonical parse output | S1 | 1 |
| RT-05 | Duplicate identical chunks | Dedupe at chunk build (`data/chunks/`) | S2 | 1 |
| FM-10 | No `fund_management` in parse | Validation fails for scheme | S0 | 1 |
| CI-06 | NAV date in raw page | Extract for `last_updated` when possible | S2 | 1 |
| PH1-01 | Parsed file empty for scheme | Fail Phase 1 gate | S0 | 1 |
| PH1-02 | Section `costs` missing | Fail validation | S0 | 1 |
| PH1-03 | Wrong scheme in filename map | Reject or fix mapping | S0 | 1 |
| PH1-04 | Zero / too few chunks for scheme | Fail Phase 1 gate | S0 | 1 |
| IG-10 | Chunk missing `source_url` | Reject at chunk build | S0 | 1 |

**pytest:** `tests/test_parse.py`, `tests/test_chunk.py`, `tests/test_phase1_gate.py`

---

## Phase 2 — Embedding & Index

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| IG-10 | Chunk missing `source_url` | Re-validate at index upsert | S0 | 2 |
| PH2-01 | Only 4/5 schemes indexed | Fail exit gate | S0 | 2 |
| PH2-02 | Zero chunks for a scheme | Fail index build | S0 | 2 |
| PH2-03 | Embedding API failure | Abort; no partial wipe | S0 | 2 |
| PH2-04 | Chunk count below minimum | `test_ingestion` fails | S0 | 2 |
| PH2-09 | No vector store on disk | Block Phase 3+ until Phase 2 done | S0 | 2 |
| RT-02 | Query against empty index | 503 / unhealthy (when API exists) | S0 | 2 |

**pytest:** `tests/test_ingestion.py`

---

## Phase 3 — Classifier

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| CL-01 | “Should I invest?” | Refusal + AMFI/SEBI; no RAG | S0 | 3 |
| CL-02 | “Which fund is better?” | Refusal | S0 | 3 |
| CL-03 | “Is manager the best?” | Refusal | S0 | 3 |
| CL-04 | Fact + advisory blend | Refuse advisory | S0 | 3 |
| CL-05 | “3Y return?” | `PERFORMANCE_COMPARE` | S0 | 3 |
| CL-06 | Compare all five returns | Refusal | S0 | 3 |
| CL-08 | “Beat Nifty next year?” | Refusal | S0 | 3 |
| CL-09 | PAN in message | `PII` hard refuse | S0 | 3 |
| CL-10 | Phone/email/Aadhaar/OTP | `PII` hard refuse | S0 | 3 |
| CL-11 | PII + factual blend | Refuse entire message | S0 | 3 |
| CL-12 | Non-HDFC scheme | `OUT_OF_CORPUS` + list | S0 | 3 |
| CL-13 | HDFC scheme not in five | `OUT_OF_CORPUS` | S0 | 3 |
| CL-16 | Jailbreak / recommend | Refusal | S0 | 3 |
| CL-17 | Prompt injection | Ignored | S0 | 3 |
| CL-19 | “Fund is amazing, right?” | Refusal | S1 | 3 |
| CL-20 | “better” in “benchmark” | Factual path | S1 | 3 |
| CL-21 | “thoughts on investing…” | Refusal | S0 | 3 |
| CL-07 | “What is NAV?” | `FACTUAL` (handled in 4–5) | S1 | 3 |
| CL-14 | Capital gains download | `FACTUAL` if in corpus else N/A | S1 | 3 |
| CL-15 | ELSS on non-ELSS | `FACTUAL` → not found later | S1 | 3 |
| CL-18 | “Is exit load 1%?” | `FACTUAL` | S1 | 3 |
| CL-22 | AMFI/SEBI regulatory Q | Pointer only | S1 | 3 |
| FM-06 | “Is manager good?” | Refusal (classifier) | S0 | 3 |
| FM-07 | “Switch because of manager” | Refusal | S0 | 3 |
| MX-01 – MX-10 | Adversarial blends | Per class above | S0 | 3 |
| SE-04 | PII in logs | Redact patterns | S0 | 3 |

**pytest:** `tests/test_classifier.py`

---

## Phase 4 — Retriever

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| SC-01 | Full scheme name | Filter `scheme_id` | S0 | 4 |
| SC-05 | Generic “HDFC fund” | Clarify or best match | S1 | 4 |
| SC-06 | Gold vs silver expense | One-citation policy at gen | S1 | 4 |
| SC-07 | All five min SIP | Retrieve per scheme or clarify | S1 | 4 |
| SC-08 | Wrong scheme retrieved | Filter + threshold | S0 | 4 |
| SC-09 | Regular plan asked | Direct Growth scope | S1 | 4 |
| SC-10 | IDCW plan | Not found if absent | S2 | 4 |
| SC-12 | Groww URL in query | Parse allowlisted path | S2 | 4 |
| IN-06 | Hinglish query | Alias + retrieve | S1 | 4 |
| IN-07 | Typos in scheme name | Alias map | S1 | 4 |
| IN-09 | Two topics one message | Top-k covers primary | S1 | 4 |
| IN-10 | Pasted Groww page | Retrieve facts only | S1 | 4 |
| IN-14 | Gibberish | No chunks above threshold | S2 | 4 |
| RT-01 | Below similarity threshold | Not-found template path | S0 | 4 |
| RT-03 | Wrong section | Manager boost | S1 | 4 |
| RT-06 | Metric “--” on page | Not available | S1 | 4 |
| RT-07 | Embedding timeout | Retry → error | S0 | 4 |
| RT-10 | Tax + exit load | Top-k both sections | S1 | 4 |

**pytest:** `tests/test_retriever.py`

---

## Phase 5 — RAG Backend, Generator & API

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| GN-01 | 4+ sentences | Validator regenerate / fallback | S0 | 5 |
| GN-02 | No citation | Inject from top chunk | S0 | 5 |
| GN-03 | Multiple URLs | One allowlisted | S0 | 5 |
| GN-04 | Blog/Wikipedia link | Replace with corpus URL | S0 | 5 |
| GN-05 | Missing footer | Append footer | S0 | 5 |
| GN-06 | “recommend”, “should buy” | Block | S0 | 5 |
| GN-07 | Hallucinated ratio | Not in sources | S0 | 5 |
| GN-08 | Computed returns | Block unless verbatim | S0 | 5 |
| GN-09 | “best fund” ranking | Block | S0 | 5 |
| GN-10 | LLM timeout/429 | Safe error | S0 | 5 |
| GN-11 | Empty LLM output | Fallback | S1 | 5 |
| GN-12 | Bullet list | Sentence validator | S1 | 5 |
| GN-13 | Footer timezone | `INGEST_TIMEZONE` | S2 | 5 |
| GN-14 | Multiple managers | ≤3 sentences | S1 | 5 |
| GN-15 | Long “also manages” | Summarize + cite | S1 | 5 |
| FM-01 | Who manages? | Biographical facts | S0 | 5 |
| FM-02 | Education / experience | Corpus only | S0 | 5 |
| FM-03 | Other schemes managed | From chunk | S1 | 5 |
| FM-04 | Manager across funds | Correct scheme URL | S0 | 5 |
| FM-08 | Manager typo | Retrieval works | S2 | 5 |
| FM-09 | Co-managers | Both named | S1 | 5 |
| CI-01 | Factual citation | One of five Groww URLs | S0 | 5 |
| CI-02 | Refusal citation | AMFI/SEBI only | S0 | 5 |
| CI-03 | Official factsheet | Scheme Groww URL | S1 | 5 |
| CI-04 | hdfcfund.com | Prefer Groww scheme URL | S2 | 5 |
| AP-01 | Missing API key | Fail fast startup | S0 | 5 |
| AP-02 | Invalid API key | 503 on chat | S0 | 5 |
| AP-03 | Missing `message` | 422 | S1 | 5 |
| AP-07 | `GET /api/schemes` | 5 schemes | S1 | 5 |
| AP-09 | Corrupt vector store | Health fail | S0 | 5 |
| IN-02 | Whitespace message | 400 | S1 | 5 |
| IN-03 | Message >4k | Reject/limit | S1 | 5 |
| IN-04 | Single “?” | Clarify | S2 | 5 |
| IN-05 | Emoji-only | Clarify schemes | S2 | 5 |
| IN-08 | ALL CAPS | Case-insensitive | S2 | 5 |
| IN-12 | Repeated questions | Consistent answer | S2 | 5 |
| SE-03 | Log injection | Sanitize | S2 | 5 |

**pytest:** `tests/test_golden.py` (core, via TestClient)

---

## Phase 6 — Chat UI

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| IN-01 | Empty send | UI validation | S1 | 6 |
| IN-11 | HTML in user message | Escape on render | S1 | 6 |
| IN-13 | Follow-up without scheme | Prompt for scheme | S1 | 6 |
| UI-01 | API down | Error + retry | S1 | 6 |
| UI-02 | Slow >30s | Loading / timeout | S1 | 6 |
| UI-03 | Example chips | Predefined queries | S1 | 6 |
| UI-04 | Mobile disclaimer | Sticky disclaimer | S1 | 6 |
| UI-05 | Refusal styling | Distinct from answer | S1 | 6 |
| UI-06 | Citation click | `noopener` new tab | S2 | 6 |
| UI-07 | XSS in answer | Escape HTML | S0 | 6 |
| UI-08 | Double submit | Disable while loading | S2 | 6 |
| UI-09 | Long answer overflow | CSS wrap | S2 | 6 |
| AP-10 | API crash mid-request | Timeout in UI | S1 | 6 |
| PH6-01 | CORS misconfigured | Fix before demo | S0 | 6 |
| PH6-02 | Footer not rendered | Show API `footer` | S1 | 6 |
| PH6-03 | Markdown link not clickable | Render as `<a>` | S1 | 6 |

---

## Phase 7 — Daily Ingestion Pipeline

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| IG-01 | Fetch 403/503 | Backoff; fallback; keep index | S0 | 7 |
| IG-02 | Partial fetch 3/5 | Fail job; keep old index | S0 | 7 |
| IG-03 | HTML structure change | Tests fail; alert | S0 | 7 |
| IG-04 | Empty fetch body | Fail; keep index | S0 | 7 |
| IG-08 | Embed fail mid-reindex | Abort; keep index | S0 | 7 |
| IG-09 | Zero chunks after parse | Fail job | S0 | 7 |
| IG-11 | Empty fund_management post-fetch | Test failure | S0 | 7 |
| IG-13 | Groww rate limit | Delay between URLs | S1 | 7 |
| SK-01 | Overlapping ingest | Lock file | S0 | 7 |
| SK-02 | Ingest during traffic | Old index until swap | S1 | 7 |
| SK-03 | No atomic swap | Temp → swap | S1 | 7 |
| SK-04 | Disk full | Fail; keep index | S0 | 7 |
| RT-08 | Query during ingest | Old snapshot / 503 | S1 | 7 |
| AP-06 | Health during ingest | `ingesting: true` | S1 | 7 |
| CI-05 | Failed nightly ingest | Footer = last success | S1 | 7 |
| CI-07 | Groww 404 | Log in ingest | S2 | 7 |
| FM-05 | Manager change post-ingest | Updated after daily run | S1 | 7 |
| PH7-01 | Partial index write | Atomic swap only | S0 | 7 |
| PH7-03 | Chunk count drop >50% | Warn / fail job | S1 | 7 |
| PH7-04 | Lock file stale | TTL on lock | S1 | 7 |

**pytest:** `test_ingestion.py` (lock, swap, `run_daily` smoke)

---

## Phase 8 — Daily Scheduler

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| SK-05 | Cron not set (dev) | Manual `reindex.sh` OK | S1 | 8 |
| SK-06 | UTC vs IST | Document `INGEST_TIMEZONE` | S2 | 8 |
| SK-07 | Admin reindex during cron | 409 / lock | S1 | 8 |
| SK-08 | GitHub Actions on fork | Secrets documented | S2 | 8 |
| PH7-05 | Cron twice same minute | `flock` / lock | S1 | 8 |
| PH7-06 | README missing cron | Block release (Phase 10) | S1 | 8 |

**pytest:** manual cron smoke; lock interaction covered in Phase 7 `test_ingestion.py`

---

## Phase 9 — Tests

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| RT-09 | Wrong fact in golden | Per-scheme tests | S1 | 9 |
| AP-04 | Chat burst | Rate limit 429 | S1 | 9 |
| AP-08 | Open admin reindex | 401 / disabled | S0 | 9 |
| SE-01 | Scrape `/api/chat` | Rate limit | S1 | 9 |
| SE-02 | Token flooding | Limit + max length | S1 | 9 |
| SE-05 | Corpus exfiltration | Rate limit | S2 | 9 |
| PH7-02 | Golden CI flake | Stable thresholds | S1 | 9 |

**pytest:** full `test_golden.py` + expanded `test_ingestion.py`

---

## Phase 10 — Documentation & Deployment

| ID | Scenario | Expected behavior | Sev | Phase |
|----|----------|-------------------|-----|-------|
| AP-05 | Wrong CORS prod | Block; document allowed origins | S1 | 10 |
| PH7-06 | README missing cron | Block handoff | S1 | 10 |
| PH10-01 | Missing `vector_store/` on deploy | README: run `build_index` first | S0 | 10 |
| PH10-02 | `.env` not copied on new host | `.env.example` + deploy checklist | S1 | 10 |
| PH10-03 | API/UI different origins undocumented | CORS + static UI path in README | S1 | 10 |
| PH10-04 | Cron runs wrong working directory | `reindex.sh` sets `cd` to repo root | S1 | 10 |

**Manual:** fresh-machine README walkthrough; optional Docker compose up

---

## Golden test mapping by phase

```text
Phase 0: PH0-01, PH0-04, SC-02, SC-03, SC-04
Phase 1: FM-10, IG-07, PH1-01–04, RT-05, IG-10
Phase 2: PH2-01, PH2-04, SC-02 (retrieval)
Phase 3: CL-01, CL-02, CL-09, CL-12, CL-20, CL-21, MX-01, MX-02, MX-07
Phase 4: SC-08, RT-01, IN-06, IN-14
Phase 5: GN-01, GN-06, GN-07, FM-01, FM-06, CI-01, AP-03
Phase 6: UI-07, UI-04, PH6-01 (manual)
Phase 7: IG-01, SK-01, SK-04, PH7-01, CI-05
Phase 8: SK-05, SK-07, PH7-05
Phase 9: RT-09, PH7-02, AP-08, SE-01
Phase 10: PH7-06, AP-05, PH10-01, PH10-04
```

---

## Master registry (phase 0–10)

| Phase | Primary IDs |
|-------|-------------|
| **0** | SE-06, SC-02–04, SC-11, PH0-01–04 |
| **1** | IG-05–07, IG-12, RT-04, RT-05, FM-10, CI-06, PH1-01–04, IG-10 |
| **2** | PH2-01–04, PH2-09, RT-02 |
| **3** | CL-01–22, FM-06–07, MX-01–10, SE-04 |
| **4** | SC-01, SC-05–12, IN-06–10, IN-14, RT-01, RT-03, RT-06–07, RT-10 |
| **5** | GN-01–15, FM-01–04, FM-08–09, CI-01–04, AP-01–03, AP-07, AP-09, IN-02–05, IN-08, IN-12, SE-03 |
| **6** | UI-01–09, IN-01, IN-11, IN-13, AP-10, PH6-01–03 |
| **7** | IG-01–04, IG-08–09, IG-11, IG-13, SK-01–04, SK-02, RT-08, AP-06, CI-05, CI-07, FM-05, PH7-01, PH7-03, PH7-04 |
| **8** | SK-05–SK-08, PH7-05 |
| **9** | RT-09, AP-04, AP-08, SE-01–02, SE-05, PH7-02 |
| **10** | AP-05, PH7-06, PH10-01–04 |

---

## Phase coverage matrix

| Domain | P0 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 |
|--------|----|----|----|----|----|----|----|----|----|----|------|
| Config / setup | ● | | | | | | | | | | |
| Parse | | ● | | | | | | ● | | | |
| Index / embed | | | ● | | | | | ● | | | ● |
| Classifier | | | | ● | | | | | | | |
| Retriever | | | | | ● | | | | | | |
| Generator / API | | | | | | ● | | | | ● | ● |
| UI | | | | | | | ● | | | | ● |
| Ingestion / ops | | | | | | | | ● | | | ● |
| Scheduler | | | | | | | | | ● | | ● |
| Docs / deploy | | | | | | | | | | | ● |

---

## Response templates

| Situation | Template |
|-----------|----------|
| Not in corpus | That information isn’t available in our approved sources for this assistant. |
| Out of scope scheme | I can only answer about these five HDFC schemes: … |
| Advisory | I provide facts only, not investment advice. For learning, see [AMFI/SEBI]. |
| PII | Please don’t share personal or account details. Ask a factual question about a supported scheme. |
| Low retrieval | I couldn’t find a confident match. Try naming a scheme and topic (e.g., expense ratio). |
| System error | Something went wrong. Please try again in a moment. |
| Index missing (Phase 5+) | Assistant is temporarily unavailable. Please try again later. |

---

## References

- [implementation-plan.md](./implementation-plan.md) — eleven phases (0–10), exit gates
- [architecture.md](./architecture.md) — system design
- [problemStatement.md](./problemStatement.md) — compliance rules
