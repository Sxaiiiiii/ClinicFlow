/* Chat: send messages without reloading and poll for new ones. Text is inserted with textContent (never innerHTML). */
document.addEventListener("DOMContentLoaded", () => {
  // ---- "new message" picker on the conversation list
  const select = document.getElementById("newChatSelect");
  const startBtn = document.getElementById("startChatBtn");
  if (select && startBtn) {
    startBtn.addEventListener("click", () => { if (select.value) location.href = select.dataset.base + select.value; });
  }

  const box = document.getElementById("chatBox");
  if (!box) return;
  const list = document.getElementById("chatMessages");
  const form = document.getElementById("chatForm");
  const input = form.querySelector("textarea");
  const errorBox = document.getElementById("chatError");
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let lastId = parseInt(box.dataset.lastId || "0", 10);
  let lastDate = box.dataset.lastDate || "";

  const scrollDown = () => { list.scrollTop = list.scrollHeight; };
  const showError = (text) => { errorBox.textContent = text; errorBox.classList.toggle("d-none", !text); };

  function addMessage(m) {
    if (m.id <= lastId) return;                       // already on the page
    const empty = document.getElementById("chatEmpty");
    if (empty) empty.remove();
    if (m.date !== lastDate) {
      const sep = document.createElement("div"); sep.className = "chat-date";
      const label = document.createElement("span"); label.textContent = m.date;
      sep.appendChild(label); list.appendChild(sep); lastDate = m.date;
    }
    const row = document.createElement("div"); row.className = "msg " + (m.mine ? "mine" : "theirs"); row.dataset.id = m.id;
    const bubble = document.createElement("div"); bubble.className = "bubble"; bubble.textContent = m.body;
    const meta = document.createElement("div"); meta.className = "meta"; meta.textContent = m.time;
    row.append(bubble, meta); list.appendChild(row);
    lastId = m.id;
  }

  async function poll() {
    if (document.hidden) return;
    try {
      const res = await fetch(box.dataset.pollUrl + "?after=" + lastId, { credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      if (data.messages.length) { data.messages.forEach(addMessage); scrollDown(); }
    } catch (e) { /* offline: try again on the next tick */ }
  }
  setInterval(poll, 4000);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    const button = form.querySelector("button");
    button.disabled = true; showError("");
    try {
      const res = await fetch(form.action, {
        method: "POST", credentials: "same-origin",
        headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch" },
        body: new FormData(form),
      });
      const data = await res.json();
      if (data.ok) { addMessage(data.message); input.value = ""; input.style.height = "auto"; scrollDown(); }
      else showError(data.error || "Could not send the message.");
    } catch (e) { showError("Could not send. Check your connection and try again."); }
    button.disabled = false; input.focus();
  });

  // Enter sends, Shift+Enter makes a new line; the box grows as you type
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 120) + "px"; });
  scrollDown();
});
