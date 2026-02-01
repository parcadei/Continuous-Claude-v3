# Building a Multi-Faceted Personal Assistant with Claude

This document explains the key architectural components that transform Claude from a basic chatbot into a capable personal assistant.

---

## The Problem

Out of the box, Claude is smart but limited:
- No access to your email, calendar, or files
- No memory of previous conversations
- No defined workflows for complex tasks
- Can't coordinate multiple activities in parallel

**The solution:** Four architectural layers that extend Claude's capabilities.

---

## 1. MCPs (Model Context Protocol Servers)

**What:** Connectors that give Claude secure access to external services and data.

**Think of it as:** Giving your assistant keys to different rooms in your digital life.

### Personal Assistant Examples

| MCP Server | What It Enables |
|------------|-----------------|
| **Gmail/Outlook** | Read, search, draft, and send emails |
| **Google Calendar** | View schedule, create events, find free time |
| **Google Drive/Dropbox** | Access and organize your documents |
| **Notion/Obsidian** | Read and update your notes and knowledge base |
| **Todoist/Things** | Manage tasks and projects |
| **Weather API** | Context-aware suggestions ("bring an umbrella") |
| **News/RSS** | Curated information feeds |
| **Browser** | Research anything on the web |
| **Finance (Plaid)** | View transactions, track spending patterns |

### Why It Matters

Without MCPs:
> "Can you check my calendar for tomorrow?"
> "I don't have access to your calendar. Please tell me what's on it."

With MCPs:
> "Can you check my calendar for tomorrow?"
> "You have 3 meetings: 9am standup, 11am client call with Acme Corp, and 2pm dentist appointment. The client call conflicts with your usual gym time."

---

## 2. Skills

**What:** Pre-defined workflows that encode expertise for specific tasks. Activated by triggers or commands.

**Think of it as:** Training your assistant on exactly how you want things done.

### Personal Assistant Examples

| Skill | Trigger | What It Does |
|-------|---------|--------------|
| `/morning-briefing` | Session start or "good morning" | Weather, today's calendar, priority emails, news headlines |
| `/email-triage` | "Check my email" | Categorize by urgency, summarize threads, draft quick replies |
| `/meeting-prep` | 30 min before meetings | Research attendees on LinkedIn, pull relevant docs, create agenda |
| `/travel-plan` | "Plan a trip to..." | Research flights, hotels, activities; create itinerary; check loyalty programs |
| `/research` | "Research X for me" | Deep web search, compile findings, cite sources, create summary |
| `/weekly-review` | Sunday evening | Summarize completed tasks, upcoming commitments, pending items |
| `/expense-report` | "Process my receipts" | Extract data from receipts, categorize, format for submission |
| `/gift-finder` | "Find a gift for..." | Consider relationship, interests, budget; suggest options with purchase links |

### Why It Matters

Without skills (improvised):
> "Help me prepare for my meeting with John Smith"
> "Sure! What would you like to know about the meeting?"

With `/meeting-prep` skill (structured):
> "Help me prepare for my meeting with John Smith"
> "Preparing briefing for your 2pm with John Smith (Acme Corp CTO):
> - **Background:** 15 years at Acme, previously at Google, MIT CS degree
> - **Recent news:** Acme just announced Series C funding
> - **Your history:** 3 previous meetings, last discussed API integration
> - **Relevant docs:** Found proposal draft from last month
> - **Suggested talking points:** [...]"

---

## 3. Agents (Specialized Workers)

**What:** Focused assistants that handle specific domains. The main assistant delegates to them and synthesizes results.

**Think of it as:** A team of specialists your assistant can call on.

### Personal Assistant Examples

