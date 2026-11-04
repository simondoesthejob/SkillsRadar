# Gold set: labelling guidelines

The gold set is a few hundred job postings, each labelled by hand with the skills it asks for. It is
the yardstick for the skill extractor: precision and recall are measured against it, and the results
go on the methodology page. It is only as good as the labels are consistent, so follow these rules the
same way every time. If a rule feels wrong, change it here and relabel the affected postings rather
than quietly doing something different.

## What to label

A **skill** is a specific, nameable thing a candidate could list on a CV:

| Label it | Examples |
|---|---|
| Programming and query languages | Python, SQL, R, Scala, TypeScript |
| Libraries and frameworks | pandas, PyTorch, React, Django, Spark |
| Tools and platforms | Docker, Terraform, Tableau, Snowflake, AWS, Git |
| Techniques and methods | machine learning, A/B testing, time series, NLP, ETL |
| Named practices | Agile, Scrum, CI/CD, MLOps |

Label a skill when the posting asks for it, mentions it as part of the job, or lists it as desirable
("nice to have", "a plus"). A technology the team uses day to day counts even if the text does not
say the candidate needs it ("our stack is Kafka, Flink and Airflow"). Do not try to separate
"required" from "desirable"; treat them the same for now.

## What not to label

- **Soft skills and traits**: communication, leadership, stakeholder management, "team player".
- **Qualifications and experience**: "degree in a numerate subject", "5+ years", "MSc preferred".
- **Industries and domains**: finance, healthcare, retail. (Treat "quantitative finance" as not a skill.)
- **Vague words**: "data", "software", "analytics", "AI" on its own as a company strapline, "cloud" on its own.
  If the text says something specific ("machine learning", "AWS"), label that.
- **The employer's own products**, unless they are a technology a candidate would be expected to know.
- **Skills mentioned only in company boilerplate** ("we love open source") rather than the role.
- **Negations**: "no Java experience needed" is not a Java skill.

When unsure whether something counts, ask: *would a recruiter search a CV for this term?* If yes,
label it. If you are still unsure, label it or not, but add a short note so the call can be reviewed.

## How to write each skill

- Use the **vocabulary name**. Type a few letters and pick it from the list; aliases such as `sklearn`
  or `k8s` are turned into the standard name (`scikit-learn`, `Kubernetes`) automatically.
- If the skill is not in the list, type it in its usual form ("DuckDB", "Delta Live Tables") and press
  **Shift+Enter**. It shows in yellow. These new skills feed emerging-skill detection later and are
  added to the vocabulary when they come up repeatedly.
- One entry per skill per posting, however often it is repeated. Lists with "or" count each one
  ("Python or R" is two skills; "AWS, Azure or GCP" is three).
- Write the thing itself, not a phrase around it: "Python", not "strong Python skills".
- Specific beats general, and both can apply: a posting that says "PySpark" gets `PySpark`, and also
  `Apache Spark` only if it says Spark or clearly means it.

## Skip and notes

- **Skip** a posting that is not a real job (a recruiter's list of vacancies, a duplicate) or that has
  too little text to judge. Skipped postings are excluded from scoring.
- A posting with **no technical skills** at all is valid: save it with an empty skill list. These
  matter, because they show whether the extractor invents skills.
- Use the notes box for anything odd, or a judgement call you want to revisit.

## Keeping it independent of the extractor

The labelling page deliberately shows **no automatic suggestions**. Pre-filled hints would pull your
labels towards whatever the rules extractor finds, and the gold set would then flatter it. Label from
reading the text. Please do not run the extractor first and copy its output.

## Consistency check (recommended)

Human labels drift. After the first full pass, wait a few days and relabel about 20 postings you have
forgotten. Compare the two sets: agreement of 85 to 90% or more is healthy. Where they differ, the
rule above was not clear enough; tighten it. Record the final agreement figure on the methodology
page, because it is the ceiling on how good any extractor can look.

## Dev and test halves

Postings are split into a **dev** half and a **test** half by a hash of their ID (`gold/split.py`).
Label them all the same way; the split only matters when scoring. Use dev to tune the extractor and
read its errors. The test half is for the final published score and its error detail is hidden by
`scripts/evaluate_extractor.py`, so it cannot leak into tuning.

## Reviewing against the extractor

A second pass in the labeller's review mode shows where the extractor and you disagree, with the
matched text highlighted. Treat suggestions as evidence to weigh, not answers: add a skill only if
the posting genuinely asks for it under the rules above. Reviewing is dev-half only; relabel the test
half without suggestions. Review-prompted labels are tagged so they can be scored separately.

## How big

Aim for **200** postings: about 120 from Reed, 60 from Hacker News and 20 from Adzuna. Adzuna is a
small slice because its text is cut off at 500 characters, which is itself worth reporting. 200
postings with roughly 8 to 15 skills each gives a few thousand labels. That is enough to tell a good
extractor from a bad one, but for rare skills the scores will be noisy, so report them with a note.
More can be added later with `python scripts/gold_sample.py --extend 50`.

## Privacy and terms

The sample holds job-listing text from Adzuna, Reed and Hacker News. Keep `data/` out of Git (it is
git-ignored) and do not publish the postings themselves. The methodology page can publish the labelling
rules, the counts and the scores. Individual labels are fine to publish if keyed by an opaque ID
rather than text.
