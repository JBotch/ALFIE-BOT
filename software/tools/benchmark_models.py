"""Compare local AI models on this computer.

    python tools/benchmark_models.py                      # qwen3:0.6b, gemma3:1b, qwen3:1.7b
    python tools/benchmark_models.py --models qwen3:0.6b --repeat 3
    python tools/benchmark_models.py --mock               # no Ollama needed: tries the tool itself

Asks each model the questions in benchmarks/questions.json with AlfieBot's
real personality prompt, then checks every answer exactly as the robot
would (valid JSON, personality rules, output safety rules). Questions the
robot answers without AI (hand-written replies, fixed safety replies) are
still asked, to compare the models, and marked in the report. Saves a CSV and
a Markdown report in benchmarks/results/ and adds the timings to the AI
statistics database (data/alfiebot.db), labelled with this machine.

Models must already be installed (ollama pull <model>): this tool never
downloads anything. Laptop results don't predict a Raspberry Pi 5; run the
same benchmark on the Pi to measure it.
"""

import argparse
import csv
import datetime as dt
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alfiebot.ai.local_provider import DEFAULT_URL, RECOMMENDED_MODELS, OllamaProvider  # noqa: E402
from alfiebot.ai.mock_provider import MockProvider  # noqa: E402
from alfiebot.ai.performance import PerformanceTracker, machine_label  # noqa: E402
from alfiebot.ai.provider_base import AIRequest  # noqa: E402
from alfiebot.config import load_config  # noqa: E402
from alfiebot.conversation.intents import match_intent  # noqa: E402
from alfiebot.core.actions import InvalidResponse  # noqa: E402
from alfiebot.core.brain import check_reply  # noqa: E402
from alfiebot.core.personality import Personality  # noqa: E402
from alfiebot.core.safety import check_input  # noqa: E402
from alfiebot.face.controller import AI_EXPRESSIONS  # noqa: E402
from alfiebot.storage.database import Database  # noqa: E402

QUESTIONS = ROOT / "benchmarks" / "questions.json"
FIELDS = ["model", "category", "question", "run", "alfiebot", "ok", "valid", "problem", "latency_s",
          "completion_tokens", "tokens_per_s", "speech", "expression", "action"]


def handled_without_ai(text: str) -> str:
    """How AlfieBot answers this without asking the AI, or "" if it asks the AI."""
    check = check_input(text)
    if check.topic:
        return f"fixed safety reply ({check.topic})"
    intent = match_intent(text).intent
    if intent not in ("fallback", "unknown"):
        return f"hand-written reply ({intent})"
    return ""


def load_questions(path=QUESTIONS):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["questions"]


def run_model(provider, questions, personality, repeat, timeout, max_tokens, log=print):
    """Rows for one model (warm-up first, so loading isn't counted)."""
    system = personality.system_prompt(e.value for e in AI_EXPRESSIONS)
    start = time.monotonic()
    warm = provider.generate(AIRequest([{"role": "user", "content": "Hello!"}], system=system,
                                       timeout_s=max(timeout, 120.0), max_tokens=max_tokens))
    load_s = time.monotonic() - start
    if not warm.ok:
        log(f"  warm-up failed: {warm.error}")
    rows = []
    for run in range(1, repeat + 1):
        for q in questions:
            result = provider.generate(AIRequest([{"role": "user", "content": q["text"]}], system=system,
                                                 timeout_s=timeout, max_tokens=max_tokens))
            row = {"model": provider.model, "category": q["category"], "question": q["text"], "run": run,
                   "alfiebot": handled_without_ai(q["text"]), "ok": result.ok, "valid": False, "problem": result.error or "",
                   "latency_s": round(result.latency_s, 3), "completion_tokens": result.completion_tokens,
                   "tokens_per_s": round(result.tokens_per_s, 1) if result.tokens_per_s else "",
                   "speech": "", "expression": "", "action": "", "_result": result}
            if result.ok:
                try:
                    response, notes = check_reply(personality, result.text)
                    row.update(valid=True, problem="; ".join(notes), speech=response.speech,
                               expression=response.expression.value, action=response.action or "")
                except InvalidResponse as exc:
                    row.update(problem=str(exc), speech=result.text[:200])
            mark = "ok " if row["valid"] else "BAD"
            log(f"  {mark} {row['latency_s']:6.2f} s  {q['category']:<11} {q['text'][:40]:<40} "
                f"{row['speech'][:60] or row['problem'][:60]}")
            rows.append(row)
    return rows, load_s


