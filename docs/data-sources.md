# Data sources and terms

The project only uses sources with an official API or a documented public endpoint. It does
not scrape job boards, because that typically breaches their terms and would undermine a
portfolio project. Terms were checked on 2026-10-04; re-check them before publishing anything.

| Source | Access | Limits / obligations | Status |
|---|---|---|---|
| **Adzuna API** | Free key from developer.adzuna.com | Default limits: 25 calls/min, 250/day, 1,000/week, 2,500/month. Permitted uses include publishing listings and personal research. Acknowledge "The Adzuna API" and link to adzuna.co.uk wherever data is published. One account per person or entity. | Implemented |
| **Reed Jobseeker API** | Free key from reed.co.uk/developers/jobseeker; HTTP basic auth with the key as username | Reed's public API page lists no rate limits or terms, so read the terms shown when you register and keep call volumes low. Search results carry a truncated description; full text needs one call per job (`/jobs/{id}`). | Implemented |
| **Hacker News "Who is hiring?"** | Public Algolia HN API, no key | No key. Be polite (one thread per run). Comments are user-generated free text, so extraction quality varies. | Implemented |
| **LinkedIn** | No official way to read postings | The Job Posting API is for approved partners *posting* jobs, and is closed to new partners. Automated access, including the unauthenticated guest endpoints, is outside the documented API and in tension with LinkedIn's User Agreement. | Deliberately excluded |

## Budgeting API calls

Calls per day = runs per day x queries x pages per query, per source. The defaults (5 queries
x 2 pages, one run a day) use 10 Adzuna calls and 10 Reed calls a day. That is far below
Adzuna's 250/day limit and leaves room for backfills. Both sources space calls 2.5 seconds apart
by default (Adzuna allows 25/minute).

## Overlap between sources

Adzuna aggregates vacancies from many boards, including some that also appear on Reed, so the
same job can arrive from both. Records are only deduplicated within a source (`dedupe_key`).
Cross-source matching on normalised title, company and location is done in the curated layer
(phase 2), and its match rate is itself a useful metric to report.

## Salary fields

Salary values are stored as the sources give them. Reed's detail endpoint exposes a salary type
(hourly, daily, annual and so on), and Adzuna's estimates can be predicted rather than
advertised (`salary_predicted`). Normalisation to an annual figure belongs in the curated layer.

## What the public UI may show

Show aggregate statistics (skill counts, trends, salary distributions) with each provider's
attribution rather than republishing full listings. If you later want to publish listings,
check each provider's terms and request higher limits where needed.

Raw postings contain employer names and free text only. No personal data is intentionally
collected, but Hacker News comments name individuals as contacts, so the raw bucket stays private
and the curated layer should drop contact details.
