"""Does the backend see a long prompt in full? Put a code at the start, ask for it at the end."""
import sys, random
from dotenv import load_dotenv
from tombstone.client import BACKENDS, OpenAIChatClient
from tombstone.messages import Message
from tombstone.prefix import ApproxTokenizer, HFTokenizer
from evals.tasks.world import NameGen, make_setting, page_text

load_dotenv(".env")
b = BACKENDS[sys.argv[1]]
tok = HFTokenizer(b.tokenizer) if b.tokenizer else ApproxTokenizer()
rng = random.Random(0)
st = make_setting(rng, NameGen(rng))
for target in (int(sys.argv[2]),):
    body = ""
    while tok.count(body) < target:
        body += page_text(rng, st, "Archive notes.", [], n_sentences=60) + "\n\n"
    prompt = f"The access code is ZEPHYR-4417.\n\n{body}\n\nWhat is the access code stated at the very start? Reply with the code only."
    c = OpenAIChatClient(b, temperature=0.0).complete([Message("user", prompt)], [])
    print(f"{b.name}: our count {tok.count(prompt)}, host prompt_tokens {c.usage.prompt}, "
          f"answer {(c.message.content or '').strip()[-40:]!r}")
