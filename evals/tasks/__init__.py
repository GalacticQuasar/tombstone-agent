from .base import Task
from .chain import chain
from .dossier import dossier
from .repo import repo
from .toy import toy_bridge

TASKS: dict[str, Task] = {
    t.id: t
    for t in [
        toy_bridge(),
        dossier(1), dossier(2),
        chain(1), chain(2),
        repo(1), repo(2),
    ]
}
