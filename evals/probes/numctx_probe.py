import sys, random, dataclasses
from dotenv import load_dotenv
from tombstone.client import BACKENDS, OpenAIChatClient
from tombstone.messages import Message
from evals.tasks.world import NameGen, make_setting, page_text
load_dotenv(".env")
rng = random.Random(0); st = make_setting(rng, NameGen(rng))
body = "\n\n".join(page_text(rng, st, "Archive notes.", [], n_sentences=60) for _ in range(12))
prompt = f"The access code is ZEPHYR-4417.\n\n{body}\n\nWhat is the access code stated at the very start? Reply with the code only."
for extra in ({"options": {"num_ctx": 65536}}, {"num_ctx": 65536}, {"max_context_length": 65536}):
    b = dataclasses.replace(BACKENDS["purdue-llama3.3-70b"], extra_body=extra)
    try:
        c = OpenAIChatClient(b, temperature=0.0).complete([Message("user", prompt)], [])
        print(extra, "prompt_tokens", c.usage.prompt, repr((c.message.content or "").strip()[-30:]))
    except Exception as e:
        print(extra, "error", str(e)[:150])
