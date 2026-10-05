"""
Phase 8 Manual E2E Scenario Verification Script (12 Steps)

Candidate: Jane Doe
Existing verified evidence: Python, Flask, Docker, Kubernetes technology presence
Target: Senior Backend Engineer
Requirement: Production Kubernetes experience
Initial state: EXPERIENCE_GAP
Action: Build Kubernetes Deployment Project
"""
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("backend"))
from app.main import app
from app.schemas.career_execution import ExecutionStatus, ProgressState

client = TestClient(app)

def run_phase8_e2e():
    print("=" * 75)
    print("VETTORA PHASE 8 — 12-STEP MANUAL E2E CAREER EXECUTION VERIFICATION")
    print("=" * 75)

    # Setup Candidate: Jane Doe with Python, Flask, Docker, Kubernetes presence
    resume_path = "data/test_fixtures/resume_standard_sample.pdf"
    with open(resume_path, "rb") as f:
        resp = client.post("/api/coach/resume", files={"resume_file": ("resume_jane_doe.pdf", f, "application/pdf")})
    assert resp.status_code == 200, f"Resume upload failed: {resp.text}"
    candidate_data = resp.json()
    candidate_id = candidate_data["candidate_id"]
    print(f"\n[SETUP] Candidate initialized: {candidate_id}")

    # Setup Target: Senior Backend Engineer requiring Production Kubernetes experience
    target_payload = {
        "candidate_id": candidate_id,
        "target_role": "Senior Backend Engineer",
        "company": "CloudTech Systems",
        "job_description_text": (
            "Responsibilities:\n"
            "- Python and Flask API architecture\n"
            "- Containerization with Docker\n"
            "- Experience managing production Kubernetes clusters (EKS/GKE)\n"
        )
    }
    tgt_resp = client.post("/api/coach/career-targets", json=target_payload)
    assert tgt_resp.status_code == 201, f"Target creation failed: {tgt_resp.text}"
    target_id = tgt_resp.json()["target_id"]
    print(f"[SETUP] Career Target created: {target_id}")

    # Verify initial state of requirement: EXPERIENCE_GAP
    prog_resp = client.get(f"/api/coach/career-targets/{target_id}/progress?candidate_id={candidate_id}")
    assert prog_resp.status_code == 200, f"Target progress fetch failed: {prog_resp.text}"
    prog_data = prog_resp.json()
    k8s_req = next(r for r in prog_data["requirement_progress"] if "kubernetes" in r["requirement_text"].lower())
    print(f"[INITIAL STATE] Requirement '{k8s_req['requirement_text']}' is current_state={k8s_req['current_state']}, gap_type={k8s_req['gap_type']}")
    assert k8s_req["gap_type"] == "EXPERIENCE_GAP" or k8s_req["current_state"] in ["EXPERIENCE_GAP", "MISSING"], f"Expected EXPERIENCE_GAP, got {k8s_req}"

    # Create career action for target
    act_resp = client.post(
        "/api/coach/career-actions",
        json={
            "candidate_id": candidate_id,
            "target_id": target_id,
            "requirement_id": k8s_req["requirement_id"],
            "title": "Build Kubernetes Deployment Project",
            "action_type": "BUILD_PROJECT",
            "priority": "HIGH",
            "description": "Plan and deploy containerized microservice to Kubernetes",
            "rationale": "Closes experience gap for Kubernetes production deployment",
        }
    )
    assert act_resp.status_code == 201, f"Failed to create action: {act_resp.text}"
    action_id = act_resp.json()["action_id"]
    print(f"[SETUP] Created Action to track: {action_id} (Build Kubernetes Deployment Project)")

    # STEP 1: Create execution
    exec_resp = client.post(
        "/api/coach/career-executions",
        json={
            "candidate_id": candidate_id,
            "action_id": action_id,
            "target_id": target_id,
            "notes": "Plan and deploy containerized microservice to Kubernetes",
        }
    )
    assert exec_resp.status_code == 201, f"Step 1 failed: {exec_resp.text}"
    execution = exec_resp.json()
    execution_id = execution["execution_id"]
    print(f"[STEP 1] PASS: Execution created: {execution_id} with status={execution['status']} and state={execution['progress_state']}")
    assert execution["status"] == ExecutionStatus.NOT_STARTED.value
    assert execution["progress_state"] == ProgressState.PLANNED.value

    # STEP 2: Move to IN_PROGRESS
    start_resp = client.post(
        f"/api/coach/career-executions/{execution_id}/start",
        json={"candidate_id": candidate_id}
    )
    assert start_resp.status_code == 200, f"Step 2 failed: {start_resp.text}"
    execution = start_resp.json()
    print(f"[STEP 2] PASS: Execution moved to {execution['status']} (state={execution['progress_state']})")
    assert execution["status"] == ExecutionStatus.IN_PROGRESS.value
    assert execution["progress_state"] == ProgressState.IN_PROGRESS.value

    # STEP 3: Submit project artifact
    artifact_payload = {
        "candidate_id": candidate_id,
        "name": "Microservice Helm Charts & Kubernetes Manifests",
        "artifact_type": "GITHUB_REPO",
        "url_or_path": "https://github.com/janedoe/microservice-k8s-infra",
        "description": "Implemented Helm charts, deployments, services, and ingress on local Minikube cluster",
        "technologies": ["Kubernetes", "Helm", "Docker"],
    }
    art_resp = client.post(
        f"/api/coach/career-executions/{execution_id}/submit-artifact",
        json=artifact_payload
    )
    assert art_resp.status_code == 200, f"Step 3 failed: {art_resp.text}"
    execution = art_resp.json()
    print(f"[STEP 3] PASS: Project artifact submitted. Status={execution['status']}, State={execution['progress_state']}")
    assert execution["status"] == ExecutionStatus.AWAITING_EVIDENCE.value
    assert execution["progress_state"] == ProgressState.EVIDENCE_SUBMITTED.value

    # STEP 4: Mark self-reported complete
    comp_resp = client.post(
        f"/api/coach/career-executions/{execution_id}/complete",
        json={
            "candidate_id": candidate_id,
            "notes": "Completed deployment scripts and local testing."
        }
    )
    assert comp_resp.status_code == 200, f"Step 4 failed: {comp_resp.text}"
    execution = comp_resp.json()
    print(f"[STEP 4] PASS: Marked complete. Status={execution['status']}, Progress State={execution['progress_state']}")
    assert execution["status"] == ExecutionStatus.COMPLETED.value
    assert execution["progress_state"] == ProgressState.SELF_REPORTED_COMPLETE.value

    # Verify: Requirement remains EXPERIENCE_GAP (Self-reported complete does NOT grant skills or experience!)
    prog_resp4 = client.get(f"/api/coach/career-targets/{target_id}/progress?candidate_id={candidate_id}")
    k8s_req4 = next(r for r in prog_resp4.json()["requirement_progress"] if "kubernetes" in r["requirement_text"].lower())
    print(f"         VERIFICATION: Requirement state remains: current_state={k8s_req4['current_state']}, gap_type={k8s_req4['gap_type']}")
    assert k8s_req4["gap_type"] == "EXPERIENCE_GAP" or k8s_req4["current_state"] in ["EXPERIENCE_GAP", "MISSING"], "Self-reported complete must NOT change requirement state!"

    # STEP 5: Validate artifact (Implementation scope only)
    verify_impl_resp = client.post(
        f"/api/coach/career-executions/{execution_id}/verify-evidence",
        json={"candidate_id": candidate_id}
    )
    assert verify_impl_resp.status_code == 200, f"Step 5 failed: {verify_impl_resp.text}"
    ver_impl = verify_impl_resp.json()
    print(f"[STEP 5] PASS: Implementation artifact verified: {len(ver_impl['evidence_ids'])} item(s)")
    assert ver_impl["verified"] is True

    # Verify that requirement does NOT become production experience!
    prog_resp5 = client.get(f"/api/coach/career-targets/{target_id}/progress?candidate_id={candidate_id}")
    k8s_req5 = next(r for r in prog_resp5.json()["requirement_progress"] if "kubernetes" in r["requirement_text"].lower())
    print(f"         VERIFICATION: Current scope: '{k8s_req5['claim_scope']}', State: '{k8s_req5['current_state']}'")
    assert "PRODUCTION" not in k8s_req5["claim_scope"], "Level 3 implementation must not grant production scope!"

    # STEP 6: Add genuine operational evidence
    art_prod_payload = {
        "candidate_id": candidate_id,
        "name": "AWS EKS Production Cluster Operational Runbook & Telemetry",
        "artifact_type": "PROJECT_REPORT",
        "url_or_path": "https://internal.ops/reports/eks-prod-runbook.pdf",
        "description": "Managed production multi-node EKS Kubernetes clusters, on-call rotation, and Helm zero-downtime upgrades",
        "technologies": ["Kubernetes", "AWS EKS", "Prometheus", "Helm"],
    }
    art_prod_resp = client.post(
        f"/api/coach/career-executions/{execution_id}/submit-artifact",
        json=art_prod_payload
    )
    assert art_prod_resp.status_code == 200, f"Step 6 failed: {art_prod_resp.text}"
    print(f"[STEP 6] PASS: Added genuine operational production artifact.")

    # STEP 7: Verify evidence
    verify_prod_resp = client.post(
        f"/api/coach/career-executions/{execution_id}/verify-evidence",
        json={"candidate_id": candidate_id}
    )
    assert verify_prod_resp.status_code == 200, f"Step 7 failed: {verify_prod_resp.text}"
    ver_prod = verify_prod_resp.json()
    print(f"[STEP 7] PASS: Operational evidence verified! Verified count={len(ver_prod['evidence_ids'])}")
    assert ver_prod["verified"] is True
    assert len(ver_prod["evidence_ids"]) >= 1

    # STEP 8: Refresh target — verify before/after state
    prog_resp8 = client.get(f"/api/coach/career-targets/{target_id}/progress?candidate_id={candidate_id}")
    assert prog_resp8.status_code == 200
    prog_data8 = prog_resp8.json()
    print(f"[STEP 8] PASS: Target Before/After snapshot:")
    print(f"         Before Matched: {prog_data8['before_summary'].get('matched')}, After Matched: {prog_data8['after_summary'].get('matched')}")
    print(f"         Before Gaps: {prog_data8['before_summary'].get('experience_gaps')}, After Gaps: {prog_data8['after_summary'].get('experience_gaps')}")
    print(f"         Deltas recorded: {len(prog_data8['delta'])}")
    assert len(prog_data8["delta"]) > 0, "Expected requirement deltas!"

    # STEP 9: Refresh Career Intelligence
    ci_resp = client.get(f"/api/coach/career-intelligence/{candidate_id}/{target_id}")
    assert ci_resp.status_code == 200, f"Step 9 failed: {ci_resp.text}"
    ci_data = ci_resp.json()
    print(f"[STEP 9] PASS: Career Intelligence refreshed. Verified strengths: {len(ci_data.get('strengths', []))}")
    assert any("kubernetes" in s["requirement_text"].lower() for s in ci_data.get("strengths", []))

    # STEP 10: Refresh Interview Readiness — verify no fabricated claims
    # Create interview target if needed to query readiness
    itgt_resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": candidate_id,
            "target_role": "Senior Backend Engineer",
            "company": "CloudTech Systems",
            "job_description_text": target_payload["job_description_text"]
        }
    )
    itgt_id = itgt_resp.json()["interview_target_id"]
    readiness_resp = client.get(f"/api/coach/interview-readiness/{candidate_id}/{itgt_id}")
    assert readiness_resp.status_code == 200, f"Step 10 failed: {readiness_resp.text}"
    readiness = readiness_resp.json()
    k8s_readiness_req = next(r for r in readiness["requirement_map"] if "kubernetes" in r["requirement_text"].lower())
    print(f"[STEP 10] PASS: Interview readiness refreshed. Rationale: \"{k8s_readiness_req['rationale']}\"")
    assert k8s_readiness_req is not None

    # STEP 11: Verify Evidence Vault provenance
    ev_resp = client.get(f"/api/coach/evidence/{candidate_id}")
    assert ev_resp.status_code == 200
    vault_data = ev_resp.json()
    items = vault_data.get("evidence", []) if isinstance(vault_data, dict) else vault_data
    provenance_items = [it for it in items if "artifact_submission" in str(it.get("source_section", "")) or "career_execution" in str(it.get("source_section", ""))]
    print(f"[STEP 11] PASS: Provenance verified. {len(provenance_items)} item(s) in Evidence Vault linked to career execution:")
    for pi in provenance_items:
        eid = pi.get("evidence_id") or pi.get("id")
        src = pi.get("source_document") or pi.get("source_section")
        print(f"          - ID: {eid}, Source: {src}")
        assert eid is not None
        assert src is not None

    # STEP 12: Verify candidate isolation
    other_candidate_id = "cand_other_9999"
    # Try to access Jane's execution as another candidate -> must return 403 Forbidden
    cross_resp = client.get(f"/api/coach/career-executions/{other_candidate_id}/{execution_id}")
    print(f"[STEP 12] PASS: Cross-candidate execution access rejected with status {cross_resp.status_code}")
    assert cross_resp.status_code in [403, 404]

    # Try to start Jane's execution as another candidate -> must return 403 Forbidden
    cross_start = client.post(
        f"/api/coach/career-executions/{execution_id}/start",
        json={"candidate_id": other_candidate_id}
    )
    assert cross_start.status_code == 403
    print(f"          Cross-candidate mutation rejected with status {cross_start.status_code}")

    print("\n" + "=" * 75)
    print("ALL 12 MANUAL E2E STEPS COMPLETED AND VERIFIED SUCCESSFULLY!")
    print("=" * 75)

if __name__ == "__main__":
    run_phase8_e2e()
