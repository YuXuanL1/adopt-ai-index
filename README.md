# AI Adoption Index — Parts 1, 1.5 and 2

| Part | Script | What it produces |
| --- | --- | --- |
| 1 — Sourcing & ethics | `src/part1_check_sources.py` | Source register: robots.txt check + flagged terms-of-use clauses per site |
| 1 — Sourcing & ethics | `src/part1_edgar_pull.py` | 10-K/10-Q/earnings 8-K/proxy filings per firm from SEC's official APIs (12 quarters; 16 for retirement firms) |
| 1.5 — Firm universe | `src/part15_build_universe.py` | Every firm tagged with the sectors it belongs to, each tag backed by cited evidence, plus a coverage report |
| 2 — Taxonomy | `src/part2_sample_docs.py` | Stratified 30–50 filing sample (draft, then frozen on approval) + coverage report |
| 2 — Taxonomy | `src/part2_extract_ai_passages.py` | Every AI passage with firm/quarter/form/section/page + a blank open-coding sheet |
| 2 — Taxonomy | `src/part2_taxonomy_doc.py` | The taxonomy document (deliverable, Markdown + Word) built from `data/taxonomy.csv`, with every cited passage checked |

## 1. Set up (once)

1. Open this folder in VS Code (**File → Open Folder…**). Install the **Python** extension if prompted.
2. In a terminal (**Terminal → New Terminal**):
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   Then **Ctrl/Cmd+Shift+P → Python: Select Interpreter → .venv**.
3. Copy `.env.example` to `.env` with your **team** name and a **shared team email**. SEC requires
   every automated request to say who is asking; the scripts refuse to run without it.
4. Check it works (no internet needed): `pytest`, or the flask icon (Testing panel).

## 2. Run, in this order

Every script is in **Run and Debug** (Ctrl/Cmd+Shift+D). Or in the terminal:

```bash
# Part 1a - save each site's terms of use by hand into data/terms/<source_id>.txt, then:
python src/part1_check_sources.py

# Optional RSS collection: only after you personally enter `approved` for the source
# in outputs/part1/source_register.csv and confirm the official feed URL.
python src/rss_pull.py --source businesswire --rss-url 'https://official-feed-url-here'

# Optional HTML web scraping: add only Terms-approved public URLs to data/web_targets.csv,
# change that source's access_method to web, then run:
python src/web_scrape.py

# Approved supplemental news metadata from GDELT (one firm first):
python src/gdelt_news.py --firms jpm

# Part 1.5 - tag the firm universe (run before the full pull: it sets each firm's backfill depth)
python src/part15_build_universe.py --firms jpm     # one firm
python src/part15_build_universe.py                 # all firms
python src/part15_build_universe.py --nlp-check     # add an NLP second opinion

# Part 1b - download filings
python src/part1_edgar_pull.py --dry-run            # list only
python src/part1_edgar_pull.py --firms jpm
python src/part1_edgar_pull.py                      # every SEC filer
```

Results land in `outputs/`. Everything downloaded is cached in `data/cache/`, so re-runs are fast.

## 3. How Part 1.5 decides a firm's sectors

The assignment asks for **every** sector a firm belongs to, not one. Tags come from evidence, and
each one records where it came from (`evidence` column):

1. **Business segments (main method).** Reads the firm's reportable segments and their full-year
   revenue from the XBRL data in its latest 10-K, maps each segment to sectors with the rules in
   `data/segment_rules.csv`, and tags a sector only if its segments are **≥10% of revenue** (SEC's own
   segment test). Example — JPMorgan: Consumer & Community Banking + Commercial & Investment Bank → bank
   (primary, largest share); Asset & Wealth Management → asset management + wealth; Corporate → none.
2. **SIC code** for single-segment firms (BlackRock, T. Rowe Price).
3. **Recordkeeping test** for the retirement tag. "Retirement plan provider" is a business line, not a
   segment or SIC code, so the script checks the 10-K's "Item 1. Business" for recordkeeping language
   about retirement plans. It must find "recordkeeping" in the same sentence as a plan word — so a bank's
   regulatory "recordkeeping requirements" or its own employee 401(k) don't count.
4. **Manual tags with a citation** for firms with no 10-K (Vanguard, Fidelity, TIAA, Nationwide,
   Betterment) and for traits no filing states (fintech/AI-native). Set in `data/firms.csv`.

**Primary sector** = the one with the largest revenue share.
**Checks:** your `hand_sectors` labels are compared with the evidence; any difference, unmapped segment,
segment under 10%, or missing citation is listed in `needs_review`. A person confirms `final_sectors`.
**`--nlp-check`** (optional): TF-IDF or embedding similarity between each firm's description and the
sector definitions; if it suggests a sector the evidence didn't give, the firm is flagged for review.

## 4. Refining the universe and coverage depth

The assignment says students should refine and expand the sectors and firms, and instructors should
adjust coverage to whichever chapter/sector needs the most depth. All of that is in data files — no code
changes:

