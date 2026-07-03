from datetime import date, time

import streamlit as st

from pawpal_system import Owner, Pet, Schedule, Task

PRIORITY_MAP = {"low": 1, "medium": 2, "high": 3}
PRIORITY_LABEL = {1: "low", 2: "medium", 3: "high"}

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")

# Initialize Owner once; persists across reruns.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan")

owner = st.session_state.owner

# --- Owner ---
st.subheader("Owner")
col1, col2, col3 = st.columns(3)
with col1:
    owner.name = st.text_input("Owner name", value=owner.name)
with col2:
    start_h, start_m = divmod(owner.day_start, 60)
    day_start_t = st.time_input("Day starts", value=time(start_h, start_m))
    owner.day_start = day_start_t.hour * 60 + day_start_t.minute
with col3:
    end_h, end_m = divmod(owner.day_end, 60)
    day_end_t = st.time_input("Day ends", value=time(end_h, end_m))
    owner.day_end = day_end_t.hour * 60 + day_end_t.minute

# --- Add a Pet ---
st.subheader("Pets")

with st.form("add_pet_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        pet_name = st.text_input("Pet name", value="Mochi")
    with col2:
        species_options = ["dog", "cat", "other"]
        species = st.selectbox("Species", species_options)
    with col3:
        breed = st.text_input("Breed (optional)")
    if st.form_submit_button("Add pet"):
        owner.add_pet(Pet(name=pet_name, species=species, breed=breed))

if owner.pets:
    st.table([
        {"name": p.name, "species": p.species, "breed": p.breed, "tasks": len(p.tasks)}
        for p in owner.pets
    ])
else:
    st.info("No pets yet. Add one above.")

# --- Add a Task ---
st.subheader("Tasks")

if not owner.pets:
    st.info("Add a pet before adding tasks.")
else:
    pet_names = [p.name for p in owner.pets]

    with st.form("add_task_form"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            selected_pet = st.selectbox("Pet", pet_names)
        with col2:
            task_title = st.text_input("Task title", value="Morning walk")
        with col3:
            duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
        with col4:
            priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

        col5, col6, col7 = st.columns(3)
        with col5:
            category = st.selectbox("Category", ["(none)", "walk", "feeding", "meds", "grooming"])
        with col6:
            recurrence = st.selectbox("Recurrence", ["none", "daily", "weekly"])
        with col7:
            t = st.time_input("Preferred time (optional)", value=None)
            preferred_time = (t.hour * 60 + t.minute) if t else None

        if st.form_submit_button("Add task"):
            pet = owner.pets[pet_names.index(selected_pet)]
            pet.add_task(Task(
                name=task_title,
                duration=int(duration),
                priority=PRIORITY_MAP[priority],
                category=None if category == "(none)" else category,
                recurrence=None if recurrence == "none" else recurrence,
                preferred_time=preferred_time,
            ))

    for pet in owner.pets:
        if pet.tasks:
            st.markdown(f"**{pet.name}'s tasks**")
            for idx, task in enumerate(list(pet.tasks_by_priority())):
                col_name, col_info, col_del = st.columns([3, 4, 1])
                with col_name:
                    st.write(task.name)
                with col_info:
                    st.caption(f"{task.duration} min · {PRIORITY_LABEL.get(task.priority, str(task.priority))} priority · {task.category or 'no category'}")
                with col_del:
                    if st.button("Remove", key=f"remove_{pet.name}_{idx}"):
                        pet.remove_task(task)
                        st.session_state.pop("schedule", None)
                        st.rerun()

st.divider()

# --- Generate Schedule ---
if st.button("Generate schedule"):
    if not owner.all_tasks():
        st.warning("Add at least one task before generating a schedule.")
    else:
        sched = Schedule(owner=owner, date=date.today())
        sched.generate()
        st.session_state.schedule = sched

if "schedule" in st.session_state:
    sched = st.session_state.schedule
    st.subheader("Today's Schedule")

    # Summary metrics
    total_scheduled = sum(task.duration for _, _, task in sched.entries)
    completed_count = sum(1 for _, _, task in sched.entries if task.completed)
    day_window = owner.day_end - owner.day_start
    pct_used = int(total_scheduled / day_window * 100) if day_window > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tasks scheduled", len(sched.entries))
    m2.metric("Completed", f"{completed_count} / {len(sched.entries)}")
    m3.metric("Total time", f"{total_scheduled} min")
    m4.metric("Day used", f"{pct_used}%")

    # Conflict warnings — displayed before the table so they're impossible to miss.
    # Each conflict gets its own st.warning so owners can read one problem at a time.
    conflicts = sched.detect_conflicts()
    if conflicts:
        st.error(f"{len(conflicts)} scheduling conflict{'s' if len(conflicts) > 1 else ''} detected — review before your day starts:")
        for msg in conflicts:
            st.warning(msg.replace("WARNING: Conflict", "Conflict"))
        st.caption("Tip: open the task form and adjust the preferred time for one of the conflicting tasks.")

    # Category filter
    all_cats = sorted({task.category for _, _, task in sched.entries if task.category})
    filter_cat = st.selectbox("Filter by category", ["(all)"] + all_cats) if all_cats else "(all)"

    # Schedule table with checkboxes — replaces static st.table
    COL_WIDTHS = [0.5, 1.5, 2, 3, 1.5, 1.5, 1.5]
    header_cols = st.columns(COL_WIDTHS)
    for col, label in zip(header_cols, ["", "Time", "Pet", "Task", "Duration", "Priority", "Category"]):
        col.markdown(f"**{label}**")

    visible_entries = [
        (s, p, t) for s, p, t in sorted(sched.entries, key=lambda e: e[0])
        if filter_cat == "(all)" or t.category == filter_cat
    ]

    if visible_entries:
        for start, pet, task in visible_entries:
            cols = st.columns(COL_WIDTHS)
            h, m = divmod(start, 60)
            done = cols[0].checkbox(
                "done",
                value=task.completed,
                key=f"done_{pet.name}_{task.name}_{start}",
                label_visibility="collapsed",
            )
            if done and not task.completed:
                task.mark_complete()
                # Regenerate so metrics and strikethroughs update immediately
                new_sched = Schedule(owner=owner, date=date.today())
                new_sched.generate()
                st.session_state.schedule = new_sched
                st.rerun()
            cols[1].write(f"{h:02d}:{m:02d}")
            cols[2].write(pet.name)
            cols[3].markdown(f"~~{task.name}~~" if task.completed else task.name)
            cols[4].write(f"{task.duration} min")
            cols[5].write(PRIORITY_LABEL.get(task.priority, str(task.priority)))
            cols[6].write(task.category or "—")
    elif sched.entries:
        st.info("No tasks match the selected filter.")
    else:
        st.info("No tasks scheduled.")

    # Rescheduled tasks — preferred time existed but the scheduler moved them
    rescheduled_notes = []
    for start, pet, task in sched.entries:
        if task.preferred_time is not None and task.preferred_time != start:
            h_p, m_p = divmod(task.preferred_time, 60)
            h_s, m_s = divmod(start, 60)
            rescheduled_notes.append(
                f"{pet.name}'s '{task.name}' moved from {h_p:02d}:{m_p:02d} → {h_s:02d}:{m_s:02d} "
                f"(preferred time conflicted with another task)"
            )
    if rescheduled_notes:
        with st.expander(f"{len(rescheduled_notes)} task(s) moved from preferred time"):
            for note in rescheduled_notes:
                st.info(note)

    # Dropped tasks — shown as a warning block, not buried in plain text
    if sched.dropped:
        with st.container(border=True):
            st.warning(f"{len(sched.dropped)} task(s) couldn't fit in today's schedule:")
            for task in sched.dropped:
                st.write(f"- {task.summary()}")

    with st.expander("Why this plan?"):
        st.text(sched.explain())
