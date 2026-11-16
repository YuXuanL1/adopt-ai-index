# Source strategy for Parts 1 and 1.5

The index must distinguish direct evidence of a firm's AI adoption from background news. Use
each source only for the role listed below, and cite the exact document URL and access date.

| Priority | Source type | Use it for | Collection method |
| --- | --- | --- | --- |
| 1 | SEC EDGAR filings: 10-K, 10-Q, 8-K, DEF 14A | Main evidence, firm identity, business segments, and dated AI disclosures | Official SEC APIs/bulk data only |
| 2 | Company earnings materials and press releases | Specific AI products, partnerships, deployments, and announcements | Manual unless the site's terms and robots rules permit a defined automated route |
| 3 | Earnings-call transcripts | Management discussion and implementation details | Manual review; preserve the transcript URL and short quoted excerpt |
| 4 | Credible news APIs/news articles | Discovery and independent context | API only if its plan permits class use; otherwise use manually and cite |
| 5 | Careers, product, and innovation pages | Supporting evidence of AI-related hiring or product capability | Manual review; never treat a job advertisement alone as proof of deployed AI |
| 6 | Federal Reserve and FINRA material | Regulatory and industry context | Context only, not a firm's adoption score |

## Rules for web collection

1. Before any automated request, save the current Terms of Service in `data/terms/<source_id>.txt` and run `part1_check_sources.py`.
2. A positive robots.txt result is not permission by itself. Record a human decision in the source register after reading the terms.
3. If the source has an official API, RSS feed, or bulk download, use that route rather than HTML scraping.
4. Respect the rate limit in the source register, identify the team in the User-Agent, cache responses, and keep the request log.
5. Keep only the text needed for the assignment. In the final write-up, identify source type, document date, URL, and any important access limitation.

## Recommendation for the first submission

Build the initial index from SEC EDGAR. Add a small, manually reviewed set of company press
releases and earnings transcripts for the retirement-plan-provider firms. This gives the project
evidence from multiple source types without relying on restricted publisher sites.
