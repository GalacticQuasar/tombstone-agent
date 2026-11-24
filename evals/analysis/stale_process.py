import json, re, sys, os, math, glob, statistics as st
from collections import defaultdict
from evals.tasks import TASKS
from tombstone.tools import ToolRegistry

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
CALIBS = {"qwen-explicit": "runs/distract-calib", "gptoss-explicit": "runs/distract-calib-gptoss",
          "qwen-implicit": "runs/distract-implicit"}
HEDGE = "however but although note earlier previous was changed from superseded conflict unclear possibly might".split()
HRE = re.compile(r"\b(" + "|".join(HEDGE) + r")\b", re.I)
_task_cache = {}

def get_task(tid):
    if tid not in _task_cache:
        t = TASKS[tid]() if callable(TASKS[tid]) else TASKS[tid]
        reg = ToolRegistry(t.make_tools())
        _task_cache[tid] = (t, reg)
    return _task_cache[tid]

def page(tid, url):
    t, reg = get_task(tid)
    return reg.dispatch("web_fetch", {"url": url})[0]

def parse_q(prompt):
    m = re.search(r"current (.+?) of (\S+), after", prompt) or re.search(r"What's the (.+?) of (\S+?)\?", prompt)
    return m.group(1), m.group(2)

def numre(v):
    return re.compile(r"(?<![\d.,])" + re.escape(str(v)) + r"(?!\d)")

def outdated(v4id, k, service, key):
    t, reg = get_task(v4id)
    day = 4 + k
    vals = set()
    for (tool, url) in t.labels:
        m = re.match(r"https://ops.example/notices/(\d+)-(\d+)-(.+)$", url)
        if not m or m.group(3) != service or int(m.group(1)) > day: continue
        d = int(m.group(1))
        for line in str(page(v4id, url)).splitlines():
            mm = re.match(r"- (.+?): (\d+) → (\d+)", line)
            if mm and mm.group(1) == key:
                if d < day: vals.add(int(mm.group(3)))
                else: vals.add(int(mm.group(2)))
    return vals

def load_runs(root):
    runs = {}
    for d in sorted(glob.glob(root + "/*stale*")):
        if d.endswith("unfinished") or not os.path.exists(d + "/summary.json"): continue
        s = json.load(open(d + "/summary.json"))
        runs[d] = s
    return runs

def analyse(d, s, v4id):
    ev = [json.loads(l) for l in open(d + "/trace.jsonl")]
    task, _ = get_task(s["task"])
    prompts = [p for p in ev[0]["phases"]] if "phases" in ev[0] else None
    nph = len(s["answers"])
    bounds = {}  # phase boundaries: last turn of phase k
    for e in ev:
        if e["event"] == "phase": bounds[e["phase"] - 1] = e["turn"]
    last_turn = max(e["turn"] for e in ev if e["event"] == "turn")
    bounds[nph - 1] = last_turn
    def phase_of(turn):
        for k in range(nph):
            if k in bounds and turn <= bounds[k]: return k
        return nph - 1
    ph = [dict(turns=0, fetch=0, refetch=0, earlier=0, compl=0, content=[]) for _ in range(nph)]
    seen = set(); cur = 1
    for e in ev:
        if e["event"] == "turn":
            cur = e["turn"]; k = phase_of(cur)
            ph[k]["turns"] += 1; ph[k]["compl"] += (e["usage"] or {}).get("completion") or 0
            if e.get("content"): ph[k]["content"].append(e["content"])
        elif e["event"] == "tool_result" and e["tool"] == "web_fetch":
            k = phase_of(cur); url = e["arguments"]["url"]
            ph[k]["fetch"] += 1
            if url in seen: ph[k]["refetch"] += 1
            seen.add(url)
            m = re.match(r"https://ops.example/notices/(?:day-)?(\d+)", url)
            if m and int(m.group(1)) < 4 + k: ph[k]["earlier"] += 1
    rows = []
    for k in range(nph):
        key, svc = parse_q(prompts[k])[0], parse_q(prompts[k])[1]
        od = outdated(v4id, k, svc, key)
        exp = task.phases[k].expected[0]
        od = {v for v in od if str(v) != str(exp)}
        ans = s["answers"][k] or ""
        def has(txt): return any(numre(v).search(txt) for v in od)
        r = ph[k]
        rows.append(dict(k=k, turns=r["turns"], fetch=r["fetch"], refetch=r["refetch"], earlier=r["earlier"],
                         compl=r["compl"], anslen=len(ans), hedge=len(HRE.findall(ans)),
                         hedge_words=HRE.findall(ans),
                         od_final=int(has(ans)), od_any=int(has(ans) or any(has(c) for c in r["content"])),
                         od=sorted(od), ans=ans, svc=svc, key=key, ok=s["phase_success"][k] if k < len(s["phase_success"]) else None))
    return rows

