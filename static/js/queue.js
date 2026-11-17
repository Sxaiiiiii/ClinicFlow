/* Queue page helpers: toggle between "existing patient" and "new walk-in patient" */
document.addEventListener("DOMContentLoaded", () => {
  const select = document.getElementById("walkinPatient");
  const newFields = document.getElementById("walkinNewFields");
  if (!select || !newFields) return;
  const sync = () => {
    const isNew = select.value === "";
    newFields.classList.toggle("d-none", !isNew);
    newFields.querySelectorAll("input,select,textarea").forEach((el) => (el.disabled = !isNew));
    newFields.querySelectorAll("[data-req]").forEach((el) => (el.required = isNew));
  };
  select.addEventListener("change", sync);
  sync();
});
