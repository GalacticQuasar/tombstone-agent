"""Lossy summaries: a later question needs an exact string from an early page that wasn't asked then.

A build catalog reached only by links (web_fetch only, no search; URLs are opaque). Each
phase: from the index, open a component's release list, then open releases until one
"Fixes #N", and report its build ID. Other releases of that component mention #N in
near-miss ways (mitigates it, adds diagnostics for it, fixes a digit-swapped issue). The last
phase asks for the arm64 checksum of the phase-0 build, without repeating any URL, so it has
to come from the original page or a summary that kept the exact string or URL.

Predicted loser: compact. Predicted winner: self_forget (retrieves the original).
"""

from __future__ import annotations

import random

from evals.env.web import MockWeb, Page

from .base import Phase, SourceLabel, Task, final_phase

COMPONENTS = ("parser", "scheduler", "gateway", "indexer", "renderer", "uploader", "resolver")
PLATFORMS = ("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64", "windows-amd64", "freebsd-amd64")
_AREAS = "cache config logging retries timeouts metrics docs packaging tests startup shutdown tls".split()
_STEPS = "fetch deps|compile core|compile plugins|link|run unit tests|run integration tests|package|sign|upload".split("|")
N_PHASES = 5
RELEASES = 8
INDEX = "https://builds.example/index"


def _hex(rng: random.Random, n: int) -> str:
    return "".join(rng.choices("0123456789abcdef", k=n))


def _swap(n: int, rng: random.Random) -> int:
    """A different 4-digit issue number with two adjacent digits swapped."""
    s = str(n)
    for i in rng.sample(range(3), 3):
        t = s[:i] + s[i + 1] + s[i] + s[i + 2:]
        if t != s and t[0] != "0":
            return int(t)
    return n + 9


def _release_page(rng: random.Random, comp: str, version: str, build: str, sums: dict[str, str],
                  key_line: str | None) -> str:
    notes = [f"- {rng.choice(['Improves', 'Refactors', 'Cleans up', 'Speeds up', 'Documents'])} "
             f"{rng.choice(_AREAS)} handling (#{rng.randint(1000, 9999)})" for _ in range(rng.randint(8, 12))]
    if key_line:
        notes.insert(rng.randrange(len(notes)), f"- {key_line}")
    t = rng.randint(8, 20) * 3600
    log = []
    for i, step in enumerate(_STEPS, 1):
        for _ in range(rng.randint(3, 6)):
            t += rng.randint(3, 400)
            log.append(f"[{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}] step {i}/{len(_STEPS)}: {step} "
                       f"({rng.choice(['ok', 'cache hit', 'ok', 'retried once', 'ok'])})")
    return "\n".join([
        f"{comp} {version}",
        f"build id: {build}",
        f"released: 2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}",
        "", "Changes:", *notes,
        "", "Artifacts (sha256, first 16 hex):", *(f"  {p:14} {h}" for p, h in sums.items()),
        "", "Build log (excerpt):", *log,
    ])


def exact(variant: int) -> Task:
    rng = random.Random(f"exact-{variant}")
    comps = rng.sample(COMPONENTS, len(COMPONENTS))
    url = lambda: f"https://builds.example/r/{_hex(rng, 10)}"  # noqa: E731
    pages: list[Page] = []
    labels: dict[tuple[str, str], SourceLabel] = {("web_fetch", INDEX): SourceLabel("needed_later", 0)}
    index_lines = ["Build catalog", "", "Components:"]
    asked: list[tuple[str, int, str, dict[str, str]]] = []  # component, issue, build id, checksums

    for ci, comp in enumerate(comps):
        comp_url = url()
        index_lines.append(f"- {comp}: {comp_url}")
        phase = ci if ci < N_PHASES else 0
        issue = rng.randint(1000, 9999)
        fix_at = rng.randrange(2, RELEASES)  # near misses come both before and after the fix
        near = rng.sample([i for i in range(RELEASES) if i != fix_at], 3)
        key_lines = {
            fix_at: f"Fixes #{issue}: {rng.choice(_AREAS)} {rng.choice(['crash', 'leak', 'hang', 'corruption'])} under load",
            near[0]: f"Mitigates #{issue} (partial; the full fix lands in a later release)",
            near[1]: f"Adds diagnostics for #{issue}",
            near[2]: f"Fixes #{_swap(issue, rng)}: {rng.choice(_AREAS)} regression",
        }
        major = rng.randint(1, 4)
        rel_lines = [f"{comp} releases", ""]
        for r in range(RELEASES):
            version, rurl = f"{major}.{r}.{rng.randint(0, 3)}", url()
            build = _hex(rng, 12)
            sums = {p: _hex(rng, 16) for p in PLATFORMS}
            pages.append(Page(rurl, f"{comp} {version}", _release_page(rng, comp, version, build, sums, key_lines.get(r))))
            rel_lines.append(f"- {comp} {version}: {rurl}")
            label = "distractor"
            if r == fix_at and ci < N_PHASES:
                label = "needed_later" if ci == 0 else "relevant"
                asked.append((comp, issue, build, sums))
            labels[("web_fetch", rurl)] = SourceLabel(label, phase)
        pages.append(Page(comp_url, f"{comp} releases", "\n".join(rel_lines)))
        labels[("web_fetch", comp_url)] = SourceLabel("relevant" if ci < N_PHASES else "distractor", phase)
    pages.append(Page(INDEX, "Build catalog", "\n".join(index_lines)))

    phases: list[Phase] = []
    for i, (comp, issue, build, _) in enumerate(asked):
        lead = f"The build catalog starts at {INDEX} (use web_fetch; there is no search). " if i == 0 else "Next, from the same catalog: "
        phases.append(final_phase(
            f"{lead}Find the {comp} release that fixes issue #{issue}. What is its build id? "
            f"Other releases mention the issue too, so check what each one says.",
            "<build id>", build,
        ))
    comp0, _, _, sums0 = asked[0]
    phases.append(final_phase(
        f"Back to the {comp0} build from the first question: what is the sha256 prefix of its linux-arm64 artifact?",
        "<16 hex characters>", sums0["linux-arm64"],
    ))

    def tools():
        return [t for t in MockWeb(pages).tools() if t.name == "web_fetch"]

    return Task(id=f"exact_{variant}", phases=phases, make_tools=tools, labels=labels)
