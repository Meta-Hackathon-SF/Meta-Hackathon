import fx, json
from fx import datasets
from server.matching.models import PromptText
from server.matching.baseline import baseline_groups
from server.matching.evaluation import pair_metrics
ds = datasets.e2_set()
qonly = [PromptText(a["id"], f"zz{a['questionId']}zz", 1.0) for a in ds["answers"]]
qtext = [PromptText(a["id"], a["text"] + " " + dict((q["questionId"], q["text"]) for q in ds["questions"])[a["questionId"]], 1.0) for a in ds["answers"]]
m1 = pair_metrics(baseline_groups(qonly), ds["gold"]).to_wire()
m2 = pair_metrics(baseline_groups(qtext), ds["gold"]).to_wire()
print("questionId-only keyword baseline", m1); print("answer+question keyword baseline", m2)
d = json.loads(fx.OUT.read_text()); d["E2_questions_matter"]["questionIdOnlyBaseline"] = m1; d["E2_questions_matter"]["keywordBaselineWithQuestionText"] = m2
fx.OUT.write_text(json.dumps(d, indent=1))
