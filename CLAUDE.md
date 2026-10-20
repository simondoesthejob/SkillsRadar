# Skills Radar: project context for Claude

## What this is
A portfolio project: a UK job-market skills radar on AWS. It ingests job postings from official
APIs, extracts the skills they ask for, models how demand changes over time, and shows it in a web
UI. Built end to end with Terraform, GitHub Actions and SageMaker Pipelines.

The owner is an experienced software engineer (UK, Europe/London), recently made redundant and doing
a remote MSc in Data Science. The project has three jobs: demonstrate skills to employers, give
refresher practice, and be genuinely useful. Explain Terraform and AWS ideas as you go, because
Terraform is new to the owner. Python is the main language; Go, Node.js and Java are familiar; React
or C# is acceptable for the UI.

Differentiators to protect (see docs/roadmap.md):
- A personalised skill-gap engine (rank skills worth learning, with evidence).
- Emerging-skill detection (new tools the vocabulary does not know yet).
- A properly evaluated extractor: precision and recall against a hand-labelled gold set,
  published on a methodology page.

## Data sources and rules
- Adzuna API (limits: 25/min, 250/day, 1000/week, 2500/month; must show "The Adzuna API" attribution).
- Reed API (basic auth: key as username, empty password; resultsToTake max 100; date format assumed
  day-first dd/mm/yyyy, unverified against the live API).
- Hacker News "Who is hiring?" via the keyless Algolia API.
- LinkedIn is deliberately excluded, including public guest endpoints. Do not add it.
- Details and call budgets: docs/data-sources.md.

## Layout
| Path | Purpose |
|---|---|
| `src/skillsradar/` | Python package: `models.py`, `config.py`, `http.py`, `handler.py`, `sources/{adzuna,reed,hn_hiring}.py` |
| `tests/` | Offline unit tests (fake HTTP and AWS clients) |
| `terraform/iam/` | Stack: IAM groups and policies (admin applies once, local state, no CI) |
| `terraform/bootstrap/` | Stack: state bucket and GitHub OIDC roles (applied once locally, local state) |
| `terraform/envs/dev/` | Stack: data buckets and ingestion (S3 remote state, applied by CI) |
| `terraform/modules/` | `data`, `ingest`, `github_oidc`, `iam_groups` |
| `.github/workflows/` | `ci.yml`, `terraform-plan.yml` (PRs), `terraform-apply.yml` (main, `dev` environment) |
| `docs/` | architecture.md, data-sources.md, roadmap.md, iam-access.md |

## Commands
```bash
python -m venv .venv && source .venv/bin/activate
make install   # pip install -e ".[dev]"
make lint      # ruff check + ruff format --check
make fmt
make test      # pytest
make tf-fmt    # terraform fmt -recursive
```
Terraform requires 1.10+ and AWS provider ~> 5.80. CI runs `terraform fmt -check -recursive terraform`,
then `init -backend=false` and `validate` in each of the three root stacks.

## Conventions
- Python 3.12. Ruff rules E, F, I, UP, B, SIM; line length 100. Run `ruff format` before committing.
- The ingestion Lambda is dependency-free: `urllib` plus the runtime's boto3. Keep it that way.
- Raw data keys are Hive-partitioned: `raw/source=<s>/dt=YYYY-MM-DD/run-HHMMSS.jsonl.gz`.
- The handler writes what it can, then raises if any source failed, so failures reach the DLQ.
- Every stack has a `providers.tf` with no credentials (`aws_profile`, `assume_role_arn`,
  `allowed_account_ids` variables, `default_tags`). Never hard-code keys or secrets.
- Resource names use the prefix `skillsradar-<env>` (dev: `skillsradar-dev`).
- Secret values (Adzuna, Reed) are set by hand with `aws secretsmanager put-secret-value`, never in
  Terraform or Git.
- Never commit `*.tfstate`, `terraform.tfvars`, `backend.hcl` or `.env` (all git-ignored).

## Authenticating Terraform locally (macOS, zsh)
- Provider 5.x cannot read `aws login` sessions. Run
  `eval "$(aws configure export-credentials --format env)"` first.
- With the MFA policy on, use `aws sts get-session-token` credentials (docs/iam-access.md).
- Stack order: `terraform/iam` (optional), then `terraform/bootstrap`
  (`terraform apply -var github_repo=<owner>/<repo>`), then push to main so CI applies `envs/dev`.
- GitHub setup: repo variables `TF_STATE_BUCKET` and `AWS_PLAN_ROLE_ARN`; environment `dev` with
  variable `AWS_APPLY_ROLE_ARN`.

## Status
Phase 1 (foundations and ingestion) is deployed and running; phase 2 is in progress.
- Python: 24 tests pass and ruff is clean.
- Terraform: CI runs `fmt` and `validate`; the apply workflow deploys `envs/dev` through GitHub OIDC.
  The IAM policies in `iam_groups` are best-effort and were never tested against live AWS, so expect
  the odd AccessDenied to need one more action.
- The GitHub OIDC `sub` claim for this repo is ID-qualified (`owner@id/name@id`), so the bootstrap's
  `github_repo` variable must use that form.
- Done: keys stored, each source tested, daily schedule enabled and confirmed working.
- Phase 2 step 1 built, not yet applied: `terraform/modules/analytics` (Glue database and table with
  partition projection, Athena workgroup with a 1 GiB scan cap, five saved queries in
  `terraform/modules/analytics/queries/`). Needs a push to main (CI apply) and a one-off re-apply of
  `terraform/iam` so the operator group can run Athena queries.
- Next: curation job (Parquet, validation, dedupe, salary normalisation), Reed enrichment, Step
  Functions; then SageMaker pipelines, the API and UI (phases 3 to 5). See docs/roadmap.md.
- Terraform formatting can be checked here with OpenTofu (`tofu fmt`); providers cannot be fetched
  in the sandbox, so `validate` only runs in CI.

## Known follow-ups
- The apply role has `AdministratorAccess`; tighten it to least privilege.
- Bootstrap state is local; consider `terraform init -migrate-state` into the S3 bucket.
- No AWS Budget is created by Terraform; set one by hand.
- Keep an eye on cost: Secrets Manager is about $0.40 per secret per month, and SageMaker costs
  arrive in later phases (prefer serverless inference or batch transform, and tear down non-prod
  resources).
