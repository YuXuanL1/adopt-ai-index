# AI-Use Categorization Taxonomy — v0.1-DRAFT - for team review

_Generated 2026-11-09 by `src/part2_taxonomy_doc.py` from `data/taxonomy.csv` and `data/taxonomy_starter_crosswalk.csv`. Edit those files and re-run; do not edit this document by hand._

> **Status.** Draft for team review. Built from all filings on disk (sample not frozen yet) for **JPM** only. Categories must be re-checked when the other pilot banks are added.

## 1. Purpose and unit of analysis

The taxonomy classifies **AI passages** — a sentence that mentions AI plus one sentence either side, merged when hits are close — taken from SEC filings. Each passage gets **one** category: what the AI is used for. It is built to separate firms *using* AI from firms *talking about* AI, so it has two kinds of category:

- **AI-use categories** (C01, C02, C03, C04, C05, C06, C07, C08, C09, C10): the passage names a business function where the firm applies AI.
- **Non-use categories** (C11, C12, C00): AI is mentioned, but no specific use is the subject — strategy and spending, risks and governance, or text that is not about the firm's own AI at all. These are kept, not discarded, so later parts can measure how much AI text is talk rather than use.

## 2. How it was built

1. **Documents.** Filings already downloaded in Part 1 (10-K, 10-Q, earnings 8-K, proxy DEF 14A, annual report ARS). AI terms were found in 14 documents.
2. **Passages.** A keyword list (`data/ai_keywords.csv`) found 165 AI passages; 147 remain after removing repeated text (e.g. the annual report reprinting the 10-K). Unique passages by form: 10-K 19, 8-K 2, ARS 88, DEF 14A 38.
3. **Open coding.** Unique passages were read and their AI use described in free text before any category list was applied. For this draft that pass was done with AI assistance; the team's own open coding (`outputs/part2/open_coding_sheet.csv`) is the check on it.
4. **Grouping.** Similar uses were grouped into categories, then compared with the assignment's starter list: categories were kept, merged, split, or added when the filings required it (section 6). Uses with no supporting passage were not adopted (section 7).
5. **Rules.** Each category got inclusion/exclusion rules written from the boundary cases met in coding, and 2–3 paraphrased examples cited to the filing, page/section and passage id.

## 3. Categories at a glance

