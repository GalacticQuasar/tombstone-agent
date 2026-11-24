import sys, random, dataclasses
from dotenv import load_dotenv
from tombstone.client import BACKENDS, OpenAIChatClient
from tombstone.messages import Message
from tombstone.prefix import ApproxTokenizer
from evals.tasks.world import NameGen, make_setting, page_text
load_dotenv(".env")
rng = random.Random(0); st = make_setting(rng, NameGen(rng))
body = "\n\n".join(page_text(rng, st, "Archive notes.", [], n_sentences=60) for _ in range(20))
prompt = f"The access code is ZEPHYR-4417.\n\n{body}\n\nWhat is the access code stated at the very start? Reply with the code only."
print("approx tokens", ApproxTokenizer().count(prompt))
for model in sys.argv[1:]:
    b = dataclasses.replace(BACKENDS["purdue-qwen3-8b"], name=f"probe-{model}", model=model, rate_group="purdue")
    try:
        c = OpenAIChatClient(b, temperature=0.0).complete([Message("user", prompt)], [])
        print(f"{model:32} prompt_tokens {c.usage.prompt:>6}  {(c.message.content or '').strip()[-30:]!r}")
    except Exception as e:
        print(f"{model:32} error {str(e)[:120]}")
