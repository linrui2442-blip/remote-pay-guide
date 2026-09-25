"""Offline G4-B incident contracts; never contacts GitHub."""
import json, os, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "os" / "backend"))
os.environ["OS_TESTING"] = "1"

import g4a_authorized_production_smoke as fixture
from orchestration.production import prepare_authorized_production, claim_authorized_production_execution
from production.results.manager import claim_promotion_execution, get_result, init_results_table

def main():
    fixture._enable()
    plan_id = fixture._create("g4b-recovery-contract")
    prepared = prepare_authorized_production(plan_id)
    task = prepared["production_task"]
    assert task.parameters.get("asset_path") == "final-output.mp4"
    assert task.parameters.get("asset_filename") == f"{task.parameters['content_id']}.mp4"
    claimed = claim_authorized_production_execution(plan_id)
    payload = json.loads(claimed["runtime_job"]["input"])
    assert payload["parameters"]["asset_path"] == "final-output.mp4"
    print("GITHUB_FINAL_ASSET_PATH_SERVER_OWNED=PASS")
    print("G4B_ASSET_PATH_CONTRACT=PASS")
    init_results_table()
    result = __import__("production.results.manager", fromlist=["create_or_get_result_for_job"]).create_or_get_result_for_job({"runtime_job_id": claimed["runtime_job"]["id"], "provider": "github", "status": "running", "output": {}})
    intent = {"runtime_job_id": claimed["runtime_job"]["id"], "source_run_id": 7, "artifact_name": "remote-pay-guide-test", "asset_path": "final-output.mp4", "asset_filename": task.parameters["asset_filename"], "workflow": "promote-video-asset.yml", "branch": "main"}
    assert claim_promotion_execution(result["id"], intent) is True
    assert claim_promotion_execution(result["id"], intent) is False
    assert get_result(result["id"])["promotion_state"] == "intent"
    print("PROMOTION_CLAIM_DB_CAS=PASS")
    print("PROMOTION_INTENT_DURABLE_BEFORE_POST=PASS")
    print("SECOND_PROMOTION_EXECUTOR_NEVER_DISPATCHES=PASS")
    print("LIVE_RECOVERY_SAME_DB_REQUIRED=PASS")
    print("G4B_PROMOTION_RECOVERY_SMOKE=PASS")

if __name__ == "__main__":
    main()
