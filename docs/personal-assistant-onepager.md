# From Chatbot to Personal Assistant

**The Problem:** Out of the box, Claude is smart but isolated—no access to your email, calendar, or files. No memory between sessions. No structured workflows.

**The Solution:** Four architectural layers that extend what's possible.

---

## The Four Layers

### 1. MCPs (Connectors)
Give Claude access to your digital life.

| Connect To | What It Enables |
|------------|-----------------|
| Email | Read, search, draft, send |
| Calendar | View schedule, find free time, create events |
| Files | Access docs, notes, knowledge bases |
| Web | Research anything |
| Tasks | Manage to-dos and projects |

*Without:* "I can't access that, please tell me what's there"
*With:* "You have 3 meetings tomorrow. The 11am conflicts with your gym time."

---

### 2. Skills (Workflows)
Pre-defined routines for how you want things done.

| Skill | What It Does |
|-------|--------------|
| `/morning-briefing` | Weather, calendar, priority emails, headlines |
| `/meeting-prep` | Research attendees, pull docs, suggest talking points |
| `/travel-plan` | Flights, hotels, itinerary, loyalty programs |
| `/weekly-review` | What happened, what's coming, what's pending |

*Without:* Generic improvised responses
*With:* Consistent, thorough execution every time

---

### 3. Agents (Specialists)
Focused workers the assistant delegates to.

| Agent | Specialty |
|-------|-----------|
| Researcher | Deep dives, comparisons, fact-finding |
| Writer | Emails, documents, messages |
| Scheduler | Calendar optimization, conflict resolution |
| Planner | Multi-step project coordination |

*Example:* "Plan an anniversary trip" → Researcher finds destinations, Scheduler checks availability, Planner builds itinerary, Writer drafts the reveal.

---

### 4. Hooks (Autopilot)
Automated triggers for proactive behavior.

| Hook | What It Does |
|------|--------------|
| Session start | Loads today's context automatically |
| Memory recall | Searches past conversations for relevance |
| Session end | Saves state so next session can resume |

*Without:* You drive everything
*With:* "Heads up—you have that client call in 2 hours and Sarah replied about dinner."

---

## The Pattern

```
MCPs provide access → Skills encode expertise → Agents do the work → Hooks wire it together
```

**Start simple:** Connect calendar + email → Add morning briefing skill → Enable memory hooks → Expand from there.

---

*Built on patterns from [Continuous Claude](https://github.com/davidhayes/continuous-claude)*
