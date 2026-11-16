# Pattern Algebra for Humans

> How do we get AI agents to work together without stepping on each other's toes?

---

## The Problem: Too Many Cooks

Imagine you run a busy restaurant kitchen. You have five talented chefs, and the dinner rush just started. Orders are piling up.

Here's the thing: if all five chefs try to use the same stove at once, chaos ensues. Food burns. Dishes come out wrong. Customers leave angry.

But if you coordinate them properly? Magic happens. One person preps salads while another grills steaks. The pasta chef doesn't need to wait for the grill - they can work in parallel. And when the steak is done, it gets handed off to the plating station in a smooth relay.

That's the pattern algebra in a nutshell. It's a set of rules for coordinating AI "chefs" (we call them agents) so they work together smoothly instead of fighting over the same resources.

---

## The Three Magic Words

Everything in the pattern algebra boils down to three simple concepts:

### 1. Sequential - "First this, then that"

You know how a recipe works, right?

1. Chop the onions
2. Sauté them until golden
3. Add the tomatoes
4. Simmer for 20 minutes

You can't sauté before chopping. You can't add tomatoes before you have something to add them to. The order matters.

In agent-speak, we write this as:

```
Chop ; Sauté ; Add ; Simmer
```

That semicolon means "then." Finish one thing completely before starting the next.

**Real example:** When you ask an AI to research a topic and then write a report, that's sequential. The writing can't start until the research is done - otherwise, what would it write about?

---

### 2. Parallel - "At the same time"

Now imagine you're hosting a dinner party. You need:
- Appetizers ready by 6:00
- Main course ready by 7:00
- Dessert ready by 8:00

Do you make each course one after another? Of course not. While the roast is in the oven (3 hours of cook time), you're also prepping the appetizers AND making the dessert dough.

These things happen *at the same time* because they don't interfere with each other.

We write this as:

```
Appetizers | MainCourse | Dessert
```

That vertical bar means "at the same time."

**Real example:** When you want three AI agents to each research a different angle of a problem - one looks at technical aspects, one looks at costs, one looks at risks - they can all work simultaneously. They're not waiting for each other.

---

### 3. Choice - "Either this or that"

Sometimes you have to pick. The menu says:

> Served with fries OR salad (pick one)

Not both. One or the other.

We write this as:

```
Fries + Salad
```

That plus sign means "choose one."

