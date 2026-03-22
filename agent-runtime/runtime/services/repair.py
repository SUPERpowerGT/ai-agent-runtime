from __future__ import annotations


def build_failure_report(
    *,
    task_spec: dict,
    llm_result: str,
    llm_error: str | None,
    findings: list[dict],
) -> dict:
    """
    Build a structured validation report that can be consumed by repair logic.
    """
    summary = "Validation failed."
    if findings:
        summary = findings[0]["message"]
    elif llm_result == "FAIL" and llm_error:
        summary = llm_error

    return {
        "status": "FAIL",
        "summary": summary,
        "task_mode": task_spec.get("task_mode", "generate"),
        "findings": findings,
        "llm_verdict": {
            "result": llm_result,
            "error": llm_error,
        },
    }


def build_fix_strategy(*, task_spec: dict, failure_report: dict) -> dict:
    """
    Turn a failure report into a generic repair strategy.
    """
    findings = failure_report.get("findings", [])
    priorities = [finding["message"] for finding in findings]

    preserve = []
    if task_spec.get("code_contracts"):
        preserve.append("Preserve the existing public function names and parameter shapes.")
    if task_spec.get("behavior_summaries"):
        preserve.append("Preserve the behaviors described in the extracted behavior summaries.")
    if task_spec.get("constraints"):
        preserve.append("Respect the extracted user constraints.")

    rules = [
        "Fix the failing validation findings before making any optional cleanup changes.",
        "Keep unrelated code unchanged unless a broader edit is required to satisfy validation.",
        "Prefer the smallest change that resolves the current validation failures.",
    ]

    task_mode = task_spec.get("task_mode", "generate")
    if task_mode in {"optimize", "rewrite"}:
        rules.append("Preserve the original external behavior while resolving the findings.")

    return {
        "goal": "Produce a corrected version of the current code that satisfies the latest validation report.",
        "task_mode": task_mode,
        "priorities": priorities or ["Address the latest validation failure."],
        "preserve": preserve,
        "rules": rules,
    }


def summarize_findings(findings: list[dict]) -> str:
    if not findings:
        return "No validation findings."
    return "; ".join(finding["message"] for finding in findings)
