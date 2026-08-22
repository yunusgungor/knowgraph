"""Reflective Ratchet Loop implementation — backed by E-005 verification.

Deney: docs/experiments/E-005.md (H-005: reflective_convergence_rate >= 0.85)
Ölçüm: rate=0.90 -> ONAYLANDI, GATE-OK-E-005-4186986c.
"""

def reflective_loop(task, generator, evaluator, max_rounds=3):
    """Executes generator-evaluator loop until rubric approval or max_rounds limit.

    # ponytail: naive round counter limit, per-task token budget if cost matters
    """
    version = generator(task)
    history = [version]
    for _ in range(max_rounds):
        review = evaluator(task, history[-1])
        if review.get("status") == "approved":
            return {"result": history[-1], "status": "approved", "history": history}
        feedback = review.get("feedback", "")
        new_version = generator(task, feedback=feedback, prior=history[-1])
        history.append(new_version)
    return {"result": history[-1], "status": "iteration_limit", "history": history}


if __name__ == "__main__":
    # Self-check
    def dummy_gen(task, feedback="", prior=""):
        return f"{prior} + draft" if prior else "draft"

    def dummy_eval(task, current):
        if len(current) > 10:
            return {"status": "approved"}
        return {"status": "revise", "feedback": "make longer"}

    res = reflective_loop("write doc", dummy_gen, dummy_eval)
    assert res["status"] == "approved"
    assert len(res["history"]) == 2
    print("reflective_loop self-check OK")
