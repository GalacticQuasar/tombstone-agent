import json, os, re, sys, glob, math, collections
from statistics import mean
from evals.tasks import TASKS
from evals.tasks.latent import CONCEPTS
from tombstone.tools import ToolRegistry

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CALIBS = {"qwen-explicit": "runs/distract-calib", "gptoss-explicit": "runs/distract-calib-gptoss",
          "qwen-implicit": "runs/distract-implicit"}
HEDGE = "however but although note earlier previous another also conflict unclear possibly might".split()
HRE = re.compile(r"\b(" + "|".join(HEDGE) + r")\b", re.I)
TID = re.compile(r"latent-(on|off)-(short|long)(?:-(implicit))?_(\d+)$")
OUT = sys.argv[1] if len(sys.argv) > 1 else "."

_info = {}
def task_info(tid):
    if tid in _info: return _info[tid]
    t = TASKS[tid]; reg = ToolRegistry(t.make_tools())
    urls = [u for (tool, u) in t.labels if tool == "web_fetch"]
    pages = {u: reg.dispatch("web_fetch", {"url": u})[0] for u in urls}
    _info[tid] = (t, pages); return _info[tid]

def name_of(text):
    m = re.search(r"material about (.+?), who lived in", text); return m.group(1)

def setup(tid):
    """per-phase decoy/lexical names. cross decoy url found via on-task."""
    m = TID.match(tid); on_id = f"latent-on-{m.group(2)}{'-implicit' if m.group(3) else ''}_{m.group(4)}"
    ton, pon = task_info(on_id); t, pages = task_info(tid)
    res = {}
    for k, ph in enumerate(t.phases):
        prompt = ph.prompt if hasattr(ph, "prompt") else str(ph)
        cands = [c for c in range(len(CONCEPTS)) if CONCEPTS[c][0] in prompt]
        c = max(cands, key=lambda c: len(CONCEPTS[c][0]))
        lex = [u for u, tx in pages.items() if CONCEPTS[c][3] in tx]
        ans = [u for u, tx in pages.items() if CONCEPTS[c][1] in tx]
        cross = [u for u, tx in pon.items() if CONCEPTS[c][2] in tx]
        res[k] = dict(lex=name_of(pages[lex[0]]) if lex else None,
                      cross=name_of(pon[cross[0]]) if cross and k > 0 else None,
                      cross_url=cross[0] if cross and k>0 else None,
                      expected=ph.expected[0] if hasattr(ph, "expected") else None)
    return res

def analyse(rundir, tid):
    ev = [json.loads(l) for l in open(os.path.join(rundir, "trace.jsonl"))]
    turns = [e for e in ev if e["event"] == "turn"]
    pe = {e["phase"]: e["turn"] for e in ev if e["event"] == "phase"}
    last = max(t["turn"] for t in turns)
    S = setup(tid); out = {}
    fetched = set()
    nph = 8
    for k in range(nph):
        lo = 0 if k == 0 else pe.get(k)
        hi = pe.get(k + 1, last) if k + 1 < nph else last
        if lo is None or (k + 1 < nph and (k + 1) not in pe): 
            # incomplete: phase not finished
            if k + 1 < nph and (k+1) not in pe: break
        ts = [t for t in turns if lo < t["turn"] <= hi]
        # note: fetched must be accumulated over earlier phases in order
        nf = ns = refetch = 0
        for t in ts:
            for tc in t["tool_calls"]:
                if tc["name"] == "web_fetch":
                    nf += 1
                    a = tc["arguments"]; a = json.loads(a) if isinstance(a, str) else a
                    u = a.get("url")
                    if u in fetched: refetch += 1
                    fetched.add(u)
                elif tc["name"] == "web_search": ns += 1
        if k == 0: continue
        allc = " ".join((t["content"] or "") for t in ts)
        fin = (ts[-1]["content"] or "") if ts else ""
        s = S[k]
        out[k] = dict(turns=len(ts), fetch=nf, search=ns, refetch=refetch,
                      comp=sum(t["usage"]["completion"] for t in ts), anslen=len(fin),
                      hedge=len(HRE.findall(fin)),
                      dec_ment=int(bool(s["cross"] and s["cross"] in allc)),
                      dec_final=int(bool(s["cross"] and s["cross"] in fin)),
                      lex_final=int(bool(s["lex"] and s["lex"] in fin)),
                      _allc=allc, _decoy=s["cross"], _k=k)
    return out

def sign_p(diffs):
    d = [x for x in diffs if abs(x) > 1e-12]; n = len(d)
    if n == 0: return 1.0, 0
    pos = sum(x > 0 for x in d); k = min(pos, n - pos)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n * 2
    return min(1.0, p), n

# collect
runs = {}  # (calib, scope, length, variant, seed, on/off) -> metrics
for cname, cdir in CALIBS.items():
    for d in sorted(os.listdir(os.path.join(REPO, cdir))):
        if "unfinished" in d: continue
        p = os.path.join(REPO, cdir, d)
        if not os.path.exists(os.path.join(p, "summary.json")): continue
        s = json.load(open(os.path.join(p, "summary.json")))
        m = TID.match(s["task"])
        if not m: continue
        key = (cname, "implicit" if m.group(3) else "explicit", m.group(2), int(m.group(4)), s["seed"], m.group(1))
        runs[key] = (analyse(p, s["task"]), s)   # later dirs overwrite earlier (sorted by timestamp)

