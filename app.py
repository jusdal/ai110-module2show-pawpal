from datetime import date

import streamlit as st

from pawpal_system import Owner, Pet, Schedule, Task

PRIORITY_MAP = {"low": 1, "medium": 2, "high": 3}

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")

# Initialize Owner once; persists across reruns.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan")

owner = st.session_state.owner

# --- Owner ---
st.subheader("Owner")
owner.name = st.text_input("Owner name", value=owner.name)

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
            recurrence = st.selectbox("Recurrence", ["daily", "none"])
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
            st.table([
                {"title": t.name, "duration_minutes": t.duration, "priority": t.priority}
                for t in pet.tasks_by_priority()
            ])

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
    st.code(str(sched), language=None)

    if sched.dropped:
        st.warning("Couldn't fit everything:")
        for task in sched.dropped:
            st.write(f"- {task.summary()}")

    with st.expander("Why this plan?"):
        st.text(sched.explain())
