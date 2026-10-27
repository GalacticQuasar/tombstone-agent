from .base import Task
from .toy import toy_bridge

TASKS: dict[str, Task] = {t.id: t for t in [toy_bridge()]}