METRICS = ["turns", "fetch", "search", "refetch", "comp", "anslen", "hedge", "dec_ment", "dec_final", "lex_final"]
pairs = collections.defaultdict(list)  # (calib,length) -> list of (on_phase_dict, off_phase_dict)
npairs_runs = collections.Counter()
for key, (on, son) in runs.items():
    if key[5] != "on": continue
    off = runs.get(key[:5] + ("off",))
    if not off: continue
    npairs_runs[(key[0], key[2])] += 1
    for k in on:
        if k in off[0]: pairs[(key[0], key[2])].append((on[k], off[0][k], key, k))

def table(title, plist):
    L = [f"### {title}  (n phase-pairs = {len(plist)})", "", "| metric | on | off | diff (on-off) | sign-test p (n nonzero) |", "|---|---|---|---|---|"]
    for mt in METRICS:
        a = [p[0][mt] for p in plist]; b = [p[1][mt] for p in plist]
        pv, n = sign_p([x - y for x, y in zip(a, b)])
        L.append(f"| {mt} | {mean(a):.2f} | {mean(b):.2f} | {mean(a)-mean(b):+.2f} | {pv:.3f} ({n}) |")
    L.append("")
    return "\n".join(L)

md = ["# Latent-task process analysis (strategy none)", "",
"## Method", "",
"Per run, phases 1-7 (phase 0 has no cross decoy) are delimited by the trace `phase` events (phase k = turns after the turn that answered k-1 up to the turn answering k). Metrics: turns, web_fetch/web_search counts, re-fetches of URLs fetched earlier in the run, completion tokens, final-answer length, hedge-word count in final answer, `dec_ment` = cross-decoy resident's full name appears in any assistant content in the phase (on-task: the cross-decoy resident; off-task: the same slot resident, baseline), `dec_final` = name in final answer, `lex_final` = lexical-decoy resident name in final answer. Each on-run is paired with the off-run of the same calibration/length/scope/variant/seed; the unit is the phase (phases within a run are not independent, so p-values are optimistic). p = exact two-sided sign test on nonzero per-phase differences; no multiple-comparison correction (10 metrics x many strata). Runs with duplicate dirs: latest kept. Incomplete runs contribute only phases they finished (a phase is included only if the next phase event or the run end exists).", ""]
cnt = ["## Run pairs and accuracy", "", "| calib | length | run pairs | phase-pairs | on acc | off acc |", "|---|---|---|---|---|---|"]
def acc(cn, ln, which):
    v = [sum(s["phase_success"]) / max(1, len(s["phase_success"])) for k, (o, s) in runs.items() if k[0] == cn and k[2] == ln and k[5] == which]
    return f"{mean(v):.3f}" if v else "-"
for (cn, ln) in sorted(pairs): cnt.append(f"| {cn} | {ln} | {npairs_runs[(cn,ln)]} | {len(pairs[(cn,ln)])} | {acc(cn,ln,'on')} | {acc(cn,ln,'off')} |")
md += cnt + [""]
md.append("## Tables per calibration and length\n")
for (cn, ln) in sorted(pairs): md.append(table(f"{cn} / {ln}", pairs[(cn, ln)]))
for cn in CALIBS:
    pl = [p for (c, l), v in pairs.items() if c == cn for p in v]
    md.append(table(f"{cn} / both lengths", pl))
md.append(table("POOLED all calibrations and lengths", [p for v in pairs.values() for p in v]))
md.append(table("POOLED, Qwen only (explicit + implicit)", [p for (c, l), v in pairs.items() if c.startswith("qwen") for p in v]))

md.append("## Decoy-name mention counts (phases)\n\n| calib | length | on mentions | off mentions | on in final | off in final | phase-pairs |\n|---|---|---|---|---|---|---|")
for (cn, ln), pl in sorted(pairs.items()):
    md.append(f"| {cn} | {ln} | {sum(p[0]['dec_ment'] for p in pl)} | {sum(p[1]['dec_ment'] for p in pl)} | {sum(p[0]['dec_final'] for p in pl)} | {sum(p[1]['dec_final'] for p in pl)} | {len(pl)} |")
allp = [p for v in pairs.values() for p in v]
md.append(f"| ALL | | {sum(p[0]['dec_ment'] for p in allp)} | {sum(p[1]['dec_ment'] for p in allp)} | {sum(p[0]['dec_final'] for p in allp)} | {sum(p[1]['dec_final'] for p in allp)} | {len(allp)} |\n")

# excerpts
md.append("## Excerpts (on-run phases where decoy name is mentioned)\n")
shown = 0; seen = set()
for (cn, ln), pl in sorted(pairs.items()):
    for on, off, key, k in pl:
        if on["dec_ment"] and cn not in seen and shown < 3:
            seen.add(cn); shown += 1
            t = on["_allc"]; i = t.index(on["_decoy"])
            md.append(f"**{key[:5]} phase {k}, decoy = {on['_decoy']}**\n\n> " + t[max(0, i - 150): i + 150].replace("\n", " ") + "\n")
if shown < 3:
    for (cn, ln), pl in sorted(pairs.items()):
        for on, off, key, k in pl:
            if on["dec_ment"] and shown < 3 and (key, k) not in seen:
                seen.add((key, k)); shown += 1
                t = on["_allc"]; i = t.index(on["_decoy"])
                md.append(f"**{key[:5]} phase {k}, decoy = {on['_decoy']}**\n\n> " + t[max(0, i - 150): i + 150].replace("\n", " ") + "\n")
if shown == 0: md.append("(no on-run phase mentions the decoy name)\n")
open(os.path.join(OUT, "latent_report.md"), "w").write("\n".join(md))
print("\n".join(md))
