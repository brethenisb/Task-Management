const API = "/api/tasks";
let tasks = [], filter = "all";

const $ = id => document.getElementById(id);
const pad = n => String(n).padStart(2, "0");
const dayOf = d => d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
const store = (k, v) => {
  try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) {}
  return null;
};
const fired = new Set(JSON.parse(store("fired") || "[]"));

async function api(path = "", opts = {}) {
  const options = {
    ...opts,
    headers: {
      ...(opts.headers || {})
    }
  };

  if (opts.body) {
    options.headers["Content-Type"] = "application/json";
  }

  const res = await fetch(API + path, options);

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      body.error ||
      "Server error " + res.status + ". Check the python app.py terminal."
    );
  }

  return res.status === 204 ? null : res.json();
}

function showError(msg) {
  $("error").hidden = !msg;
  $("error").textContent = msg || "";
}

async function load() {
  try { tasks = await api(); showError(""); }
  catch (e) {
    showError(e instanceof TypeError
      ? "Cannot reach the backend. Start it with: python app.py"
      : "Backend is running but returned an error: " + e.message);
  }
  render();
}

function render() {
  const list = $("list");
  list.innerHTML = "";
  const today = dayOf(new Date());
  const shown = tasks.filter(t =>
    filter === "all" || (filter === "done" && t.is_done) ||
    (filter === "pending" && !t.is_done) || (filter === "exam" && t.category === "exam"));

  if (!shown.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = tasks.length ? "Nothing in this view." : "No tasks yet. Add your first one.";
    list.appendChild(li);
  }
  shown.forEach(t => {
    const li = document.createElement("li");
    li.className = t.category + (t.is_done ? " done" : "");
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.checked = t.is_done;
    cb.setAttribute("aria-label", "Mark done: " + t.title);
    cb.onchange = () => toggle(t, cb.checked);

    const body = document.createElement("div"); body.className = "body";
    const title = document.createElement("div"); title.className = "title";
    title.textContent = (t.category === "exam" ? (t.is_done ? "\uD83C\uDFC6 " : "\uD83D\uDCD8 ") : "") + t.title;
    const meta = document.createElement("div"); meta.className = "meta";
    const late = t.due_date && !t.is_done && t.due_date < today;
    if (late) meta.classList.add("late");
    meta.textContent = (t.category === "exam" ? "Exam" : "Task") + " \u00b7 " + t.priority +
      (t.due_date ? " \u00b7 " + (late ? "Overdue " : "Due ") + t.due_date : "") +
      (t.remind_at ? " \u00b7 Remind " + t.remind_at.replace("T", " ").slice(0, 16) : "");
    body.append(title, meta);

    const del = document.createElement("button");
    del.className = "del"; del.textContent = "Delete";
    del.setAttribute("aria-label", "Delete: " + t.title);
    del.onclick = async () => { try { await api("/" + t.id, { method: "DELETE" }); load(); } catch (e) { showError(e.message); } };

    li.append(cb, body, del);
    list.appendChild(li);
  });

  $("nAll").textContent = tasks.length;
  $("nDone").textContent = tasks.filter(t => t.is_done).length;
  $("nActive").textContent = tasks.filter(t => !t.is_done).length;
  updateStatus();
}

// Red = no task added today, green = all of today's tasks done, amber = some pending
function updateStatus() {
  const today = dayOf(new Date());
  const mine = tasks.filter(t => dayOf(new Date(t.created_at)) === today);
  const s = $("status");
  if (!mine.length) {
    s.className = "red"; s.textContent = "You have not added any task today. Add one now!";
  } else if (mine.every(t => t.is_done)) {
    s.className = "green"; s.textContent = "All of today's tasks are completed. Well done!";
  } else {
    const n = mine.filter(t => !t.is_done).length;
    s.className = "amber"; s.textContent = n + " task" + (n > 1 ? "s" : "") + " pending today.";
  }
  document.title = (s.className === "red" ? "(!) " : "") + "Task Manager";
}

async function toggle(t, done) {
  try {
    await api("/" + t.id, { method: "PATCH", body: JSON.stringify({ is_done: done }) });
    if (done && t.category === "exam") celebrate(t.title);
  } catch (e) { showError(e.message); }
  load();
}