| Agent | Specialty | When Summoned |
|-------|-----------|---------------|
| **Researcher** | Deep dives, fact-finding, comparisons | "Find the best electric SUV under $60k" |
| **Writer** | Drafting emails, documents, messages | "Write a thank-you note to..." |
| **Scheduler** | Calendar optimization, conflict resolution | "Find time for a 2-hour focus block this week" |
| **Analyst** | Data patterns, trends, insights | "How's my spending this month vs last?" |
| **Planner** | Multi-step project coordination | "Plan my daughter's birthday party" |
| **Curator** | Filtering, organizing, summarizing | "What's worth reading from my saved articles?" |

### Why It Matters

Complex requests get broken down:

> "Plan a surprise anniversary trip for my wife"

Main assistant coordinates:
1. **Researcher** → Find destinations matching her interests (beaches, she mentioned wanting to visit Portugal)
2. **Scheduler** → Identify your mutual free time, check her calendar for conflicts
3. **Analyst** → Review budget based on recent spending
4. **Planner** → Create detailed itinerary with reservations
5. **Writer** → Draft the "reveal" message

Each agent works in parallel, reports back, main assistant synthesizes into a coherent plan.

---

## 4. Hooks

**What:** Automated triggers that fire at specific moments. Enable proactive behavior and context persistence.

**Think of it as:** The assistant's autopilot systems.

### Personal Assistant Examples

| Hook | When It Fires | What It Does |
|------|---------------|--------------|
| **Morning Context** | Session start | Loads today's calendar, weather, priority items |
| **Memory Recall** | Every conversation | Searches past sessions for relevant context |
| **Calendar Awareness** | Approaching meeting | Proactively offers prep, travel time alerts |
| **Email Priority** | New session | Flags anything urgent since last check |
| **Habit Tracker** | Daily check-in | Notes streaks, reminds of commitments |
| **Handoff Saver** | Session end | Saves state so next session can resume |
| **Follow-up Detector** | Reviewing tasks | Identifies promises made that need action |

### Why It Matters

Without hooks (reactive):
> You have to remember to ask about everything

With hooks (proactive):
> "Good morning! Quick heads up:
> - You have that important client call in 2 hours
> - Sarah replied to your email about dinner plans
> - Your flight to Chicago tomorrow is still on time
> - Reminder: You wanted to follow up with Mike about the proposal"

---

## How They Work Together

**Example: "Help me plan next week"**

```
┌─────────────────────────────────────────────────────────┐
│  HOOKS fire on session start                            │
│  → Load calendar, pending tasks, recent context         │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  SKILL: /weekly-planning activated                      │
│  → Structured workflow for week planning                │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  MCPs provide data                                      │
│  → Calendar: meetings and commitments                   │
│  → Tasks: pending items and deadlines                   │
│  → Email: threads needing response                      │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  AGENTS work in parallel                                │
│  → Scheduler: Optimize meeting placement                │
│  → Analyst: Flag overcommitment risks                   │
│  → Planner: Suggest focus time blocks                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Main Assistant synthesizes                             │
│  → "Here's your week at a glance..."                    │
│  → "I noticed you're double-booked Thursday..."         │
│  → "Suggested changes: [...]"                           │
└─────────────────────────────────────────────────────────┘
```

---

## The Transformation

| Without Architecture | With Architecture |
|---------------------|-------------------|
| "I can't access that" | Connected to your services |
| Forgets everything between sessions | Remembers context and preferences |
| Generic responses | Follows your defined workflows |
| One thing at a time | Coordinates parallel activities |
| You drive everything | Proactively surfaces what matters |

---

## Getting Started

**Phase 1: MCPs** - Connect the services you use most (calendar, email, notes)

**Phase 2: Skills** - Define 3-5 workflows you do repeatedly (morning routine, meeting prep, research)

**Phase 3: Hooks** - Add context loading and memory so it feels continuous

**Phase 4: Agents** - Specialize workers for your common complex tasks

Each layer builds on the previous. Start simple, expand as you find friction.

---

*This architecture is what we've built in the [Continuous Claude](https://github.com/davidhayes/continuous-claude) project for coding workflows. The same patterns apply to any domain.*
