# Skills Radar

A job-market skills radar on AWS: ingest job postings from official APIs, extract the skills
they ask for, model how demand changes over time, and show it in a web UI. Built end to end
with Terraform, GitHub Actions and SageMaker Pipelines.

What is meant to set it apart from existing skills dashboards: a **personalised skill-gap engine**
(rank the skills worth learning next, with evidence), **emerging-skill detection** (new tools the
vocabulary does not know yet), and a **properly evaluated extractor** (precision and recall against
a hand-labelled set, published on a methodology page).

> Data from [The Adzuna API](https://www.adzuna.co.uk/), [Reed](https://www.reed.co.uk/) and
> Hacker News "Who is hiring?".

**Status: phase 1 (foundations and ingestion).** See [docs/architecture.md](docs/architecture.md)
for the design, [docs/roadmap.md](docs/roadmap.md) for phases 2 to 5, and
[docs/data-sources.md](docs/data-sources.md) for source terms and call budgets.

## What is here

| Path | Purpose |
|---|---|
| `src/skillsradar/` | Python package: job sources (Adzuna, Reed, Hacker News), canonical model, ingestion Lambda handler |
| `tests/` | Unit tests; no network or AWS access needed |
| `terraform/iam/` | One-off access stack: bootstrap and operator IAM groups (applied locally by an admin, before the bootstrap) |
| `terraform/bootstrap/` | One-off stack: remote-state bucket and GitHub OIDC roles (applied locally) |
| `terraform/envs/dev/` | Dev environment: data buckets, ingestion Lambda, schedule, DLQ, alarm |
| `terraform/modules/` | `data`, `ingest`, `github_oidc`, `iam_groups` modules |
| `scripts/aws_cli_walkthrough.sh` | Learning aid: the same AWS resources built with plain AWS CLI calls (`DRY_RUN=1` prints them without calling AWS). Not a deployment path |
| `.github/workflows/` | CI (lint, tests, `terraform fmt/validate`), plan on pull request, apply on merge |

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
make install   # pip install -e ".[dev]"
make lint
make test
```

## Connecting Terraform to AWS

Each stack (`terraform/iam`, `terraform/bootstrap`, `terraform/envs/dev`) has a `providers.tf` that
defines the connection. It holds **no credentials**; those come from the standard AWS chain. Pick
one way to authenticate:

| Situation | How |
|---|---|
| Your own machine, IAM Identity Center | `aws sso login --profile <name>` then `export AWS_PROFILE=<name>` |
| Your own machine, IAM user with MFA | `aws sts get-session-token ...` and export the three `AWS_*` variables (see [docs/iam-access.md](docs/iam-access.md)) |
| GitHub Actions | Nothing to set: the workflows use OIDC |

Then copy each stack's `terraform.tfvars.example` to `terraform.tfvars` (git-ignored) and set at
least `allowed_account_ids`. Terraform then refuses to run if your credentials belong to a different
AWS account, which is a cheap protection against applying to the wrong one. `aws_profile` and
`assume_role_arn` are optional overrides.

The S3 backend in `terraform/envs/dev` authenticates on its own and ignores the `aws_profile`
variable, so use the `AWS_PROFILE` environment variable if you use profiles.

## First deployment

1. **Prerequisites:** an AWS account with a budget alert set, the AWS CLI configured, Terraform
   1.10 or later, a free [Adzuna API key](https://developer.adzuna.com/), a free
   [Reed Jobseeker API key](https://www.reed.co.uk/developers/jobseeker) (read both providers' terms
   when you register), and this repository on GitHub.
2. **Access (only if you want a dedicated deployment user):** an admin identity applies
   `terraform/iam` once to create the IAM groups, then you add your deployment user to them. The
   order matters; follow [docs/iam-access.md](docs/iam-access.md). Otherwise skip to the next step
   using your own admin identity.
3. **Bootstrap (local state, run once, as a member of the bootstrap group or an admin):**
   ```bash
   cd terraform/bootstrap
   terraform init
   terraform apply -var github_repo=<owner>/<repo>
   ```
   If the account already has a GitHub OIDC provider, add `-var create_oidc_provider=false`.
4. **Configure GitHub:** set repository variables `TF_STATE_BUCKET` and `AWS_PLAN_ROLE_ARN`;
   create a GitHub environment named `dev` with the variable `AWS_APPLY_ROLE_ARN` (add required
   reviewers if you want an approval gate). Use the bootstrap outputs for the values.
5. **Deploy:** push to `main`. The apply workflow creates the buckets, Lambda and secret.
6. **Store the API credentials** (never in Git):
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id skillsradar-dev/adzuna \
     --secret-string '{"app_id":"<id>","app_key":"<key>"}'
   aws secretsmanager put-secret-value \
     --secret-id skillsradar-dev/reed \
     --secret-string '{"api_key":"<key>"}'
   ```
7. **Test each source on its own**, then enable the schedule by setting
   `ingest_schedule_enabled = true` in `terraform/envs/dev/variables.tf`:
   ```bash
   aws lambda invoke --function-name skillsradar-dev-ingest \
     --payload '{"sources":["reed"]}' --cli-binary-format raw-in-base64-out out.json
   ```
   Valid source names are `adzuna`, `reed` and `hn_hiring`; with no payload, all three run.

   Turn the schedule on as early as you can: the forecasting work needs months of history, and
   history only accumulates while the pipeline is running.

## Cost

At this stage the cost is pennies a month: one small Lambda run a day, a few MB in S3, and one
Secrets Manager secret (about $0.40/month). Costs grow with the SageMaker phase; the plan is
serverless inference or batch transform, plus tearing down non-production resources in CI.

## Verification status

The Python code passes `ruff` and 24 unit tests (all offline, with fake HTTP and AWS clients).
The Reed source has not been run against the live API yet, and its date format (day-first) is
handled defensively because Reed's documentation does not specify one. The Terraform has **not yet been through
`terraform validate`** (no Terraform binary was available where it was written), so CI will be the
first check. Expect to fix small syntax or provider-version issues on the first run.