| ID | Category | AI use? | Definition | Supporting passages |
|---|---|---|---|---|
| C01 | Fraud, financial crime & KYC | yes | AI used to detect or prevent fraud, screen transactions (sanctions/AML) and run know-your-customer due diligence. | 8 |
| C02 | Credit underwriting & decisioning | yes | AI used in deciding whether, how much and at what terms to lend (consumer, mortgage, card, commercial). | 4 |
| C03 | Risk management & modelling | yes | AI/ML used to measure, monitor or manage the firm's own market, credit, liquidity or operational risk, incl. valuation and stress-testing models and 'risk intelligence'. | 6 |
| C04 | Markets, trading & capital optimization | yes | AI used in trading, pricing, securities inventory, execution or optimizing the trading balance sheet and capital. | 3 |
| C05 | Advice, sales & personalization | yes | AI that decides or suggests what to offer or recommend to clients - delivered straight to clients (personalization, robo-advice, marketing) or through advisors and bankers (next-best-action and prospecting tools). | 10 |
| C06 | Customer service, onboarding & client tools | yes | AI used to serve clients' existing needs: contact-centre support, routing, faster onboarding, and AI features inside tools clients use themselves (e.g. cash-flow forecasting). | 5 |
| C07 | Operations & process automation | yes | AI used to run back- and middle-office processes: payments and trade processing, document handling, workflow, removing manual steps, operations productivity. | 6 |
| C08 | Software engineering | yes | AI used to write, test or maintain the firm's own software (coding assistants, developer tools). | 5 |
| C09 | Employee productivity, knowledge & HR | yes | General-purpose AI given to employees (LLM platforms, assistants, knowledge search, drafting/summarizing), plus AI used in HR processes such as training or recruiting. | 6 |
| C10 | Research & investment insights | yes | AI used to produce or speed up research and investment analysis: reading reports and documents, generating insights for investors or analysts. | 5 |
| C11 | AI strategy, investment & capability | no | Statements about the firm's AI ambition, spending, data/cloud readiness, AI talent and organization, number of use cases or overall AI value - with NO specific business use as the subject. | 14 |
| C12 | AI risk, governance & regulation | no | Text about risks created by AI (failures, bias, misuse, AI-enabled attacks, workforce displacement, competition), AI regulation, and how the board and management oversee AI. | 14 |
| C00 | Context only (not the firm's AI) | no | AI is mentioned but the passage is not about the firm's own AI use, strategy or governance. | 16 |

_Supporting passages = passages linked to the category while drafting; not a full count._

## 4. How to assign a category

Give each passage the **one** category it says most about. Work through these questions in order:

1. Is the passage about **this firm's own** AI (its use, plans, spending, risks or oversight)? If not — macro commentary, public policy, AI companies as clients, metaphors, glossary — code **C00**.
2. Does it name a **specific business use** of AI as its main subject? Code that use (**C01–C10**), even if strategy words appear around it. If several uses are named, pick the one described most.
3. Is it about **risks created by AI**, AI regulation or **oversight** of AI? Code **C12**.
4. Otherwise — ambition, budgets, data readiness, talent, use-case counts, rankings — code **C11**.

Judge only from the passage text. Automation, algorithms or models with **no AI term** in the passage are not AI. Boundary rules for each category are in section 5.

## 5. Category definitions

### C01 — Fraud, financial crime & KYC

**Definition.** AI used to detect or prevent fraud, screen transactions (sanctions/AML) and run know-your-customer due diligence.

**Include:**

- Fraud scoring or prediction
- Transaction or sanctions screening
- AML alert triage
- KYC/client due-diligence checks
- Identity verification done BY the firm with AI.

**Exclude:**

- AI-enabled attacks or identity fraud BY criminals (-> C12 risk).
- Speed or experience of account opening without a KYC/screening angle (-> C06).
- Cyber-defence with no fraud angle (no category yet - note it).

**Examples (paraphrased):**

1. The investment bank says AI has let it handle over twice as many transaction-screening reviews while cutting manual operator checks by half.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 64; passage jpm-2026-annual-ARS-1eecf2_
2. AI/ML in KYC work is credited with cutting unit costs by close to 40%, and with cheaper, more effective sanctions screening and fraud protection.  
   _Source: JPMorganChase 2024 Annual Report (ARS, filed 2025-04-07, acc. 0000019617-25-000326), PDF p. 73; passage jpm-2025-annual-ARS-9f9a95_
3. The consumer bank says its AI work started in risk areas such as fraud detection more than ten years ago.  
   _Source: JPMorganChase 2024 Annual Report (ARS, filed 2025-04-07, acc. 0000019617-25-000326), PDF p. 69; passage jpm-2025-annual-ARS-c34dea_

**Relation to starter list:** Fraud detection & AML/KYC (kept; transaction screening from 'Compliance' moved here)

**Note for reviewers:** Strongest operational evidence in the sample: two passages state quantified results.

### C02 — Credit underwriting & decisioning

**Definition.** AI used in deciding whether, how much and at what terms to lend (consumer, mortgage, card, commercial).

**Include:**

- Underwriting models
- Credit decisioning
- Loan-origination AI
- Credit-line or pricing decisions on loans.

**Exclude:**

- 'Automatically decisioned' applications with no AI term in the passage (rules engines are not AI unless stated).
- Credit-RISK measurement of the existing book (-> C03).
- Insurance underwriting (no evidence in banks; add a sub-tag if insurers join).

**Examples (paraphrased):**

1. The consumer bank says it applies data and AI-enabled techniques to refine underwriting and credit decisions across its mortgage business.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 67; passage jpm-2024-annual-ARS-a71ca4_
2. Home Lending ties its spending on technology, data and AI to better sales and underwriting and faster time to market.  
   _Source: JPMorganChase 2024 Annual Report (ARS, filed 2025-04-07, acc. 0000019617-25-000326), PDF p. 68; passage jpm-2025-annual-ARS-aaca57_
3. The consumer bank describes predictive AI/ML in credit as a mature, established use case.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 59; passage jpm-2026-annual-ARS-461216_

**Relation to starter list:** Underwriting (kept, narrowed to lending)

### C03 — Risk management & modelling

**Definition.** AI/ML used to measure, monitor or manage the firm's own market, credit, liquidity or operational risk, incl. valuation and stress-testing models and 'risk intelligence'.

**Include:**

- Risk measurement and stress testing with ML
- Model-risk frameworks that state the firm uses ML/AI models
- AI that flags operational or control issues early.

**Exclude:**

- Risks CAUSED BY AI (bias, AI failures, AI regulation -> C12).
- Fraud and screening (-> C01).
- Credit decisions on new loans (-> C02).

**Examples (paraphrased):**

1. The 10-K's model-risk section says the firm uses estimation models, some built on ML or AI, across businesses for valuation, risk measurement, capital and stress tests.  
   _Source: JPMorganChase 10-K FY2024 (filed 2025-02-14, acc. 0000019617-25-000270), MD&A (Estimations and Model Risk Management); passage jpm-2024Q4-10-K-4c8cb2_
2. The pay narrative for a senior executive credits AI and ML with improving workflows and risk intelligence.  
   _Source: JPMorganChase 2025 Proxy Statement (DEF 14A, filed 2025-04-07, acc. 0000019617-25-000321), Executive compensation; passage jpm-2025-annual-DEF14A-5992a6_
3. Asset & Wealth Management says it uses AI in part to streamline processing and manage risk, alongside routine stress testing of client portfolios.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 79; passage jpm-2024-annual-ARS-d6cdd3_

**Relation to starter list:** Risk management (kept; risks OF AI split out to C12)

**Note for reviewers:** Overlaps C12 in risk-factor text: ask 'is the firm using AI to manage risk (C03) or describing a risk that AI creates (C12)?'

### C04 — Markets, trading & capital optimization

**Definition.** AI used in trading, pricing, securities inventory, execution or optimizing the trading balance sheet and capital.

**Include:**

- Algorithmic or AI-assisted trading and execution
- Pricing
- Securities-financing inventory
- Capital/balance-sheet optimization in Markets.

**Exclude:**

- Client-facing recommendations from Markets data (-> C05).
- 'Algorithmic trading' with no AI term nearby (not AI unless stated).
- Research reports (-> C10).

**Examples (paraphrased):**

1. The 2023 letter says Prime Finance was starting to apply AI to manage the securities inventory held for clients while using the balance sheet more efficiently.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 73; passage jpm-2024-annual-ARS-bc8c3e_
2. By 2025 Prime Finance is described as using AI for inventory, sharper pricing, risk and capital efficiency.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 64; passage jpm-2026-annual-ARS-9be90e_
3. Listed AI use cases include tools that optimize how capital is used in the trading business.  
   _Source: JPMorganChase 2024 Annual Report (ARS, filed 2025-04-07, acc. 0000019617-25-000326), PDF p. 73; passage jpm-2025-annual-ARS-a5c7d4_

**Relation to starter list:** Trading & execution (kept, broadened to capital optimization)

**Note for reviewers:** Thin evidence (3 passages); watch whether other banks support a separate category.

### C05 — Advice, sales & personalization

**Definition.** AI that decides or suggests what to offer or recommend to clients - delivered straight to clients (personalization, robo-advice, marketing) or through advisors and bankers (next-best-action and prospecting tools).

**Include:**

- Personalized offers and experiences
- Marketing targeting
- Pricing of products for customers
- Robo-advice
- Advisor/banker tools that surface client opportunities, prepare meetings or suggest ideas (e.g. Connect Coach, Sales Assist).

**Exclude:**

- Servicing an existing request (-> C06).
- Investment research for portfolio managers (-> C10).
- General employee GenAI tools not aimed at selling/advising (-> C09).

**Examples (paraphrased):**

1. Wealth advisors get AI tools (named Connect Coach and Sales Assist), and more than 80% of AWM front-office staff are said to use the firm's LLM Suite.  
   _Source: JPMorganChase 2024 Annual Report (ARS, filed 2025-04-07, acc. 0000019617-25-000326), PDF p. 76; passage jpm-2025-annual-ARS-4ea7a7_
2. Connect Coach reportedly reaches about 12,000 advisors with 25 specialized AI agents, pushing roughly a million tailored insights to help prospect and prepare client meetings.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 69; passage jpm-2026-annual-ARS-405104_
3. The consumer bank says its AI focus moved from cutting cost and risk toward revenue growth, with data used to personalize at scale.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 67; passage jpm-2024-annual-ARS-88c2aa_

**Relation to starter list:** MERGES 'Client-facing advice' + 'Marketing': the filings discuss personalization, sales and advice together and rarely separate them

**Note for reviewers:** If coders keep splitting C05 into advice vs marketing, split it in v0.2.

### C06 — Customer service, onboarding & client tools

**Definition.** AI used to serve clients' existing needs: contact-centre support, routing, faster onboarding, and AI features inside tools clients use themselves (e.g. cash-flow forecasting).

**Include:**

- Chatbots / virtual assistants for customers
- Call prediction and routing
- Agent-assist in service
- Onboarding speed and experience
- AI features in client treasury or banking tools.

**Exclude:**

- KYC/screening checks during onboarding (-> C01).
- Tools that recommend products (-> C05).
- Internal employee assistants (-> C09).

**Examples (paraphrased):**

1. Service specialists are said to be supported by AI for predicting calls, giving real-time insights and routing calls intelligently.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 67; passage jpm-2024-annual-ARS-979411_
2. The commercial bank says it already applies AI to bring customers on board faster and to give clients more insight.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 69; passage jpm-2024-annual-ARS-27a5ef_
3. Corporate treasury clients are said to have a cash-flow-forecasting tool to help manage liquidity.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 64; passage jpm-2026-annual-ARS-9be90e_

**Relation to starter list:** Customer service (kept, broadened with onboarding and client tools)

**Note for reviewers:** Passage 979411 also names fraud: apply the primary-use rule.

### C07 — Operations & process automation

**Definition.** AI used to run back- and middle-office processes: payments and trade processing, document handling, workflow, removing manual steps, operations productivity.

**Include:**

- Workflow automation with AI
- Eliminating manual processes with AI
- Document processing
- Reconciliation
- Operations-wide productivity targets tied to AI.

**Exclude:**

- Automation with NO AI term in the passage (RPA, 'automated' rules - not AI).
- Screening/KYC operations (-> C01).
- Software development (-> C08).

**Examples (paraphrased):**

1. A senior executive's pay narrative credits AI capabilities and workflow tools with removing manual processes and improving risk intelligence.  
   _Source: JPMorganChase 2025 Proxy Statement (DEF 14A, filed 2025-04-07, acc. 0000019617-25-000321), Executive compensation; passage jpm-2025-annual-DEF14A-c3ee31_
2. The consumer bank reports AI/ML value up almost 60% year on year and names Operations as the lead area, with a goal of over 40% gross productivity efficiency by 2030.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 59; passage jpm-2026-annual-ARS-672c24_
3. AWM mentions applying AI to streamline trade, transaction and money-movement processing.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 79; passage jpm-2024-annual-ARS-d6cdd3_

**Relation to starter list:** Back-office/operations (kept)

**Note for reviewers:** Note 672c24: the 40% figure is a 2030 TARGET (not a realized result); the 60% figure is stated realized value.

### C08 — Software engineering

**Definition.** AI used to write, test or maintain the firm's own software (coding assistants, developer tools).

**Include:**

- AI coding assistants
- Developer-productivity figures
- GenAI in the software-development life cycle.

**Exclude:**

- Firm-wide GenAI platforms used for general tasks (-> C09).
- Tech spending or cloud migration with no AI use named (-> C11).

**Examples (paraphrased):**

1. Engineers are reported to gain roughly 10-20% productivity across the development life cycle from AI coding assistants.  
   _Source: JPMorganChase 2024 Annual Report (ARS, filed 2025-04-07, acc. 0000019617-25-000326), PDF p. 62; passage jpm-2025-annual-ARS-dfbffe_
2. More than nine in ten engineers in the investment bank are said to use AI code assistants.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 64; passage jpm-2026-annual-ARS-9be90e_
3. In 2024 the CEO named software engineering as one of the areas where the firm was exploring generative AI.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 19; passage jpm-2024-annual-ARS-d5b7f5_

**Relation to starter list:** SPLIT from 'HR/internal productivity': coding is named often, has its own metrics, and shows a clear pilot -> deployment -> impact path

**Note for reviewers:** Nice evolution example for the index: exploring in 2024, a productivity figure in 2025.

### C09 — Employee productivity, knowledge & HR

**Definition.** General-purpose AI given to employees (LLM platforms, assistants, knowledge search, drafting/summarizing), plus AI used in HR processes such as training or recruiting.

**Include:**

- Enterprise GenAI/LLM platforms (e.g. LLM Suite)
- Employee assistants and agents
- Knowledge tools
- AI-delivered training (e.g. role plays)
- Recruiting with AI.

**Exclude:**

- Training employees ABOUT AI or hiring AI talent (-> C11: building capability, not using AI).
- Coding tools (-> C08).
- Tools whose purpose is selling/advising clients (-> C05).

**Examples (paraphrased):**

1. The firm says it gave its in-house generative AI platform, LLM Suite, to over 200,000 staff in 2024, inside a controlled environment that protects data.  
   _Source: JPMorganChase 2024 Annual Report (ARS, filed 2025-04-07, acc. 0000019617-25-000326), PDF p. 62; passage jpm-2025-annual-ARS-f707ca_
2. The firm says it recently launched an AI-powered Employee Assistant agent as a single place for staff to get help and complete tasks.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 52; passage jpm-2026-annual-ARS-cabfd5_
3. Private-bank advisor training now uses AI-driven role plays; practice volume rose while cost per advisor trained fell by about a quarter.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 68; passage jpm-2026-annual-ARS-9ae227_

**Relation to starter list:** HR/internal productivity (kept minus coding)

**Note for reviewers:** In 9ae227 the cost drop is not attributed to AI alone.

### C10 — Research & investment insights

**Definition.** AI used to produce or speed up research and investment analysis: reading reports and documents, generating insights for investors or analysts.

**Include:**

- Research assistants
- Document/report summarization for investment decisions
- Insight-generation tools for portfolio managers or research staff
- Stewardship data analysis.

**Exclude:**

- Insights pushed to advisors to sell or deepen relationships (-> C05).
- Firm-level macro commentary about AI (-> C00).

**Examples (paraphrased):**

1. Asset Management introduced a proprietary generative tool (GPT-Insights) to speed up its investors' research process.  
   _Source: JPMorganChase 2024 Annual Report (ARS, filed 2025-04-07, acc. 0000019617-25-000326), PDF p. 76; passage jpm-2025-annual-ARS-ed64a6_
2. An investor AI assistant called Smart Monitor reportedly ranks and pushes insights in real time, cutting time-to-insight by about 80%.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 69; passage jpm-2026-annual-ARS-405104_
3. AWM describes an AI research capability covering about 90,000 securities and 22 million documents.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 69; passage jpm-2026-annual-ARS-4b8596_

**Relation to starter list:** Research & analytics (kept, narrowed to research for investment decisions)

### C11 — AI strategy, investment & capability _(not an AI use)_

**Definition.** Statements about the firm's AI ambition, spending, data/cloud readiness, AI talent and organization, number of use cases or overall AI value - with NO specific business use as the subject.

**Include:**

- AI as a strategic priority
- AI budgets/investment
- Data and cloud 'for AI'
- AI teams, hires, Chief Data & Analytics Officer
- Training staff on AI
- Firm-wide use-case counts
- External AI rankings
- Firm-wide AI value claims.

**Exclude:**

- If a specific use is the main subject, code that use (C01-C10) even if strategy words appear.
- Risks/governance of AI (-> C12).

**Examples (paraphrased):**

1. The firm created a Chief Data & Analytics Officer role on its Operating Committee, citing how much it expects AI to shape the business.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 19; passage jpm-2024-annual-ARS-df0bdc_
2. After ten-plus years of ML/AI work, the firm states measurable value in credit, fraud and personalization alongside a roughly $19.8bn 2026 technology budget.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 52; passage jpm-2026-annual-ARS-ccdbd4_
3. The annual-report highlights cite a #1 ranking for AI capability on an external industry index.  
   _Source: JPMorgan Chase 2023 Annual Report (ARS, filed 2024-04-08, acc. 0000019617-24-000278), PDF p. 2; passage jpm-2024-annual-ARS-aab5bf_

**Relation to starter list:** NEW - not in the starter list. Captures most 'hype' text, so the index can separate talk from use

**Note for reviewers:** Not an AI USE: exclude from use-category breadth in Part 3, but keep for mention density.

### C12 — AI risk, governance & regulation _(not an AI use)_

**Definition.** Text about risks created by AI (failures, bias, misuse, AI-enabled attacks, workforce displacement, competition), AI regulation, and how the board and management oversee AI.

**Include:**

- Risk factors about AI
- AI-enabled cyber or identity attacks by others
- AI regulation
- Board/committee oversight of AI
- Director AI expertise
- Shareholder engagement on AI
- Responsible-AI controls.

**Exclude:**

- The firm USING AI to manage risk (-> C03) or fight fraud (-> C01).

**Examples (paraphrased):**

1. The 2024 risk factors warn that biased or misleading AI output could cause harm such as discriminatory lending, fraud or privacy breaches, damaging reputation.  
   _Source: JPMorganChase 10-K FY2024 (filed 2025-02-14, acc. 0000019617-25-000270), Item 1A Risk Factors; passage jpm-2024Q4-10-K-5e7ebb_
2. The 2025 risk factors add a full list of generative/agentic AI risks: failures, opaque or biased output, insufficient testing and controls.  
   _Source: JPMorganChase 10-K FY2025 (filed 2026-02-13, acc. 0001628280-26-008131), Item 1A Risk Factors; passage jpm-2025Q4-10-K-e596b6_
3. The proxy says the full Board oversees AI matters, with the Audit and Risk Committees overseeing related controls.  
   _Source: JPMorganChase 2026 Proxy Statement (DEF 14A, filed 2026-04-06, acc. 0000019617-26-000096), Board oversight; passage jpm-2026-annual-DEF14A-49df1b_

**Relation to starter list:** NEW - not in the starter list. Regulation OF AI was folded out of 'Compliance & regulatory'

**Note for reviewers:** Risk-factor wording repeats yearly - code the duplicate group once (dup_of).

### C00 — Context only (not the firm's AI) _(not an AI use)_

**Definition.** AI is mentioned but the passage is not about the firm's own AI use, strategy or governance.

**Include:**

- Macro/economic commentary (AI capex, AI energy demand)
- Public policy and geopolitics of AI
- The firm financing or researching AI COMPANIES as a market
- Third-party shareholder proposals
- Glossary entries
- Metaphors.

**Exclude:**

- Anything about the firm's own AI plans, spending, use or risks (C01-C12).

**Examples (paraphrased):**

1. The CEO's quarterly comment lists AI-driven capital investment among the tailwinds supporting the U.S. economy.  
   _Source: JPMorganChase Q1 2026 earnings release (8-K EX-99.1, filed 2026-04-14, acc. 0001628280-26-024990), EX-99.1; passage jpm-2026Q1-8-K-a5c082_
2. The CEO letter discusses the hyperscalers' AI capital spending and its likely short-term inflationary effect.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 33; passage jpm-2026-annual-ARS-2316f7_
3. The CEO calls the firm a 'neural network' of its people - a metaphor about culture, a keyword false positive.  
   _Source: JPMorganChase 2025 Annual Report (ARS, filed 2026-04-06, acc. 0001628280-26-023927), PDF p. 29; passage jpm-2026-annual-ARS-a3ab9d_

**Relation to starter list:** NEW - needed because these passages pass the keyword filter

**Note for reviewers:** Kept so the false-positive rate of the keyword list is measurable.

## 6. Changes from the starter list

| Starter category | v0.1 | Decision | Evidence in sample | Reason |
|---|---|---|---|---|
| Client-facing advice | C05 | merged | yes | Advisor tools and personalized recommendations appear (Connect Coach, Sales Assist); no robo-advice. JPM text discusses advice, sales and personalization together, so merged with Marketing |
| Portfolio construction/optimization | - | no evidence - not a v0.1 category | none | No passage describes AI in allocation or rebalancing. AWM AI text is about research and advisor tools (C10, C05). Re-test when asset managers / retirement firms are added |
| Trading & execution | C04 | kept (broadened) | yes (thin) | Prime Finance inventory, pricing and capital optimization. Broadened to 'capital optimization'; 'algorithmic trading' without an AI term is not counted |
| Risk management | C03 | kept (narrowed) | yes | ML in valuation/risk/stress-test models and 'risk intelligence'. Risks CAUSED by AI moved to new C12 |
| Fraud detection & AML/KYC | C01 | kept | yes (strongest) | Fraud prediction, transaction/sanctions screening, KYC - with quantified results |
| Compliance & regulatory | C01 / C12 | split - no stand-alone category | partial | No passage on AI for surveillance or regulatory reporting. Sanctions/transaction screening went to C01; regulation OF AI went to C12. Re-test with other banks |
| Back-office/operations | C07 | kept | yes | Manual-process elimination, operations productivity targets, trade/money-movement processing |
| Underwriting | C02 | kept (lending only) | yes | Mortgage and consumer credit decisioning. No insurance underwriting in a bank sample - add a sub-tag if insurers join |
| Customer service | C06 | kept (broadened) | yes | Call prediction/routing, faster onboarding, AI in client treasury tools. No customer chatbot named for JPM (expected for BAC's Erica) |
| Research & analytics | C10 | kept (narrowed) | yes | Research assistants and document insight tools for investors/analysts |
| HR/internal productivity | C08 + C09 | split | yes | Coding assistants are frequent and have their own metrics (C08). Enterprise GenAI platform, employee assistant, AI training role plays (C09) |
| Marketing | C05 | merged | yes | Personalization at scale and marketing use cases - merged with Client-facing advice (see above) |
| (new) | C11 | added | yes (most frequent) | AI strategy, spending, data readiness, talent, rankings - most 'hype' text. Not a use; kept so the index can separate talk from use |
| (new) | C12 | added | yes (most frequent in 10-K) | AI risk factors, AI regulation, board oversight - dominant in 10-K Item 1A and proxies |
| (new) | C00 | added | yes | Keyword hits not about the firm's AI (macro, policy, metaphors, glossary, AI companies as clients) - needed to measure false positives |

## 7. Not yet supported by evidence

- **Portfolio construction/optimization** (asset allocation, factor models, rebalancing): No passage describes AI in allocation or rebalancing. AWM AI text is about research and advisor tools (C10, C05). Re-test when asset managers / retirement firms are added
- **Compliance & regulatory** (surveillance, regulatory reporting automation): No passage on AI for surveillance or regulatory reporting. Sanctions/transaction screening went to C01; regulation OF AI went to C12. Re-test with other banks
- **Insurance underwriting**: starter 'Underwriting' example; banks only lend, so C02 covers lending only. Add a sub-tag if insurers join.
- **Customer chatbots**: starter 'Customer service' example; no JPM passage names one (BAC's Erica is expected).
- **AI for cyber-defence**: not in the starter list and not in the sample; C01 excludes it for now.

These stay out of the taxonomy until passages from other firms or sectors support them. The retirement-plan sub-tags described in Part 1.5 (participant advice, retirement income modelling, plan design and auto-features, sponsor analytics, participant chatbots) are also not covered yet: they need filings from retirement-plan providers.

## 8. Limitations

- **One firm.** Every example comes from JPM, so the taxonomy describes how one bank talks about AI. Category boundaries may move when other banks are added.
- **Where the text comes from.** Most concrete uses appear in annual-report shareholder letters, which are promotional and unaudited; the categories record what firms *say*, not verified deployment.
- **Keyword recall.** Uses described without any AI term are not found, so some uses may be missing.
- **One category per passage.** Passages that name several uses are coded by their main use; the others are lost at this level.
- **Drafted with AI assistance.** The team must check every definition, rule and paraphrase against the cited passages before submission.

## 9. Citation and paraphrase policy

Examples are paraphrased, never copied, and each cites the firm, document, filing date, SEC accession number, page or section, and the passage id. The full passage text is in `outputs/part2/ai_passages.csv` for checking; it is a working file and is not reproduced here (see the appendix).

## Appendix: Source passages (`outputs/part2/ai_passages.csv`)

This file is the raw material the taxonomy was built from: every passage in the filings that mentions AI, one passage per row. `src/part2_extract_ai_passages.py` scans each filing for the AI terms in `data/ai_keywords.csv` (e.g. AI, artificial intelligence, machine learning, generative AI), cuts out the matching sentence with one sentence either side, and merges matches that sit close together. It currently holds 165 passages (147 unique) from JPM.

| Column | Meaning |
|---|---|
| `passage_id` | Unique id; the examples in section 5 cite it — search for it to find the original text |
| `firm_id`, `quarter`, `form` | Firm, period and document type the passage comes from |
| `section`, `page` | Where in the document it sits (e.g. Item 1A Risk Factors; PDF page for annual reports) |
| `text` | The passage itself (verbatim) |
| `matched_terms` | The AI terms found in it |
| `dup_of` | Filled when the passage repeats an earlier one (e.g. the annual report reprinting the 10-K); such rows are read once |

Other columns (accession number, filing date, character positions) trace each passage back to the exact filing on SEC EDGAR.

The `text` column is copied verbatim from the filings. It is kept as an internal working file for checking and coding only; any text used in a report is paraphrased and cited, as in section 5.
