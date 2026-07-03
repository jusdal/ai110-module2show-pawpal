# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

My initial UML centered on four classes:

- **Owner** — the person using the app. Holds basic info, preferences, and the time available in a day. Owns one or more `Pet`s.
- **Pet** — basic identity (name, species, breed, age) plus the list of care `Task`s that belong to it. Responsible for managing its own tasks (`add_task()` / `remove_task()`).
- **Task** — a single care activity with a `duration` and a `priority`. This was the data the scheduler would sort and filter on.
- **Schedule** — the planner and the output. Given an owner's tasks and time budget, `generate()` would sort tasks by priority, drop the ones that didn't fit the available time, and produce an ordered daily plan it could also explain.

The core relationships were Owner → many Pets → many Tasks, with Schedule consuming the tasks to produce a daily plan. My first version was deliberately simple: a single time budget (total minutes), tasks ordered purely by priority and duration, and no notion of specific times of day — so conflicts couldn't happen yet. I kept `Task`, `Pet`, and `Owner` as dataclasses to cut boilerplate and concentrated the real logic in `Schedule`.

**b. Design changes**

Yes — the design evolved in two significant ways as I thought through real usage.

1. **Single time budget → a full timeline.** I originally gave the owner a single "available minutes" number. Once I decided tasks could have a `preferred_time` (e.g. a morning walk at 08:00), a flat budget wasn't enough — I needed to know *when* the day starts and ends. So `Owner` gained `day_start` and `day_end`, and I standardized on storing all times as minutes-since-midnight (ints) to keep the slot arithmetic simple.

2. **No conflicts → honor preferred times and bump on clash.** Supporting multiple pets for one owner meant tasks from different pets compete for the same day and could want the same time slot. I extended `Schedule.generate()` into phases: place tasks with preferred times first (resolving clashes by priority via `_resolve_clash()`), then fill the remaining gaps with the untimed tasks. To make this honest for the user, I added a `dropped` list so the plan can show what *didn't* fit and why, rather than silently discarding tasks. I also added a `pet` back-reference on `Task` so a task can still be identified after being pooled across all of the owner's pets.

A review of the skeleton (before writing any logic) surfaced several refinements I folded in while the changes were still cheap:

- **Made `generate()` idempotent.** It now clears `entries` and `dropped` at the start, so the repeated calls a Streamlit app makes on every rerun rebuild the plan instead of accumulating duplicate entries.
- **Extracted a shared `_first_free_gap()` helper.** Both anchored placement (for bumped tasks) and gap-filling need the same "where does a task of this duration fit without overlapping?" interval math, so I centralized it in one method rather than duplicating it.
- **Changed `_resolve_clash()` to return `(winner, loser)`** instead of just the winner. The earlier signature threw away the bumped task, but the loser needs to flow back into the gap-fill pool, so the caller now receives both.
- **Pinned a deterministic tie-break** in `_sort_tasks()`: priority (desc), then duration (asc), then insertion order. Without a fully specified order, identical inputs could produce different plans and make tests flaky.
- **Tightened the `Task`/`Pet` back-reference contract** so `add_task()` is the only thing that sets `task.pet` and `remove_task()` clears it, preventing dangling references.
- **Scoped recurrence to "daily" for now**, since "weekly" needs an anchor date that the model doesn't yet carry — documented as a deliberate limitation rather than a half-working feature.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers three main constraints:

1. **Time window** — the owner's `day_start` and `day_end` bound the available day. Tasks that can't fit within that window are dropped rather than placed outside it.
2. **Priority** — higher-priority tasks are placed first. When two tasks want the same time slot, the higher-priority one wins and the loser is re-queued for gap-fill.
3. **Preferred time** — tasks with a `preferred_time` are anchored to that slot when possible. This respects real-world constraints like medication schedules or feeding routines that can't simply be moved to "whenever."

Priority matters most because it's the main lever the user has to express what's non-negotiable. Preferred time comes second — it's a strong preference but can be bumped. Time window is the hard outer bound: there's no point scheduling tasks the owner genuinely can't reach.

**b. Tradeoffs**

`Schedule.generate()` uses a **greedy, priority-first placement strategy**: tasks are sorted once by priority (descending), and each task is placed at the earliest valid time slot — its `preferred_time` if that slot is free, otherwise the first gap that fits. Once a task is placed, that decision is never revisited.

This means the scheduler can miss more globally efficient arrangements. For example: a high-priority 60-minute vet visit placed at 08:00 blocks two lower-priority 30-minute tasks that together have a smaller footprint and could have fit if the vet visit had been shifted to 09:00. A look-ahead or backtracking approach could find a better packing, but at the cost of significantly more complex code.

This tradeoff is reasonable for a daily pet care planner for three reasons. First, the input scale is tiny — a typical owner has fewer than 20 tasks per day — so the difference between greedy and optimal is rarely observable in practice. Second, pet care tasks are not freely interchangeable: feeding a pet at 08:30 instead of 10:00 is a real preference, not an optimization variable, and the `preferred_time` field already captures that directly. Third, a greedy algorithm is transparent: users can predict what will happen (highest priority wins) and trust the plan rather than wondering why the scheduler moved a high-priority task to make room for lower-priority ones.

---

## 3. AI Collaboration

**a. How you used AI**

I used Claude Code as a collaborative pair throughout the project. The main uses were:

