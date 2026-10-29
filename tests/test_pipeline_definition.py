"""The Step Functions definition lives in a Terraform template; check its graph offline."""

import json
import re
from pathlib import Path

import pytest

TEMPLATE = (
    Path(__file__).parent.parent
    / "terraform"
    / "modules"
    / "orchestrate"
    / "pipeline.asl.json.tftpl"
)


@pytest.fixture(scope="module")
def definition():
    text = TEMPLATE.read_text()
    names = set(re.findall(r"\$\{(\w+)\}", text))
    assert names == {
        "ingest_function_arn",
        "enrich_function_arn",
        "curate_function_arn",
        "topic_arn",
    }
    rendered = re.sub(r"\$\{(\w+)\}", lambda m: f"arn:test:{m.group(1)}", text)
    assert "${" not in rendered  # nothing left that Terraform would try to interpolate
    return json.loads(rendered)


def _targets(state):
    found = [state["Next"]] if "Next" in state else []
    found += [c["Next"] for c in state.get("Catch", [])]
    return found


def test_every_target_exists_and_every_state_is_reachable(definition):
    states = definition["States"]
    assert definition["StartAt"] in states
    reachable, queue = set(), [definition["StartAt"]]
    while queue:
        name = queue.pop()
        if name in reachable:
            continue
        reachable.add(name)
        for target in _targets(states[name]):
            assert target in states, f"{name} points at missing state {target}"
            queue.append(target)
    assert reachable == set(states)


def test_every_path_ends_in_a_terminal_state(definition):
    states = definition["States"]
    for name, state in states.items():
        if state["Type"] in ("Succeed", "Fail"):
            continue
        assert _targets(state), f"{name} has no way out"


def test_tasks_are_bounded_and_catch_failures(definition):
    lambda_tasks = {
        name: s
        for name, s in definition["States"].items()
        if s.get("Resource") == "arn:aws:states:::lambda:invoke"
    }
    assert set(lambda_tasks) == {"Ingest", "Enrich", "Curate"}
    for name, state in lambda_tasks.items():
        assert state["TimeoutSeconds"] > 0, name
        assert state["Catch"][0]["ErrorEquals"] == ["States.ALL"], name


def test_lambda_timeouts_leave_room_for_the_lambda_itself(definition):
    # The state timeout must exceed the Lambda's own (ingest 180 s, enrich 600 s, curate 300 s).
    states = definition["States"]
    assert states["Ingest"]["TimeoutSeconds"] > 180
    assert states["Enrich"]["TimeoutSeconds"] > 600
    assert states["Curate"]["TimeoutSeconds"] > 300


def test_ingest_and_enrich_failures_do_not_stop_the_run(definition):
    states = definition["States"]
    assert states["NotifyIngestFailed"]["Next"] == "Enrich"
    assert states["NotifyEnrichFailed"]["Next"] == "Curate"
    assert states["NotifyCurateFailed"]["Next"] == "PipelineFailed"
    assert states["PipelineFailed"]["Type"] == "Fail"


def test_curate_gets_the_execution_date(definition):
    payload = definition["States"]["Curate"]["Parameters"]["Payload"]
    assert payload == {
        "dt.$": "States.ArrayGetItem(States.StringSplit($$.Execution.StartTime, 'T'), 0)"
    }


def test_notifications_name_the_execution(definition):
    for name in ("NotifyIngestFailed", "NotifyEnrichFailed", "NotifyCurateFailed"):
        params = definition["States"][name]["Parameters"]
        assert params["TopicArn"] == "arn:test:topic_arn"
        assert "$$.Execution.Id" in params["Message.$"]
