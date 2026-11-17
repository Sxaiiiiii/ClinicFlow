/* ClinicFlow — shared front-end behaviour (validation, sidebar, small helpers) */
document.addEventListener("DOMContentLoaded", () => {
  // ---- mobile sidebar
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  const toggle = document.getElementById("sidebarToggle");
  if (sidebar && toggle) {
    const set = (open) => { sidebar.classList.toggle("open", open); backdrop && backdrop.classList.toggle("show", open); };
    toggle.addEventListener("click", () => set(!sidebar.classList.contains("open")));
    backdrop && backdrop.addEventListener("click", () => set(false));
  }

  // ---- show / hide password
  document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.querySelector(btn.dataset.togglePassword);
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.innerHTML = show ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
    });
  });

  // ---- password strength meter
  document.querySelectorAll("[data-strength]").forEach((input) => {
    const bar = document.querySelector(input.dataset.strength + " > span");
    if (!bar) return;
    input.addEventListener("input", () => {
      const v = input.value;
      let score = 0;
      if (v.length >= 8) score++;
      if (/[A-Z]/.test(v)) score++;
      if (/[a-z]/.test(v)) score++;
      if (/\d/.test(v)) score++;
      if (/[^A-Za-z0-9]/.test(v) && v.length >= 10) score++;
      bar.style.width = (score / 5) * 100 + "%";
      bar.style.background = score <= 2 ? "#E5484D" : score <= 3 ? "#F5A524" : "#12A150";
    });
  });

  // ---- confirm passwords match + password rule (client-side; the server re-checks everything)
  document.querySelectorAll("[data-match]").forEach((input) => {
    const other = document.querySelector(input.dataset.match);
    const check = () => input.setCustomValidity(input.value && input.value !== other.value ? "Passwords do not match." : "");
    input.addEventListener("input", check);
    other.addEventListener("input", check);
  });
  document.querySelectorAll("input[data-password-rule]").forEach((input) => {
    input.addEventListener("input", () => {
      const v = input.value;
      const ok = v === "" || (v.length >= 8 && /[A-Z]/.test(v) && /[a-z]/.test(v) && /\d/.test(v));
      input.setCustomValidity(ok ? "" : "Use 8+ characters with upper, lower case and a number.");
    });
  });

  // ---- Bootstrap-style validation + stop double submits
  document.querySelectorAll("form.needs-validation").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
        form.classList.add("was-validated");
        const bad = form.querySelector(":invalid");
        bad && bad.focus();
        return;
      }
      form.querySelectorAll("button[type=submit]").forEach((b) => setTimeout(() => (b.disabled = true), 0));
    });
  });

  // ---- "Are you sure?" before logging out
  const logoutModalEl = document.getElementById("logoutModal");
  if (logoutModalEl && window.bootstrap) {
    const logoutModal = bootstrap.Modal.getOrCreateInstance(logoutModalEl);
    let pendingForm = null;
    document.querySelectorAll("form.js-logout").forEach((form) => {
      form.addEventListener("submit", (event) => {
        if (form.dataset.confirmed) return;
        event.preventDefault();
        pendingForm = form;
        logoutModal.show();
      });
    });
    document.getElementById("confirmLogout").addEventListener("click", () => {
      if (!pendingForm) return;
      pendingForm.dataset.confirmed = "1";
      pendingForm.submit();
    });
  }

  // ---- confirmation dialogs (event delegation, so it also works after auto-refresh)
  document.addEventListener("submit", (event) => {
    const msg = event.target.dataset && event.target.dataset.confirm;
    if (msg && !window.confirm(msg)) event.preventDefault();
  });

  // ---- auto-dismiss flash messages
  document.querySelectorAll(".alert-dismissible[data-auto]").forEach((el) =>
    setTimeout(() => bootstrap.Alert.getOrCreateInstance(el).close(), 6000));

  // ---- fill the "edit staff" modal
  document.querySelectorAll(".js-edit-staff").forEach((btn) => {
    btn.addEventListener("click", () => {
      const m = document.getElementById("staffModal");
      const d = btn.dataset;
      m.querySelector(".modal-title").textContent = "Edit staff account";
      m.querySelector("[name=staff_id]").value = d.id;
      m.querySelector("[name=first_name]").value = d.first;
      m.querySelector("[name=last_name]").value = d.last;
      m.querySelector("[name=email]").value = d.email;
      m.querySelector("[name=contact_number]").value = d.contact;
      m.querySelector("[name=specialization]").value = d.spec;
      const role = m.querySelector("[name=role]");
      role.value = d.role; role.disabled = d.role === "admin";
      const pw = m.querySelector("[name=password]");
      pw.required = false; pw.value = "";
      m.querySelector(".pw-hint").textContent = "Leave blank to keep the current password.";
    });
  });
  const newStaff = document.getElementById("newStaffBtn");
  newStaff && newStaff.addEventListener("click", () => {
    const m = document.getElementById("staffModal");
    m.querySelector("form").reset();
    m.querySelector(".modal-title").textContent = "Add staff account";
    m.querySelector("[name=staff_id]").value = "";
    m.querySelector("[name=role]").disabled = false;
    m.querySelector("[name=password]").required = true;
    m.querySelector(".pw-hint").textContent = "Min. 8 characters with upper, lower case and a number.";
  });

  // ---- fill the "reschedule" modal
  document.querySelectorAll(".js-reschedule").forEach((btn) => {
    btn.addEventListener("click", () => {
      const m = document.getElementById("rescheduleModal");
      m.querySelector("form").action = btn.dataset.action;
      const picker = m.querySelector(".slot-picker");
      picker.dataset.exclude = btn.dataset.id;
      picker.dataset.staff = btn.dataset.staff || "";
      m.querySelector("[name=appointment_date]").value = btn.dataset.date;
      m.querySelector("[name=appointment_date]").dispatchEvent(new Event("change"));
    });
  });

  // ---- auto-refresh live areas (queue pages) without losing the user's place
  document.querySelectorAll("[data-autorefresh]").forEach((area) => {
    const seconds = parseInt(area.dataset.autorefresh, 10) || 20;
    setInterval(async () => {
      if (document.hidden || document.querySelector(".modal.show") || area.contains(document.activeElement) && document.activeElement.matches("input,select,textarea")) return;
      try {
        const html = await (await fetch(location.href, { credentials: "same-origin" })).text();
        const fresh = new DOMParser().parseFromString(html, "text/html").getElementById(area.id);
        if (fresh) area.innerHTML = fresh.innerHTML;
      } catch (e) { /* offline: try again next tick */ }
    }, seconds * 1000);
  });
});