- **Design review before coding.** After writing the class skeleton from my UML, I asked the AI to review it for design issues before adding any logic. That review surfaced several concrete refinements — making `generate()` idempotent, extracting `_first_free_gap()` as a shared helper, and changing `_resolve_clash()` to return both winner and loser — all while the code was still cheap to change.
- **Implementing scheduling logic.** Once the skeleton was hardened, I worked with the AI to implement each method in `Schedule`: `_place_anchored()`, `_fill_gaps()`, `explain()`, and `detect_conflicts()`. Having the design clear up front meant those implementations came out clean on the first pass.
- **Adding tests.** I asked the AI to help identify edge cases I hadn't thought of — things like the back-reference healing in `_collect_tasks()`, unknown recurrence strings, and the `filter_tasks()` combined-filter cases.
- **Building the Streamlit UI.** I used the AI to wire the `Owner` / `Pet` / `Schedule` domain model into session state and build the schedule display, conflict warnings, and task management forms.

The most useful prompts were specific and structural: "review this skeleton and list design issues before I add logic," rather than open-ended requests. Asking the AI to explain its reasoning also helped me evaluate suggestions rather than just accept them.

**b. Judgment and verification**

When implementing `_fill_gaps()`, the AI suggested an approach that would leave natural buffer time between tasks — rather than packing each task into the very first available slot, it proposed spacing them with small gaps to give the day a more realistic feel for a pet care schedule. The idea made sense from a UX perspective, but implementing it correctly would have required tracking a separate "preferred gap size," threading that through `_first_free_gap()`, and deciding what to do when gaps weren't available. That's a significant change to the core placement logic, and the additional complexity wasn't justified for this version. I kept the simpler greedy packing and noted buffer time as a future improvement instead.

I verified the AI's implementations by reading through the logic manually and then running the test suite. For the scheduling methods specifically, I traced through a concrete two-pet, three-task example by hand before trusting the output.

---

## 4. Testing and Verification

**a. What you tested**

The test suite covers several behavioral categories:

- **Task lifecycle** — `mark_complete()` sets the flag, spawns a next occurrence for daily/weekly tasks, returns `None` for non-recurring tasks and for tasks without a pet reference, and falls back to `date.today()` when `due_date` is unset.
- **`is_due_today()`** — the due_date field gates inclusion correctly; a task due tomorrow is excluded.
- **Sorting** — `sort_by_time()` returns entries in chronological order regardless of insertion order.
- **Conflict detection** — overlapping intervals produce a warning; back-to-back tasks (end == start) do not; an empty schedule returns no warnings.
- **`explain()` content** — the rationale text mentions priority and duration, counts anchored vs. unanchored tasks correctly, names bumped tasks with their original requested times, names dropped tasks, and says "All tasks fit" when nothing is dropped.
- **Owner day window** — defaults are 07:00–21:00; unanchored tasks start at `day_start`; tasks that don't fit the window are dropped.
- **`filter_tasks()`** — filters by pet name, by completed status, and by both combined; non-matching filters return empty lists.
- **Back-reference healing** — a task appended to `pet.tasks` without `add_task()` has its `pet` reference restored during `generate()` rather than raising.
- **`remove_task()`** — removes the task from the list and clears `task.pet`.

These tests matter because the scheduling logic has several interacting phases (anchor → clash resolution → gap fill → drop), and a bug in any one phase can silently corrupt the plan rather than raising an exception. The tests pin each phase's output so regressions are caught immediately.

**b. Confidence**

I'm confident the core happy path and the most common edge cases work correctly — the test suite is specific enough that a regression in placement or conflict detection would fail a named test. The area I'm least confident about is cascading clash resolution: if multiple anchored tasks clash with each other in sequence, the order in which they're bumped and re-queued could affect the final plan in ways that aren't fully covered by the existing tests. If I had more time I would test:

- Three or more tasks all requesting the same preferred time, checking that priority order is respected through the chain.
- A task whose `preferred_time` is valid but whose duration pushes it past `day_end`, to confirm it's bumped rather than placed partially out of bounds.
- The interaction between a recurring task completing on the last slot of the day and the next occurrence being added while `generate()` is mid-run.

---

## 5. Reflection

**a. What went well**

I'm most satisfied with the `Schedule` class design. The three-phase approach — place anchored tasks first, resolve clashes by priority, then fill remaining gaps with untimed and bumped tasks — turned out to be both readable and correct. Each phase has a single responsibility, the methods are short, and the flow through `generate()` is easy to follow. The decision to do a design review on the skeleton before writing any logic was the reason that came out cleanly: fixing the `_resolve_clash()` return type and extracting `_first_free_gap()` would have been much messier mid-implementation.

**b. What you would improve**

Two things stand out:

1. **Weekly recurrence with an anchor date.** Right now a task with `recurrence="weekly"` but no `due_date` shows up every day because `is_due_today()` falls back to treating it like a daily task. Fixing this properly requires the model to carry an anchor date so the scheduler can compute whether this is the right day of the week. I documented it as a deliberate limitation rather than shipping a half-working feature, but it's the most obviously missing piece.

2. **Gap spacing between tasks.** The current scheduler packs tasks back-to-back with no breathing room. In practice a pet walk followed immediately by a medication task with no transition time isn't realistic. Adding a configurable buffer between tasks would make the plan more useful, though it adds complexity to the gap-finding logic.

**c. Key takeaway**

The most valuable thing I learned is that AI collaboration works best when you treat it as a design partner on structure, not just a code generator. Asking the AI to review the skeleton for design issues before writing any logic produced changes that would have been expensive to retrofit later. But it only works if you push back on suggestions that add complexity without proportional benefit — keeping the design simple is still your job, not the AI's.
