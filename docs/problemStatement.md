# Problem Statement: Mutual Fund FAQ Assistant (Facts-Only Q&A)

## Overview

The objective of this project is to build a **facts-only FAQ assistant** for mutual fund schemes, using **Groww** as the reference product context. The assistant answers objective, verifiable queries by retrieving information **exclusively** from a curated corpus of **five HDFC scheme pages** on Groww (see [Corpus Definition](#1-corpus-definition)). For advisory refusals, educational links may point to **AMFI** or **SEBI**.

The system must **not** provide investment advice, opinions, or recommendations. Every factual response must include a **single, clear source link** and follow defined constraints for clarity, accuracy, and compliance.

---

## Objective

Design and implement a lightweight **Retrieval-Augmented Generation (RAG)** assistant that:

- Answers factual queries about mutual fund schemes, including **fund management** information from the corpus
- Uses the curated corpus of five HDFC scheme pages on Groww
- Provides concise, source-backed responses

---

## Target Users

- **Retail investors** comparing mutual fund schemes
- **Customer support and content teams** handling repetitive mutual fund queries

---

## Scope of Work

### 1. Corpus Definition

- **AMC:** HDFC Mutual Fund
- **Corpus size:** **5** scheme pages on Groww (reference product context)
- **Scope:** The assistant is limited to factual information available on these URLs only

| # | Scheme | Source URL |
|---|--------|------------|
| 1 | HDFC Silver ETF FoF Direct Growth | [groww.in/.../hdfc-silver-etf-fof-direct-growth](https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth) |
| 2 | HDFC Mid Cap Fund Direct Growth | [groww.in/.../hdfc-mid-cap-fund-direct-growth](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) |
| 3 | HDFC Equity Fund Direct Growth | [groww.in/.../hdfc-equity-fund-direct-growth](https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth) |
| 4 | HDFC Gold ETF Fund of Fund Direct Plan Growth | [groww.in/.../hdfc-gold-etf-fund-of-fund-direct-plan-growth](https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth) |
| 5 | HDFC NIFTY 50 Index Fund Direct Growth | [groww.in/.../hdfc-nifty-50-index-fund-direct-growth](https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth) |

**Full URLs:**

1. https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth  
2. https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth  
3. https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth  
4. https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth  
5. https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth  

Typical facts retrievable from these pages include expense ratio, exit load, minimum SIP/lumpsum, riskometer, benchmark, tax implications, fund objective, and **fund management** details published on each scheme page (e.g., fund manager name(s), tenure, education, prior experience, and other schemes managed by the same manager).

### 2. FAQ Assistant Requirements

The assistant must answer **facts-only** queries, for example:

| Topic | Example query type |
|-------|-------------------|
| Costs | Expense ratio of a scheme |
| Redemption | Exit load details |
| Investment rules | Minimum SIP amount |
| Tax / lock-in | ELSS lock-in period |
| Risk | Riskometer classification |
| Benchmark | Benchmark index |
| Fund management | Who manages the fund, tenure, education, experience, and other schemes they manage |
| Operations | How to download statements or capital gains reports |

**Response rules:**

- Maximum **3 sentences** per answer
- Exactly **one** citation link per answer
- Footer on every answer: `Last updated from sources: <date>`

### 3. Refusal Handling

The assistant must **refuse** non-factual or advisory queries, such as:

- “Should I invest in this fund?”
- “Which fund is better?”
- “Is this fund manager the best choice for me?”

Refusal responses must:

- Be polite and clearly worded
- Reinforce the facts-only limitation
- Provide a relevant educational link (e.g., AMFI or SEBI resource)

### 4. User Interface (Minimal)

A simple interface with:

- A welcome message
- **Three** example questions
- A visible disclaimer: **“Facts-only. No investment advice.”**

---

## Constraints

### Data and Sources

- **Current corpus:** The **5 Groww scheme pages** listed in [Corpus Definition](#1-corpus-definition) only
- Citations in answers must point to one of these five URLs (or an official AMC/AMFI/SEBI link when refusing advisory queries)
- Do **not** use third-party blogs or other aggregator sites beyond this defined corpus

### Privacy and Security

Do **not** collect, store, or process:

- PAN or Aadhaar numbers
- Account numbers
- OTPs
- Email addresses or phone numbers

### Content Restrictions

- No investment advice or recommendations
- No performance comparisons or return calculations
- For performance-related queries: link to the **official factsheet only**
- **Fund management:** Answer only with factual biographical and tenure data from the corpus; do not rank managers, predict outcomes, or recommend switching funds based on manager quality

### Transparency

- Responses must be short, factual, and verifiable
- Every answer must include a **source link** and **last updated** date

---

## Expected Deliverables

| Deliverable | Contents |
|-------------|----------|
| **README** | Setup instructions; HDFC AMC and the 5 Groww scheme URLs above; architecture overview (RAG); known limitations |
| **Disclaimer snippet** | “Facts-only. No investment advice.” |

---

## Success Criteria

- Accurate retrieval of factual mutual fund information, including fund management data where present on the corpus pages
- Strict adherence to facts-only responses
- Consistent inclusion of valid source citations
- Proper refusal of advisory queries
- Clean, minimal, and user-friendly interface

---

## Summary

The goal is a **trustworthy, transparent, and compliant** mutual fund FAQ assistant that prioritizes **accuracy over intelligence**. Users should receive only **verified, source-backed** financial information—without advisory bias or speculative content.
