# Claude Code cost attribution

**Root:** `fixtures/claude_projects/-P-demo-tutor`  
**Pricing:** `pricing.json (repo root)`  
**Sessions parsed:** 1 &middot; **Subagent runs:** 2

**TOTAL cost, cache-aware:** $0.3438  
**TOTAL cost, naive (no cache accounting):** $0.3785 (+10% vs cache-aware)

## Cost by project

| Cost | Share | Project | Turns |
|---|---|---|---|
| $0.3438 | 100% | C:\Users\demo\dev\demo-tutor-app | 8 |

## Cost by skill

_Heuristic span: active from the turn after a Skill call to the next one._

| Cost | Share | Skill |
|---|---|---|
| $0.2060 | 60% | generate-guide |
| $0.1150 | 33% | (no skill) |
| $0.0228 | 7% | pretty-guide |

Reconciles to total: **yes**

## Cost by subagent

_`agentType` from `.meta.json` - a hard signal, not a heuristic._

| Cost | Share | Subagent |
|---|---|---|
| $0.2762 | 80% | (main session, no subagent) |
| $0.0625 | 18% | executor |
| $0.0051 | 1% | general-purpose |

Reconciles to total: **yes**

## Burn-rate gauge

- Trailing 7-day window: `2026-05-30 14:05:00+00:00` to `2026-06-06 14:05:00+00:00`
- Spend in window: $0.3438
- Daily rate: $0.0660/day (over 5.21 elapsed days)
- Weekly cap: $5.0000 (user-supplied) - 7% used
- At the current daily rate: cap reached in 75.8 days