| To… | Edit |
| --- | --- |
| Add or remove firms | `data/firms.csv` (CIK from SEC company search; leave blank for non-filers) |
| Add, split or drop a sector | `data/sector_plan.csv` (+ a definition in `data/sector_definitions.json` for the NLP check, and rules in `data/segment_rules.csv`) |
| Change how deep a sector goes | `data/sector_plan.csv`: `min_firms` and `backfill_quarters` (retirement defaults to 10+ firms, 16 quarters) |
| Turn on the optional pension sector | `data/sector_plan.csv`: `include = y` |
| Fix how a segment is read | `data/segment_rules.csv` — a row with a `firm_id` applies to that firm only and wins (e.g. MetLife's "Retirement & Income Solutions" is annuities → insurance, not recordkeeping) |

`outputs/part15/coverage_report.md` shows firms per sector against the plan and any shortfall.
`part1_edgar_pull.py` backfills each firm to the deepest depth among its sectors.
`data/segment_history.csv` records JPMorgan's Q2 2024 segment reorganization for later quarter-by-quarter coding.

## 5. Part 1 details

- `part1_check_sources.py` reads robots.txt (Python's `urllib.robotparser`), flags clauses in the terms you
  saved (scraping, AI/ML training, personal-use-only, reuse limits, APIs/RSS, rate limits, attribution) and
  writes `outputs/part1/source_register.csv` with an automatic recommendation and **blank human-decision
  columns** — a person reads `terms_evidence.csv` and decides.
- `polite_http.py` enforces the memo in code: declared User-Agent, 5 requests/second for SEC (1 per 5 s
  elsewhere), robots.txt checked before every page, everything cached, backoff on errors, and a request
  log in `outputs/compliance/`.
- Firm investor-relations sites are **not** scripted — their terms often forbid it (JPMorgan's do).
- `data/source_strategy.md` states which approved source types are primary evidence, supplemental
  evidence, or background only. It also adds Federal Reserve and FINRA material for regulatory context.

## 6. Limits to state in your methodology

- Segment-to-sector rules are judgment calls; they are in a file so they can be argued and changed.
- Segment revenue uses the 10-K's XBRL tags; if a firm tags revenue unusually, its segments come back
  empty and it falls to the SIC rule — check `needs_review`.
- Hand-entered tags for non-filers need a real citation before submission.
- Quarter labels are calendar quarters; firms with other fiscal years keep their real dates in the manifest.

## 7. Part 2 — Categorization taxonomy

Part 2 turns the filings into AI passages and a taxonomy built **from those passages** (not from the
starter list): **what the AI is used for** (`data/taxonomy.csv`), with inclusion/exclusion rules
and cited, paraphrased examples. Scoring (specificity, evidence, sentiment) and the inter-rater
check belong to Part 3. Nothing in Part 2 touches the network.

```bash
python src/part2_sample_docs.py                     # draft sample + coverage report (re-run freely)
python src/part2_sample_docs.py --freeze --reason "5 banks downloaded, approved by team"
python src/part2_extract_ai_passages.py             # passages + open_coding_sheet.csv
python src/part2_taxonomy_doc.py                    # outputs/part2/taxonomy_document.md + .docx
```

**Workflow.** (1) Freeze the sample. (2) Extract passages. (3) Each team member fills
`open_coding_sheet.csv` — a free-text `use_description` and a `proposed_category` per passage
(rows marked `duplicate` need no coding). (4) Revise `data/taxonomy.csv` from what you found.
(5) Re-run `part2_taxonomy_doc.py` to rebuild the taxonomy document — edit the CSVs, never the
document itself.

**Which filings are read.** The folder tree `data/raw/edgar/` is the source of truth (hard links to
`data/cache/`); `outputs/part1/edgar_manifest.csv` only adds dates and links, because
`part1_edgar_pull.py --firms X` rewrites it with firm X alone. Missing or empty files are listed,
never fatal. Each script prints a coverage table and warns about gaps: one firm only, one year only,
fewer than 30 documents, pilot banks with no filings.

**Sampling.** Unit = one filing (an 8-K's cover + EX-99.1 + EX-99.2 count as one). Strata = firm ×
form, with the per-firm numbers in `data/part2_sample_plan.csv` (10-K 2, 10-Q 2, 8-K 2, DEF 14A 1,
ARS 2 → 9 per bank, 45 for the 5 pilot banks); picks of a form are spread over different years.
Each firm × form has its own seeded random stream, so adding a bank later never changes the picks
for banks already sampled. The proxy (DEF 14A) and annual report (ARS, a PDF) are included because
most AI text sits there — a 10-Q usually has none.

**Freezing.** The default run writes `sample_manifest_draft.csv` only. `--freeze --reason` writes
`sample_manifest.csv` and refuses if one exists; replacing it takes `--freeze --resample --reason`,
which moves the old one to `outputs/part2/archive/` and logs the change in `sample_log.csv`.
Extraction uses the frozen sample if there is one; until then it reads every pilot filing on disk
and says so (`doc_set = all_available` on every row).

**Finding AI passages.** Terms are in `data/ai_keywords.csv`:
- `strong` terms always count. `AI` is case-sensitive and whole-word, so AGAINST, ABSTAIN, CHAIRMAN,
  "Said" and GlobalAI do not match (all occur in JPM proxies).
- `weak` terms (ML, algorithm, automation, predictive model, data science, RPA, virtual assistant)
  count only within 2 sentences of a strong term — e.g. the "automated valuation model" for home
  prices is not AI; at Bank of America "ML" means Merrill Lynch.
- `exclude` patterns veto hits inside them.

A passage is the hit sentence ± 1 sentence, and nearby hits merge up to 6 sentences
(`data/part2_settings.json`). The section is the nearest heading before the passage
(`data/part2_sections.csv`), and PDFs also keep the page number. The same text found twice — the
annual report reprints the 10-K's MD&A; risk factors repeat every year — gets `dup_of` = the
earliest passage, so it is coded once but still counted per filing later.

**The coding sheet is protected.** Re-running extraction keeps everything typed into
`open_coding_sheet.csv` (rows whose passage disappeared are kept as `orphaned`).

| To… | Edit |
| --- | --- |
| Add/remove AI terms or false-positive vetoes | `data/ai_keywords.csv` (quote a pattern that contains a comma) |
| Change how many filings per firm and form | `data/part2_sample_plan.csv` |
| Change seed, pilot firms, passage window | `data/part2_settings.json` |
| Fix section labels | `data/part2_sections.csv` |
| Revise categories, rules and examples | `data/taxonomy.csv` (+ `data/taxonomy_starter_crosswalk.csv`) |

### Taxonomy v0.1 (DRAFT — for team review)

Drafted with AI assistance from **JPMorgan only** — all 30 filings on disk on 2026-11-09, 147 unique
passages. It must be re-checked when the other four banks arrive. Each category has a definition,
include/exclude rules, three paraphrased and cited examples, and the passage ids that support it.

| ID | Category | AI use? | Starter list |
| --- | --- | --- | --- |
| C01 | Fraud, financial crime & KYC | yes | kept; transaction screening moved in from Compliance |
| C02 | Credit underwriting & decisioning | yes | kept (lending only) |
| C03 | Risk management & modelling | yes | kept; risks *of* AI split out to C12 |
| C04 | Markets, trading & capital optimization | yes | kept, broadened; thin evidence |
| C05 | Advice, sales & personalization | yes | **merged** client-facing advice + marketing |
| C06 | Customer service, onboarding & client tools | yes | kept, broadened |
| C07 | Operations & process automation | yes | kept |
| C08 | Software engineering | yes | **split** from HR/internal productivity |
| C09 | Employee productivity, knowledge & HR | yes | kept (minus coding) |
| C10 | Research & investment insights | yes | kept, narrowed |
| C11 | AI strategy, investment & capability | no | **new** — most "hype" text |
| C12 | AI risk, governance & regulation | no | **new** — dominates 10-K risk factors and proxies |
| C00 | Context only (not the firm's AI) | no | **new** — macro, policy, metaphors, glossary |

**No evidence in the sample:** portfolio construction/optimization, compliance surveillance and
regulatory reporting, insurance underwriting, AI for cyber-defence, customer chatbots. They stay
out of v0.1; re-test them with the other banks and sectors.

## 8. Part 2 limits to state in your methodology

- **One bank so far.** Only JPMorgan's filings were on disk when v0.1 was drafted (BAC, WFC, C and USB
  had not been downloaded), so the taxonomy describes how one firm talks about AI. Freeze the sample
  and revise the taxonomy once all five banks are present.
- **Where AI text lives.** In this sample, 10-Qs held almost no AI language and earnings 8-Ks only
  macro commentary; most concrete uses came from the annual-report shareholder letters, which are
  promotional and unaudited: they record what the firm *claims*, not verified deployment.
- **Keyword recall.** Uses described without any AI term ("models that flag suspicious payments") are
  missed, and weak terms are dropped unless a strong term is near. Precision is measurable (C00
  passages); recall is not.
- **Text quality.** PDF text keeps hyphenation and page headers ("work - flows"); flattened HTML tables
  can form one huge "sentence" (trimmed to 3,000 characters and marked `truncated`). Section labels are
  best-effort (nearest heading).
- **Duplicates.** Near-identical text (≥80% overlap, same firm) is coded once. Small year-to-year edits
  to boilerplate can hide inside a duplicate group — check `dup_score` when tracking wording changes.
- **Passage ids** come from accession + file + start position, so changing the window settings changes
  ids. Freeze the settings before the team starts coding.
- **The v0.1 draft was written with an AI assistant.** The team must review every definition, rule and
  paraphrase against the cited passages before submission.