**Real example:** An AI assistant might either answer your question directly (if it knows the answer) OR search the web first (if it doesn't). It picks based on the situation.

---

## Personal Space Rules: Who Can Share What?

Here's where it gets interesting. Remember our kitchen?

Not all sharing is created equal:

### Isolated - "My own cutting board"

Each chef has their own station. Their own knives. Their own workspace. Nobody touches anybody else's stuff.

This is great when you need **independent opinions**. Imagine you're a judge at a cooking competition. You don't want the judges conferring before they vote - you want each judge to make their own decision.

**When to use it:** When agents need to work completely independently. Think: voting, independent reviews, unbiased evaluations.

---

### Shared - "We're all using the same pantry"

The spices, the olive oil, the butter - everyone grabs from the same place. This means you need to be careful: if someone takes the last of the oregano, it's gone for everyone.

But sharing is also efficient. You don't need five bottles of olive oil, one per station. One shared bottle works fine if everyone coordinates.

**When to use it:** When agents need to work on the same project files, same database, same information. They can see each other's work and build on it.

---

### Handoff - "I'm done, you're up"

Picture a relay race. Runner 1 sprints, reaches the exchange zone, passes the baton to Runner 2. Clean transfer. Now it's Runner 2's turn.

In a kitchen, this is like the prep cook finishing the vegetables and handing them to the line cook. "Here are your prepped onions. My job is done. Your job starts now."

**When to use it:** When work naturally flows in stages. Research finishes, writing begins. Draft finishes, review begins.

---

## Why Some Combinations Just Don't Work

Not everything can be combined. Here are the safety rules:

### Rule 1: No two chefs on one burner

If Agent A is writing to a file and Agent B tries to write to the same file at the same time, you get garbage. It's like two people trying to type on the same keyboard simultaneously.

**The fix:** Either make them work sequentially (one after the other) or give them separate files.

### Rule 2: Can't plate before you cook

If Agent B depends on Agent A's output, B has to wait for A to finish. No amount of wishing will let you plate an uncooked steak.

**The fix:** Use sequential composition. Make the dependency explicit.

### Rule 3: Infinite loops are bad

Imagine an indecisive chef:
1. Season the dish
2. Taste it
3. "Needs more salt" - go back to step 1
4. Repeat forever...

An agent that never finishes is useless. Every loop needs an exit condition.

**The fix:** Always have a way out. "After 5 attempts, serve whatever you have."

### Rule 4: Judges can't collude

If you want independent opinions (like a jury), the agents MUST be isolated. If they can see each other's answers, they'll influence each other.

**The fix:** Use isolated scope for anything that requires truly independent evaluation.

---

## Real Patterns, Real Kitchens

Let's see how these building blocks combine into actual useful patterns:

### Pipeline: The Assembly Line

Think of a sandwich shop:
1. Person 1: Takes order, grabs bread
2. Person 2: Adds meat and cheese
3. Person 3: Adds veggies and sauce
4. Person 4: Wraps it up

Each person hands off to the next. Linear. Efficient.

```
TakeOrder ; AddProtein ; AddVeggies ; WrapUp
```

**When to use it:** Research -> Write -> Edit -> Publish. Clear stages, clear handoffs.

---

### Swarm: The Prep Team

Five prep cooks. Fifty pounds of vegetables to chop. Everyone grabs a pile and starts chopping.

```
Prep1 | Prep2 | Prep3 | Prep4 | Prep5
```

They're all doing the same type of work, in parallel, on different chunks.

**When to use it:** When you have a big task that can be split into independent pieces. Search different databases. Analyze different sections of a document.

---

### Jury: The Critics' Table

Three food critics. Each tastes the dish independently. No discussing. Then they vote.

```
(Critic1 | Critic2 | Critic3) ; TallyVotes
```

First, everyone forms their opinion in parallel. Then, we count the votes (sequential - can't count until everyone has voted).

**When to use it:** When you need consensus on important decisions. Multiple reviewers, independent assessments, then aggregate.

---

### Generator-Critic: The Revision Loop

A chef proposes a dish. The head chef tastes it.

- "Needs more salt." (Try again)
- "Too spicy." (Try again)
- "Perfect!" (Done)

```
Propose ; Review ; (Accept OR TryAgain)
```

Keep looping until it's approved.

**When to use it:** Drafting and revision. Code review cycles. Any iterative improvement process.

---

### Circuit Breaker: The Backup Plan

Your special ingredient supplier calls: "Sorry, we're out of truffles."

Plan A failed. Time for Plan B: mushrooms instead.

```
TryTruffles + FallbackToMushrooms
```

If the first option fails, switch to the alternative.

**When to use it:** When you need reliability. If the main approach times out or fails, have a fallback ready.

---

## The Cheat Sheet

Keep these simple rules in mind:

| Pattern | When to Use | Key Rule |
|---------|-------------|----------|
| **Pipeline** | Clear stages | Each stage hands off to the next |
| **Swarm** | Parallel work on chunks | Give each agent their own piece |
| **Jury** | Independent voting | Keep agents isolated |
| **Generator-Critic** | Iterative improvement | Have a clear "done" condition |
| **Circuit Breaker** | Need reliability | Always have a fallback |

And for scopes:

| Scope | Sharing | Use When |
|-------|---------|----------|
| **Isolated** | Nothing | Agents must not influence each other |
| **Shared** | Everything | Agents collaborate on same resources |
| **Handoff** | At boundaries only | Work flows in stages |

---

## Why Do We Need Math for This?

You might wonder: why formalize all this? Why not just "let the agents figure it out"?

Because chaos happens without rules.

The math prevents:

**Deadlocks:** "I'm waiting for you." "No, I'm waiting for you." Both wait forever.

**Resource exhaustion:** "Spawn 1000 agents!" Computer melts.

**Invalid combinations:** "Run these in parallel!" But they're writing to the same file. Corruption.

**Infinite loops:** Agent never finishes. Nothing gets done.

The formal rules are like health codes for a kitchen. They prevent food poisoning. They keep things running smoothly. You don't think about them while cooking, but they're why the kitchen works at all.

---

## Quick Summary

1. **Sequential (;)** = First this, then that
2. **Parallel (|)** = At the same time
3. **Choice (+)** = Pick one

For sharing:
- **Isolated** = Each agent gets their own workspace
- **Shared** = Everyone uses the same stuff (carefully!)
- **Handoff** = Pass the baton between stages

Patterns are just combinations of these basics:
- Pipeline = Sequential handoffs
- Swarm = Parallel on chunks
- Jury = Parallel voting, then aggregate
- Generator-Critic = Loop until approved
- Circuit Breaker = Try A, else B

And the safety rules exist to prevent:
- Two agents fighting over one resource
- Infinite loops
- Agents influencing each other when they shouldn't
- Waiting forever for something that'll never come

---

## Going Deeper

Hungry for the full formal treatment?

- `/docs/pattern-algebra.md` - The complete mathematical specification
- `/docs/pattern-algebra-validation.md` - How we verified the math

But honestly? You don't need the math to use this effectively. The kitchen analogy covers 90% of what you need to know.

Just remember: chefs need coordination. So do AI agents. The pattern algebra is just a fancy way of writing down what good kitchen managers have known for centuries.

---

*Now go orchestrate some agents. And maybe order some takeout while they work.*