def summarise(rows, load_s):
    times = sorted(r["latency_s"] for r in rows if r["ok"])
    speeds = [r["tokens_per_s"] for r in rows if r["tokens_per_s"] != ""]
    return {
        "answers": len(rows),
        "valid": sum(1 for r in rows if r["valid"]),
        "errors": sum(1 for r in rows if not r["ok"]),
        "handled": sum(1 for r in rows if r["alfiebot"]),
        "median_s": statistics.median(times) if times else None,
        "p90_s": times[min(len(times) - 1, int(round(0.9 * (len(times) - 1))))] if times else None,
        "tokens_per_s": statistics.mean(speeds) if speeds else None,
        "load_s": load_s,
    }


def write_report(path, machine, summaries, rows, ollama_version):
    fmt = lambda v, f="{:.2f}": "-" if v is None else f.format(v)  # noqa: E731
    lines = [f"# AlfieBot model benchmark: {machine}", "",
             f"{dt.datetime.now():%Y-%m-%d %H:%M}. Ollama {ollama_version or 'n/a'}. "
             f"{len(load_questions())} questions per run. Times are for this machine only; "
             "a Raspberry Pi 5 is not measured by this report.", "",
             "Usable = the answer passed every check AlfieBot makes before speaking. Questions marked "
             "*no AI* are answered by AlfieBot itself (a hand-written or fixed safety reply); the model's "
             "answer is shown only to compare the models.", "",
             "| Model | Usable answers | Errors | Median | 90% | Tokens/s | First load |",
             "|---|---|---|---|---|---|---|"]
    for model, sm in summaries.items():
        lines.append(f"| {model} | {sm['valid']}/{sm['answers']} | {sm['errors']} | {fmt(sm['median_s'])} s | "
                     f"{fmt(sm['p90_s'])} s | {fmt(sm['tokens_per_s'], '{:.0f}')} | {fmt(sm['load_s'], '{:.1f}')} s |")
    lines += ["", "## Answers", ""]
    for model in summaries:
        lines += [f"### {model}", "", "| Question | Time | Answer |", "|---|---|---|"]
        for r in rows:
            if r["model"] == model:
                answer = r["speech"] if r["valid"] else f"**not usable:** {r['problem']}"
                answer = re.sub(r"\s+", " ", answer).replace("|", "/")
                if r["alfiebot"]:
                    answer = f"*no AI: {r['alfiebot']}.* Model: {answer}"
                lines.append(f"| {r['question']} | {r['latency_s']:.1f} s | {answer} |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8-sig")  # the BOM keeps Windows tools from garbling it


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--models", nargs="+", default=list(RECOMMENDED_MODELS))
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--repeat", type=int, default=1, help="ask every question this many times")
    p.add_argument("--timeout", type=float, default=60.0, help="seconds per answer")
    p.add_argument("--max-tokens", type=int, default=160)
    p.add_argument("--mock", action="store_true", help="use the pretend AI instead of Ollama")
    p.add_argument("--out", default=str(ROOT / "benchmarks" / "results"))
    p.add_argument("--no-db", action="store_true", help="don't add the timings to data/alfiebot.db")
    args = p.parse_args(argv)

    config = load_config()
    machine = machine_label()
    personality = Personality.load()
    questions = load_questions()
    tracker = PerformanceTracker(machine, db=None if args.no_db else Database(config["data_dir"]))
    print(f"Benchmark on {machine}: {len(questions)} questions x {args.repeat}")

    all_rows, summaries, version = [], {}, ""
    for model in (["mock-1"] if args.mock else args.models):
        if args.mock:
            provider = MockProvider("mock-local", "local", model)
        else:
            provider = OllamaProvider(model, args.url)
            provider.refresh(wait=True)
            version = provider.version
            if not provider.available():
                print(f"{model}: skipped. {provider.unavailable_reason}")
                continue
        print(f"{model}:")
        rows, load_s = run_model(provider, questions, personality, args.repeat, args.timeout, args.max_tokens)
        for r in rows:
            tracker.record(r.pop("_result"), source="benchmark", task=r["category"])
        summaries[model] = summarise(rows, load_s)
        all_rows += rows
    if not all_rows:
        print("Nothing was measured. Is Ollama running, with the models installed (ollama list)?")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{dt.datetime.now():%Y%m%d-%H%M}_{re.sub(r'[^A-Za-z0-9]+', '-', machine).strip('-')}"
    with open(out / f"{stem}.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    write_report(out / f"{stem}.md", machine, summaries, all_rows, version)

    print("\nModel            usable  median    90%   tok/s  first load")
    for model, sm in summaries.items():
        med = f"{sm['median_s']:.2f}s" if sm["median_s"] is not None else "-"
        p90 = f"{sm['p90_s']:.2f}s" if sm["p90_s"] is not None else "-"
        tps = f"{sm['tokens_per_s']:.0f}" if sm["tokens_per_s"] else "-"
        print(f"{model:<16} {sm['valid']:>3}/{sm['answers']:<3} {med:>7} {p90:>7} {tps:>6} {sm['load_s']:>8.1f}s")
    print(f"\nSaved {out / (stem + '.md')} and .csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
