# Roadmap: phases 2 to 5

Existing tools already chart skill demand (commercial analytics, public skills maps, Hacker News
trend sites, many hobby dashboards), so the topic alone is not novel. This project differentiates
itself on three things, and every phase below serves at least one of them:

1. **A personalised skill-gap engine.** Give it your skills and target roles, and it ranks the UK
   skills worth adding, with evidence.
2. **Emerging-skill detection.** Find tools and frameworks that are new to the vocabulary, instead
   of relying on a fixed keyword list.
3. **A properly evaluated extractor.** Skill extraction is measured against a hand-labelled set,
   and the methodology page reports precision, recall, sampling bias and cross-source match rate.

## The constraint that shapes the schedule: history takes time

Momentum forecasts need months of weekly data, and the pipeline only starts collecting once the
ingestion schedule is on. **Enable the schedule as soon as phase 1 works**, even before anything
else exists. In the meantime, develop and backtest the forecasting code on the Hacker News
"Who is hiring?" archive, which goes back years (it is tech-heavy and not UK-specific, so treat
it as a development dataset, not as UK evidence).

## Phase 2: Data (Glue, Athena, Step Functions)

- **Catalog and query (built):** a Glue database and table defined in Terraform
  (`terraform/modules/analytics`, partition projection on `source` and `dt`), an Athena
  workgroup with a scan limit and results in the artifacts bucket, and five saved example
  queries in `terraform/modules/analytics/queries/`.
- **Curation job** (Glue job or Lambda, whichever is simpler for the volume): writes Parquet to the
  curated bucket, partitioned by date. It does:
  - schema validation (Pandera or Great Expectations), with metrics sent to CloudWatch;
  - dedupe within a source on `dedupe_key`, then across sources on normalised title, company and
    location, with a similarity check on descriptions for near-duplicates;
  - salary normalisation to an annual figure, flagging predicted and non-annual values;
  - dropping personal contact details found in Hacker News comments.
- **Reed enrichment:** fetch full descriptions via `/jobs/{id}` for new Reed IDs only.
- **Orchestration:** a Step Functions state machine runs ingest, validate, curate and then starts
  the ML pipeline, with retries and failure notifications through SNS.
- **Report:** cross-source match rate and per-source coverage, written as a small dataset the UI
  can display.

**Done when:** Athena answers "postings per source per day" and "top employers this week", and a
failed validation stops the run and raises an alert.

## Phase 3: ML (SageMaker Pipelines)

### 3a. Skill extraction, evaluated
- **Taxonomy:** seed from a public skills taxonomy such as ESCO (check its licence terms), plus
  tech-specific terms. Keep it in the repo as versioned data.
- **Gold set:** hand-label roughly 200 to 300 postings across sources with a simple labelling
  sheet. Split it so the test portion is never used for tuning.
- **Models:** (1) a dictionary and rules baseline; (2) an embedding-based or fine-tuned
  transformer extractor trained in a SageMaker training job.
- **Metrics:** skill-level precision, recall and F1, with error analysis by source (Hacker News
  prose and Reed's truncated text are expected to differ).
- **Quality gate:** the pipeline registers a new model only if it beats the current one on the gold
  set.

### 3b. Emerging-skill detection
- Take candidate phrases that match no taxonomy entry, embed them, and cluster them.
- Track each cluster's share of postings over time and flag sharp growth.
- Send candidates to a **review queue**. Approving one opens a pull request that adds it to the
  taxonomy, which ties the ML loop back to GitHub and CI.
- **Evaluate:** replay history and measure how early the method flags skills that later became
  common, and its false-alarm rate.

### 3c. Momentum forecasting
- Weekly share of postings per skill (share, not count, so changes in posting volume do not
  masquerade as skill trends).
- Compare a seasonal-naive baseline, ETS or ARIMA, and one global model (for example DeepAR or a
  gradient-boosted model over many skills), with **prediction intervals**.
- **Evaluate** with rolling-origin backtests, error metrics scaled against the baseline (MASE) and
  interval coverage. Report skills with too little history as "insufficient data" instead of
  forecasting them.

### 3d. Personalised gap engine
- **Input:** a skills list (and target roles) the user supplies, for example from their CV.
- **Score:** a transparent combination of demand share, momentum, and co-occurrence with the user's
  existing skills (for example pointwise mutual information), so suggestions are adjacent to what
  they already know.
- **Output:** a ranked list that shows its evidence: share of postings, trend with interval, and
  the skills it co-occurs with. No opaque scores.
- **Evaluate:** stability checks on synthetic profiles, and a sanity review of the results against
  your own experience.

**Done when:** one SageMaker Pipeline run goes from curated data to a registered, gated model, and
the methodology page shows real precision, recall and backtest numbers.

## Phase 4: Serving and UI

- **Serving:** extractor on a SageMaker serverless endpoint (or batch transform for scheduled
  scoring), behind API Gateway and Lambda.
- **Storage for the app:** Athena and Parquet for analytics; DynamoDB for user profiles and the
  review queue.
- **UI:** React and TypeScript on S3 and CloudFront, with these pages:
  - **Radar:** top and fastest-rising skills, with filters.
  - **Skill detail:** trend, forecast interval, related skills, example employers.
  - **My gap analysis:** the personalised engine, with evidence.
  - **Emerging:** the review queue.
  - **Methodology:** extraction metrics, backtest results, sampling bias, source attribution.
- **Auth (optional):** Cognito, only if profiles are stored per user. A single-user version can
  run without it.

## Phase 5: Monitoring and polish

- SageMaker Model Monitor with a data-quality baseline, plus a custom vocabulary-drift metric
  (the share of text that matches no known skill), which triggers retraining and the review queue.
- CloudWatch dashboard and alarms, AWS Budgets, and a cost note in the README.
- Tear-down workflow for expensive non-production resources.
- A short write-up of the design decisions and trade-offs, and a demo video or screenshots.

## MVP cut lines (if time runs short)

In the order I would drop things:
1. Cognito and multi-user profiles (keep a single-user profile file).
2. The transformer extractor (keep the evaluated rules baseline and report it honestly).
3. The global forecasting model (keep baseline plus ETS with intervals).
4. Cross-source fuzzy matching (keep exact-key dedupe and report the limitation).

Do not cut the evaluation work, the gap engine or the methodology page. They are what make this
project different from the existing dashboards.

## Where the learning goals land

| Skill to show or refresh | Where it appears |
|---|---|
| Terraform, AWS breadth, CI/CD with OIDC | Phase 1 onwards |
| SQL, data lakes, Athena, Glue | Phase 2 |
| Data quality engineering | Phase 2 |
| NLP, evaluation methodology, experiment tracking | Phase 3a, 3b |
| Time-series forecasting and backtesting | Phase 3c |
| Recommender-style ranking and explainability | Phase 3d |
| MLOps: pipelines, registry, gating, monitoring | Phases 3 and 5 |
| React and TypeScript (and optionally C# for the API) | Phase 4 |

## Risks

- **Short history** limits forecasting early on. Mitigation: start collecting now; develop on the
  Hacker News archive.
- **Source terms and limits** can change. Mitigation: documented budgets, per-source isolation,
  and attribution (see `data-sources.md`).
- **Sampling bias:** job adverts are not jobs, and the boards over-represent some sectors. State
  this plainly on the methodology page.
- **Cost drift** from SageMaker resources left running. Mitigation: serverless or batch inference,
  budgets and alarms from the start.
- **Scope creep.** Mitigation: the cut lines above, and finishing each phase before starting the
  next.