def sign_p(diffs):
    nz = [x for x in diffs if x != 0]; n = len(nz)
    if n == 0: return 1.0
    p = sum(1 for x in nz if x > 0)
    kk = min(p, n - p)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(kk + 1)) / 2 ** n)

def wil_p(diffs):
    try:
        from scipy.stats import wilcoxon
        nz = [x for x in diffs if x != 0]
        if len(nz) < 6: return float("nan")
        return wilcoxon(nz).pvalue
    except Exception: return float("nan")

METRICS = ["turns", "fetch", "refetch", "earlier", "compl", "anslen", "hedge", "od_final", "od_any"]
data = []  # dict(calib,length,variant,seed,ver,rows)
for cname, root in CALIBS.items():
    for d, s in load_runs(root).items():
        m = re.match(r"stale-v(\d)-(short|long)(?:-implicit)?_(\d)$", s["task"])
        if not m: continue
        ver, length, var = m.groups()
        v4id = s["task"].replace("-v1-", "-v4-")
        try: rows = analyse(d, s, v4id)
        except Exception as ex:
            print("skip", d, ex); continue
        data.append(dict(calib=cname, length=length, var=var, seed=s["seed"], ver=ver, rows=rows, acc=sum(1 for r in rows if r["ok"]), n=len(rows)))
idx = {(x["calib"], x["length"], x["var"], x["seed"], x["ver"]): x for x in data}
pairs = []
for (c, l, v, sd, ver), x in idx.items():
    if ver == "4" and (c, l, v, sd, "1") in idx: pairs.append((x, idx[(c, l, v, sd, "1")]))

out = []
def P(s=""): out.append(s)
def f(x): return f"{x:.2f}" if abs(x) < 100 else f"{x:.0f}"

def table(sel, label, phases):
    P(f"**{label}**  (run pairs: {len(sel)})"); P()
    P("| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |"); P("|---|---|---|---|---|---|---|")
    for mname in METRICS:
        a, b, dd = [], [], []
        for x4, x1 in sel:
            for r4, r1 in zip(x4["rows"], x1["rows"]):
                if r4["k"] in phases:
                    a.append(r4[mname]); b.append(r1[mname]); dd.append(r4[mname] - r1[mname])
        if not a: continue
        P(f"| {mname} | {f(st.mean(a))} | {f(st.mean(b))} | {f(st.mean(dd))} | {len(a)} | {sign_p(dd):.3f} | {wil_p(dd):.3f} |")
    P()

P("## Accuracy (phases correct, mean of 8)"); P()
for c in CALIBS:
    for ver in "41":
        xs = [x for x in data if x["calib"] == c and x["ver"] == ver]
        if xs: P(f"- {c} v{ver}: {st.mean(x['acc'] for x in xs):.2f}/8 over {len(xs)} runs")
P()
P("## Paired comparisons (v4 vs v1)"); P()
groups = [("pooled all calibrations", None, None)] + [(c, c, None) for c in CALIBS]
for gname, c, _ in groups:
    for length in (None, "short", "long"):
        sel = [p for p in pairs if (c is None or p[0]["calib"] == c) and (length is None or p[0]["length"] == length)]
        if not sel: continue
        lab = f"{gname} / {length or 'both lengths'}"
        table(sel, lab + " / phases 1-7", range(1, 8))
        if length is None:
            table(sel, lab + " / all phases 0-7", range(0, 8))
            table(sel, lab + " / phase 0 only", [0])

