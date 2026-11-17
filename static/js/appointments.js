/* Load available time slots for the chosen date (and doctor) from the server. */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".slot-picker").forEach((picker) => {
    const date = picker.querySelector("[name=appointment_date]");
    const time = picker.querySelector("[name=appointment_time]");
    const staff = picker.querySelector("[name=staff_id]");
    const hint = picker.querySelector(".slot-hint");
    const wanted = time.dataset.selected || "";

    async function load() {
      time.innerHTML = '<option value="">Select a time…</option>';
      if (!date.value) { hint.textContent = "Pick a date to see available times."; return; }
      const qs = new URLSearchParams({ date: date.value });
      const staffId = staff ? staff.value : picker.dataset.staff;
      if (staffId) qs.set("staff_id", staffId);
      if (picker.dataset.exclude) qs.set("exclude", picker.dataset.exclude);
      try {
        const data = await (await fetch("/appointments/slots?" + qs, { credentials: "same-origin" })).json();
        if (data.closed) { hint.textContent = data.message; return; }
        let free = 0;
        data.slots.forEach((s) => {
          const opt = new Option(s.label + (s.available ? "" : " (taken)"), s.value);
          opt.disabled = !s.available;
          if (s.available) free++;
          if (s.value === wanted && s.available) opt.selected = true;
          time.add(opt);
        });
        hint.textContent = free ? free + " time slot(s) available." : "No free slots on this day.";
      } catch (e) { hint.textContent = "Could not load time slots. Please refresh."; }
    }
    date.addEventListener("change", load);
    staff && staff.addEventListener("change", load);
    if (date.value) load();
  });
});
