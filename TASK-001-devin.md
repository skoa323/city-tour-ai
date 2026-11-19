# [npc-gate] Deterministic NPC gate + memory service (Genji v1)

## Context

We are building a Shibuya alley city-tour game. NPC dialogue is LLM-driven, but **the decision to refuse is never the model's**: a deterministic gate decides the verdict (`allow` / `refuse` / `eject`) from player input + NPC state; only the *wording* is generated later. `npc_core.py` in this repo is a behavioural reference (single file, rules inline) — do not treat it as the architecture.

Your job: turn it into a small service with persisted state and a real test suite.

## Scope — create only these files

```
services/npc_gate/__init__.py
services/npc_gate/app.py         FastAPI app, port 8100
services/npc_gate/gate.py        pure functions, zero I/O
services/npc_gate/store.py       SQLite persistence, stdlib sqlite3, no ORM
services/npc_gate/schemas.py     pydantic models
services/npc_gate/smoke.py       prints the 5-turn transcript
services/npc_gate/data/genji.yaml
tests/test_gate.py
tests/test_api.py
tests/test_persistence.py
tests/fixtures/smoke.txt
```

**Do not touch:** `npc_core.py`, `genji.json`, `genji.html`, anything under `client/`.

## Rules — exact numbers, do not "improve" them

- respect starts at 32, clamped 0..100
- `photo` (action=="photo" OR text matches `写真|撮|インスタ|自撮り|スマホ|カメラ|photo|pic|insta|camera`) → refuse, rule `photo`, **-12**
- `demolition` (`取り壊|再開発|建て替|買収|立て直`) → refuse, rule `demolition`, **-14**
- `apology` (`すみません|ごめん|申し訳|对不起|抱歉`) → allow, rule `apology`, **+8**
- `praise` (`うまい|美味|いい店|いいね|いいな|いいです|すごい|綺麗|きれい`) → allow, rule `praise`, **+5**
- `offmenu` (`マティーニ|モヒート|カクテル|ワイン|ビール|ウイスキー|焼酎`) → refuse, rule `offmenu`, **-3**
- `loud` streak >= 2 → eject, **-100**, `banned_until = now + 7d`
- `allow` with no rule → **+4 if new_visit**, **+4 more if new_visit and photo_seen == 0**
- **evaluation order:** banned → photo → apology → demolition → loud → offmenu → praise → allow
- band: `<30` cold, `<60` flat, else warm

## API contract

```
POST /v1/turn
  {"npc_id":"genji","session_id":"s1","text":"...","action":null,"new_visit":false}
→ 200
  {"verdict":"refuse","rule":"photo","say_key":"refuse_photo","respect":17,
   "band":"cold","refused":true,"memory_written":["tried_photo"],
   "affordances":["serve","refuse","walk_off"]}

GET  /v1/state/{session_id}   → full state
POST /v1/reset/{session_id}
```

- `say_key` is a **symbol, never a sentence**. Sentences live in `data/genji.yaml` under `lines.<say_key>.<band>`, so localisation never touches code.
- No network calls. No LLM. Deterministic: the same input sequence yields the same output bytes.

## Acceptance — must pass, paste the output into your PR

```
pytest -q                      # all green, >= 12 tests
python -m npc_gate.smoke       # transcript must match tests/fixtures/smoke.txt
# then: restart the process, GET /v1/state/s1
#       -> respect and memories still there (data/state.db)
```

Required test cases:

1. first visit, empty text → `seat_first`, respect 36, band flat
2. photo on turn 3 → refused, respect -12, memory contains `tried_photo`
3. demolition → refused, `say_key=shut_down`
4. apology after a photo → allowed, +8 — and a later photo is **still** refused
5. three visits without any photo → respect >= 68 and `say_key` switches to the warm-band line
6. off-menu order → `state_menu`, -3, never served
7. loud twice → eject, `banned_until` set; next turn → verdict `eject`, rule `banned`, `say_key=silent`
8. clamping: never below 0 or above 100
9. evaluation order: `"取り壊しの写真撮らせて"` → `photo` (-12) wins, not `demolition`
10. two parallel POSTs to the same session do not corrupt respect (single-writer / sqlite lock)
11. unknown `npc_id` → 404
12. band boundaries exactly 29/30 and 59/60

## Out of scope — do not add

LLM calls, TTS, prompt building, auth, docker, kubernetes, extra endpoints, refactors of `npc_core.py`.

## Report back in the PR description

- files added (path list)
- the `pytest` summary line
- the smoke transcript
- **every place where you had to make a judgement call the spec didn't cover, as a numbered list**