// Celebration mode (exam completed)
function celebrate(name) {
  const box = document.createElement("div");
  box.className = "celebrate";
  box.innerHTML = "<div><h2>\uD83C\uDF89 Exam completed!</h2><p></p><p>Great job. Keep going!</p></div>";
  box.querySelector("p").textContent = name;
  box.onclick = () => box.remove();
  document.body.appendChild(box);
  setTimeout(() => box.remove(), 5000);
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const c = $("confetti"), ctx = c.getContext("2d");
  c.width = innerWidth; c.height = innerHeight; c.style.display = "block";
  const colors = ["#2563eb", "#16a34a", "#f59e0b", "#ec4899", "#8b5cf6"];
  const bits = Array.from({ length: 160 }, () => ({
    x: Math.random() * c.width, y: -Math.random() * c.height * .5, w: 5 + Math.random() * 6,
    vx: -2 + Math.random() * 4, vy: 2 + Math.random() * 4, col: colors[Math.floor(Math.random() * colors.length)]
  }));
  let frames = 0;
  (function step() {
    ctx.clearRect(0, 0, c.width, c.height);
    bits.forEach(b => { b.x += b.vx; b.y += b.vy; ctx.fillStyle = b.col; ctx.fillRect(b.x, b.y, b.w, b.w * 1.6); });
    if (++frames < 240) requestAnimationFrame(step); else c.style.display = "none";
  })();
}

// Alerts and reminders
function showAlert(text, kind) {
  const box = document.createElement("div");
  box.className = "alert " + kind;
  const msg = document.createElement("span"); msg.textContent = text;
  const ok = document.createElement("button"); ok.textContent = "Dismiss";
  ok.onclick = () => box.remove();
  box.append(msg, ok);
  $("alerts").appendChild(box);
  try {
    if ("Notification" in window && Notification.permission === "granted") new Notification("Task Manager", { body: text });
  } catch (e) {}
}

function checkReminders() {
  const now = new Date(), today = dayOf(now);
  const minutes = d => d.getHours() * 60 + d.getMinutes();
  tasks.forEach(t => {
    if (!t.remind_at || t.is_done) return;
    const at = new Date(t.remind_at);
    // exam: fires once at the set time; daily task: fires every day at that time of day
    const daily = t.category === "task";
    const key = daily ? t.id + "@" + today : String(t.id);
    const dueNow = daily ? now >= at && minutes(now) >= minutes(at) : now >= at;
    if (!dueNow || fired.has(key)) return;
    fired.add(key);
    store("fired", JSON.stringify([...fired]));
    showAlert((t.category === "exam" ? "Exam reminder: " : "Reminder: ") + t.title, t.category === "exam" ? "exam" : "task");
  });
  // once a day after the chosen time, nudge if nothing was added today
  const [h, m] = ($("nudgeTime").value || "09:00").split(":");
  if (minutes(now) >= +h * 60 + +m && store("nudged") !== today && !tasks.some(t => dayOf(new Date(t.created_at)) === today)) {
    store("nudged", today);
    showAlert("You have not added any task today. Plan your day now.", "nudge");
  }
}

$("form").onsubmit = async e => {
  e.preventDefault();
  try {
    await api("", { method: "POST", body: JSON.stringify({
      title: $("title").value.trim(), category: $("category").value, priority: $("prio").value,
      due_date: $("due").value || null, remind_at: $("remind").value || null
    }) });
    if ($("remind").value && "Notification" in window && Notification.permission === "default") Notification.requestPermission();
    e.target.reset();
    showError("");
    await load();
  } catch (err) { showError(err.message); }
};

document.querySelectorAll(".filters button").forEach(b => b.onclick = () => {
  filter = b.dataset.f;
  document.querySelectorAll(".filters button").forEach(x => x.setAttribute("aria-pressed", x === b));
  render();
});

$("today").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
$("nudgeTime").value = store("nudgeTime") || "09:00";
$("nudgeTime").onchange = () => { store("nudgeTime", $("nudgeTime").value); store("nudged", ""); };
load().then(checkReminders);
setInterval(() => { checkReminders(); updateStatus(); }, 15000);
setInterval(load, 60000);