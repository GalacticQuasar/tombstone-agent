Agent that has the power to "forget" or "disregard"

Idea: context should be structured in "blocks" that can be referenced by the agent (for deletion/compression)

Extension: save context into archive files to fetch it later ("forgotten" context)
- `retrieve_context` tool to point to a replaced block and recover its context

Concern: how to reduce KV cache misses? Unavoidable when changing early context...

Examples:
- fetched website that is not relevant -> "forget" it
- moved onto next task that does not need previous task's context files -> "forget" it
