"""In-memory fake filesystem. Relevance labels live on the Task."""

from __future__ import annotations

from tombstone.tools import Tool, ToolError, object_schema


class FakeFS:
    def __init__(self, files: dict[str, str]):
        self.files = dict(files)

    def list_dir(self, path: str = "/") -> str:
        prefix = path.rstrip("/") + "/"
        entries = set()
        for f in self.files:
            if f.startswith(prefix):
                rest = f[len(prefix):]
                entries.add(rest.split("/", 1)[0] + ("/" if "/" in rest else ""))
        if not entries:
            raise ToolError(f"no such directory: {path}")
        return "\n".join(sorted(entries))

    def read_file(self, path: str) -> str:
        if path not in self.files:
            raise ToolError(f"no such file: {path}")
        return self.files[path]

    def tools(self) -> list[Tool]:
        return [
            Tool(
                "list_dir",
                "List entries in a directory. Directories end with '/'.",
                object_schema({}, {"path": {"type": "string", "description": "Absolute path; default '/'"}}),
                self.list_dir,
            ),
            Tool(
                "read_file",
                "Read a file's full contents.",
                object_schema({"path": {"type": "string"}}),
                self.read_file,
            ),
        ]