P("## Hedging marker rates in final answers (phases 1-7, pooled; share of answers containing marker)"); P()
P("| marker | v4 | v1 |"); P("|---|---|---|")
for w in HEDGE:
    r = []
    for ver in "41":
        rows = [rr for x in data if x["ver"] == ver for rr in x["rows"] if rr["k"] >= 1]
        r.append(sum(1 for rr in rows if w in [h.lower() for h in rr["hedge_words"]]) / len(rows))
    P(f"| {w} | {r[0]:.3f} | {r[1]:.3f} |")
P()

# collisions: how often the outdated values appear elsewhere in v4 task text (non asked-key lines + prompts)
P("## Chance-collision check"); P()
tot = coll = 0
for tid in sorted({x["task"] for x in []}): pass
seen_tasks = set()
for x4, _ in pairs:
    tid = f"stale-v4-{x4['length']}{'-implicit' if 'implicit' in x4['calib'] else ''}_{x4['var']}"
    if tid in seen_tasks: continue
    seen_tasks.add(tid)
    t, reg = get_task(tid)
    for r in x4["rows"]:
        k = r["k"]
        others = []
        for (tool, url) in t.labels:
            body = str(page(tid, url))
            for line in body.splitlines():
                mm = re.match(r"- (.+?): (\d+) → (\d+)", line)
                if mm and mm.group(1) == r["key"] and url.endswith(r["svc"]): continue
                others.append(line)
        txt = "\n".join(others)
        for v in r["od"]:
            tot += 1; coll += bool(numre(v).search(txt))
P(f"Across {len(seen_tasks)} distinct v4 tasks: {coll}/{tot} ({coll/max(tot,1):.0%}) (phase, outdated value) pairs also appear as a whole number somewhere else in the notice corpus (other settings' lines or rationale text; ignores 'Effective: day N' text). So a chance mention of an outdated value in an answer is possible but mostly requires the model to be quoting the asked setting's history.")
P()
P("v1 rows give the empirical chance baseline: od_final/od_any in the v1 columns above (in v1 the 'outdated' numbers are never shown, except possibly the pre-change value on today's line when it coincides).")
P()
P("## Excerpts: v4 final answers (phases 1-7) mentioning an outdated value"); P()
ex = [(x, r) for x, _ in pairs for r in x["rows"] if r["k"] >= 1 and r["od_final"]]
P(f"{len(ex)} of {sum(1 for x,_ in pairs for r in x['rows'] if r['k']>=1)} v4 phase-final answers (phases 1-7) mention an outdated value.")
P()
import random
random.seed(1)
for x, r in random.sample(ex, min(4, len(ex))):
    a = r["ans"].replace("\n", " ")
    P(f"- {x['calib']} {x['length']} var{x['var']} s{x['seed']} phase {r['k']} ({r['svc']} / {r['key']}; outdated {r['od']}):")
    P(f"  > {a[-400:] if len(a)>400 else a}")
P()
open(os.path.join(OUT, "stale_report_body.md"), "w").write("\n".join(out))
print("\n".join(out))

# extra: share of final answers (phases 1-7) containing an arrow "→"/"->" (i.e. enumerating change history)
extra = ["## Extra: answers enumerating history with arrows (phases 1-7)", "", "| calibration | v4 | v1 |", "|---|---|---|"]
for c in CALIBS:
    cells = []
    for ver in "41":
        rows = [r for x in data if x["calib"] == c and x["ver"] == ver for r in x["rows"] if r["k"] >= 1]
        cells.append(f"{sum(1 for r in rows if '→' in r['ans'] or '->' in r['ans'])}/{len(rows)}")
    extra.append(f"| {c} | {cells[0]} | {cells[1]} |")
open(os.path.join(OUT, "stale_report_extra.md"), "w").write("\n".join(extra))
print("\n".join(extra))
