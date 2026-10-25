from finbo.evals import as_json, run_offline


def test_offline_suites_have_no_misses():
    # Regression guard: if a guardrail change breaks a labelled case, this names it.
    results = run_offline()
    misses = {r.name: r.failures for r in results if r.failures}
    assert misses == {}
    assert {r.name for r in results} == {
        "PII redaction",
        "Prompt-injection scan",
        "Refusal policy",
        "Grounding check",
    }
    assert all("passed" in row for row in as_json(results))
