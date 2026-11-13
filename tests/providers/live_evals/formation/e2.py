import asyncio
import fx
from fx import datasets, prompts
from e45 import brief

async def main():
    ds = datasets.e2_set()
    texts = fx.prompt_texts(ds)
    p_ans = prompts.build_m4_payload((), texts, ())
    p_q = {"themes": [], "answers": ds["answers"], "questions": ds["questions"], "blockedPairs": []}
    ports = {"muse-spark-1.3": fx.make_port("muse-spark-1.3"), "muse-ember-1.0": fx.make_port("muse-ember-1.0"),
             "muse-wonder-1.0": fx.make_port("muse-wonder-1.0", max_attempts=1)}
    plan = []
    for m, n in (("muse-spark-1.3", 2), ("muse-ember-1.0", 2), ("muse-wonder-1.0", 1)):
        for i in range(1, n + 1):
            plan.append((m, i, "answers_only", prompts.PROMPT_VERSION_M4, p_ans))
            plan.append((m, i, "with_questions", fx.PV_Q, p_q))
    res = await asyncio.gather(*(fx.run_m4(ports[m], pv, p, ds, f"e2-{m}-{c}-{i}") for m, i, c, pv, p in plan))
    rows = []
    for (m, i, c, pv, _), r in zip(plan, res):
        rows.append({"model": m, "run": i, "condition": c, "promptVersion": pv, **r})
        print(m, c, i, brief(r))
    fx.save("E2_questions_matter", rows, {"keywordBaseline": fx.baseline_metrics(ds),
            "dataset": "synthetic 30 players, 6 latent groups x5, 2 short answers each to 6 questions; surface words collide across groups"})
    print(fx.spend())
asyncio.run(main())
