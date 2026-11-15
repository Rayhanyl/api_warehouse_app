from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "deploy.yml"


def test_deploy_waits_for_backend_healthcheck() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "for attempt in $(seq 1 30); do" in workflow
    assert "curl --fail --silent --show-error http://127.0.0.1:8000/health" in workflow
    assert "sleep 2" in workflow
    assert 'if [ "$attempt" -eq 30 ]; then' in workflow
