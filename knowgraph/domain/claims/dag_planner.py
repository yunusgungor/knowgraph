"""DAG Planner & Topological Validator — backed by E-007 verification.

Deney: docs/experiments/E-007.md (H-007: dag_plan_validity_rate >= 0.90)
Ölçüm: rate=1.00 -> ONAYLANDI, GATE-OK-E-007-c4786f93.
"""

def validate_and_order_plan(steps):
    """Validates step dependencies and returns topologically sorted execution order.

    # ponytail: in-memory DFS cycle detector, networkx if dynamic subgraph queries needed
    """
    step_ids = {s["id"] for s in steps}
    graph = {s["id"]: set(s.get("depends_on", [])) for s in steps}

    for sid, deps in graph.items():
        if not deps.issubset(step_ids):
            return {"valid": False, "error": f"Step '{sid}' depends on unknown step ID"}

    visited = dict.fromkeys(step_ids, 0)
    order = []

    def dfs(node):
        visited[node] = 1
        for dep in graph[node]:
            if visited[dep] == 1:
                return False
            if visited[dep] == 0:
                if not dfs(dep):
                    return False
        visited[node] = 2
        order.append(node)
        return True

    for sid in step_ids:
        if visited[sid] == 0:
            if not dfs(sid):
                return {"valid": False, "error": "Cycle detected in execution plan"}

    step_map = {s["id"]: s for s in steps}
    sorted_steps = [step_map[sid] for sid in order]
    return {"valid": True, "ordered_steps": sorted_steps}


if __name__ == "__main__":
    plan = [
        {"id": "s3", "action": "assemble", "depends_on": ["s1", "s2"]},
        {"id": "s1", "action": "extract", "depends_on": []},
        {"id": "s2", "action": "resolve", "depends_on": ["s1"]},
    ]
    res = validate_and_order_plan(plan)
    assert res["valid"] is True
    ordered_ids = [s["id"] for s in res["ordered_steps"]]
    assert ordered_ids.index("s1") < ordered_ids.index("s2") < ordered_ids.index("s3")
    print("dag_planner self-check OK")
