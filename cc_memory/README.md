# Slim memory system

This directory replaces the old multi-tree memory setup.

There is one editable truth:

```text
cc_memory/memory.db
```

Everything else is a view or an archive:

```text
cc_memory/mem.py              one command-line entrypoint
cc_memory/exports/MEMORY.md   generated view, safe to delete and rebuild
cc_memory/archive/            old memory trees, inactive archaeology
```

Fresh session:

```bash
python cc_memory/mem.py boot
```

Common operations:

```bash
python cc_memory/mem.py search "phase close"
python cc_memory/mem.py read <id>
python cc_memory/mem.py impact <id>
python cc_memory/mem.py add-event --text "raw source material"
python cc_memory/mem.py set-fact --subject user --predicate preference --value "..."
python cc_memory/mem.py add-entry --title "..." --body "..." --depends-on <fact-id>
python cc_memory/mem.py propose --operation update_fact --touches <id> --reason "..."
python cc_memory/mem.py check
python cc_memory/mem.py export
```

Rules:

- Do not edit `exports/MEMORY.md` by hand.
- Do not restore `cc_context/memory`, `_cc_live_memory`, or `cc_context/memory_graph` as runtime systems.
- If a fact changes, run `impact` before rewriting dependent entries.
- Archive files are evidence and migration history, not a live tree.
