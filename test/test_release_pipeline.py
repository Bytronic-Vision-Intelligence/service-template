# test/test_release_pipeline.py
"""Properties of the release workflow itself.

Each of these silently stops being true if someone edits the YAML, and nothing
else in the suite would notice. This file is copied into every service that
uses the template, so a property broken here is broken everywhere.
"""
import re
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github/workflows/release-pipeline.yml"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _jobs(workflow):
    return workflow["jobs"]


def _steps(job):
    return job["steps"]


def _all_steps(workflow):
    return [s for job in _jobs(workflow).values() for s in _steps(job)]


def _run(step) -> str:
    """A step's shell, with comment lines removed.

    Searching raw `run:` text finds matches inside comments. A step whose
    comment mentions `gh release create` is not a step that runs it, and an
    assertion fooled that way passes whatever the command actually says.
    """
    lines = str(step.get("run", "")).splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def _step_running(workflow, fragment):
    found = [s for s in _all_steps(workflow) if fragment in _run(s)]
    assert len(found) == 1, f"expected exactly one step running {fragment!r}, found {len(found)}"
    return found[0]


def test_nothing_but_a_push_to_prod_triggers_a_release(workflow):
    """Three of the service repositories are PUBLIC. A `pull_request` trigger
    would let a fork's pull request reach a workflow that holds the shared
    SERVICE signing key -- and a key in one public repo is a key compromised
    for all eight. `push` requires write access, which a fork does not have.
    """
    # PyYAML parses a bare `on:` key as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert list(triggers) == ["push"]
    assert triggers["push"]["branches"] == ["prod"]


def test_only_one_job_can_see_the_signing_key(workflow):
    """The build matrix runs on three runners including Windows and macOS. The
    key is needed on exactly one of them, so every runner that does not need it
    must not receive it -- three times the exposure buys nothing."""
    signing = [name for name, job in _jobs(workflow).items()
               if "SERVICE_SIGNING_KEY" in str(job)]
    assert signing == ["release"]
    steps = [s.get("name") for s in _all_steps(workflow)
             if "SERVICE_SIGNING_KEY" in str(s.get("env", {}))]
    assert len(steps) == 1, f"more than one step receives the key: {steps}"


def test_the_build_job_receives_no_secrets(workflow):
    assert "secrets." not in str(_jobs(workflow)["build"])


def test_the_signing_step_runs_the_repository_signer(workflow):
    """Not an inline `python -c`: the checks that make signing safe -- the key
    matching what this repository expects, the round-trip verify -- live in
    scripts/sign.py and are tested. A step that signed inline would have none
    of them and would look identical in the log."""
    step = _step_running(workflow, "scripts/sign.py")
    assert "SERVICE_SIGNING_KEY" in step.get("env", {})


def test_no_run_block_interpolates_into_a_shell(workflow):
    """A repository name or tag containing $(...) would otherwise execute on
    the runner. Checking for `${{` rather than a specific expression closes the
    class rather than one instance of it.

    The build job's steps are exempt: `matrix.platform` is a value this file
    defines itself, and it reaches paths that have no env-var equivalent.
    """
    for name, job in _jobs(workflow).items():
        if name == "build":
            continue
        for step in _steps(job):
            assert "${{" not in _run(step), \
                f"step {step.get('name')!r} interpolates into a shell"


def test_the_release_is_published_with_the_signatures(workflow):
    """A release carrying zips and no `.sig` files verifies for nobody, and
    every step before this one would still have passed."""
    step = _step_running(workflow, "gh release create")
    assert "upload/*.sig" in _run(step)
    assert "upload/*.zip" in _run(step)
    assert "SHA256SUMS" in _run(step)


def test_an_empty_download_is_not_published_as_a_release(workflow):
    """`gh release create` with no files succeeds and publishes an empty
    release. Without this guard a failed matrix leg produces a release a
    customer can download nothing from."""
    step = _step_running(workflow, "zip -qr")
    assert re.search(r'"\$found"\s+-eq\s+0', _run(step)), \
        "nothing checks that any platform was actually packaged"


def test_artefact_names_come_from_the_repository(workflow):
    """The two hand-copied pipelines in this org differ by exactly four lines,
    all of them the service name. Deriving it means a service author copies
    this file unchanged and that entire class of error disappears."""
    step = _step_running(workflow, "zip -qr")
    assert step["env"]["SERVICE"] == "${{ github.event.repository.name }}"
    assert "${SERVICE}-${platform}.zip" in _run(step)


def test_the_build_action_is_pinned_to_a_commit(workflow):
    """This action turns source into the binary a customer runs. Tracking a
    moving branch means the shipped artefact can change without any commit
    here, and without anyone reviewing the change."""
    builds = [s for s in _all_steps(workflow)
              if "python-binary-action" in str(s.get("uses", ""))]
    assert builds, "no build step found"
    for step in builds:
        ref = step["uses"].split("@", 1)[1]
        assert re.fullmatch(r"[0-9a-f]{40}", ref), \
            f"build action is pinned to {ref!r}, not a commit SHA"


def test_the_release_job_waits_for_every_platform(workflow):
    assert _jobs(workflow)["release"]["needs"] == "build"


def test_the_workflow_can_write_releases_and_no_more(workflow):
    assert workflow["permissions"] == {"contents": "write"}


def test_runtime_requirements_carry_no_test_tooling():
    """Everything in requirements.txt is installed into the release build and
    ends up inside the shipped binary. A test framework in there is shipped to
    every customer of every service that copies this template."""
    runtime = (WORKFLOW.parent.parent.parent / "requirements.txt").read_text()
    for package in ("pytest", "pluggy", "Pygments"):
        assert package.lower() not in runtime.lower(), \
            f"{package} is a runtime dependency and would be built into the binary"
