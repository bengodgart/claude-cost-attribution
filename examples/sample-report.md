# Claude Code cost attribution

**Root:** `fixtures/claude_projects/-P-demo-tutor`  
**Pricing:** `pricing.json (repo root)`  
**Sessions parsed:** 1 &middot; **Subagent runs:** 2

**TOTAL cost, cache-aware:** $0.8528  
**TOTAL cost, naive (no cache accounting):** $0.8823 (+3% vs cache-aware)

## Cost by project

| Cost | Share | Project | Turns |
|---|---|---|---|
| $0.8528 | 100% | C:\Users\demo\dev\demo-tutor-app | 8 |

## Cost by skill

_Heuristic span: active from the turn after a Skill call to the next one._

| Cost | Share | Skill |
|---|---|---|
| $0.5910 | 69% | generate-guide |
| $0.2390 | 28% | (no skill) |
| $0.0228 | 3% | pretty-guide |

Reconciles to total: **yes**

## Cost by subagent

_`agentType` from `.meta.json` - a hard signal, not a heuristic._

| Cost | Share | Subagent |
|---|---|---|
| $0.6612 | 78% | (main session, no subagent) |
| $0.1875 | 22% | executor |
| $0.0041 | 0% | general-purpose |

Reconciles to total: **yes**

## Burn-rate gauge

- Trailing 7-day window: `2026-05-30 14:05:00+00:00` to `2026-06-06 14:05:00+00:00`
- Spend in window: $0.8528
- Daily rate: $0.1636/day (over 5.21 elapsed days)
- Weekly cap: $5.0000 (user-supplied) - 17% used
- At the current daily rate: cap reached in 30.6 days
