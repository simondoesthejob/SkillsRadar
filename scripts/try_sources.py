"""Smoke-test the live APIs. Usage: python scripts/try_sources.py reed|adzuna|hn_hiring"""

import itertools
import os
import sys

from skillsradar.sources.adzuna import AdzunaSource
from skillsradar.sources.hn_hiring import HnWhoIsHiring
from skillsradar.sources.reed import ReedSource

name = sys.argv[1]
if name == "reed":
    source = ReedSource(os.environ["REED_API_KEY"], queries=("data engineer",), pages_per_query=1)
elif name == "adzuna":
    source = AdzunaSource(
        os.environ["ADZUNA_APP_ID"],
        os.environ["ADZUNA_APP_KEY"],
        country="gb",
        queries=("data engineer",),
        pages_per_query=1,
        results_per_page=10,
        request_interval=2.5,
    )
else:
    source = HnWhoIsHiring(threads=1)

for p in itertools.islice(source.fetch(), 5):
    print(p.to_record(__import__("datetime").datetime.now()))
