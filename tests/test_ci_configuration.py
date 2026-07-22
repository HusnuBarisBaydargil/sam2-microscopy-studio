from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_the_supported_test_and_lint_commands():
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job_configuration, steps_configuration = workflow.split("\n    steps:\n", maxsplit=1)

    expected_configuration = (
        "push:",
        "pull_request:",
        'python-version: "3.12"',
        'node-version: "22"',
        'SKIP_SAM_MODEL_LOAD: "1"',
        "python -m pip install -r requirements-ci.txt",
        "python -m pytest tests -q",
        "python -m ruff check .",
    )
    for expected in expected_configuration:
        assert expected in workflow

    assert "${{ runner." not in job_configuration
    run_tests_step = steps_configuration.split("- name: Run tests", maxsplit=1)[1].split(
        "- name: Run Ruff", maxsplit=1
    )[0]
    assert "PROJECT_SETTINGS_FILE: ${{ runner.temp }}/sam2-project-settings.json" in run_tests_step
    assert "PROJECT_MANIFEST_FILE: ${{ runner.temp }}/sam2-project-manifest.json" in run_tests_step


def test_ci_dependencies_include_runtime_dependencies():
    requirements = (REPO_ROOT / "requirements-ci.txt").read_text(encoding="utf-8")

    assert "-r requirements.txt" in requirements.splitlines()
    assert "pytest==8.3.4" in requirements.splitlines()
    assert "ruff==0.8.6" in requirements.splitlines()
