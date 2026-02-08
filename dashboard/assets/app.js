const toggle = document.querySelector("[data-theme-toggle]");
const body = document.body;

const counters = document.querySelectorAll("[data-count]");
const runProgress = document.querySelector("[data-progress]");
const targetsList = document.querySelector("[data-targets-list]");
const reportList = document.querySelector("[data-report-list]");
const targetForm = document.querySelector("[data-target-form]");

const storageKey = "price-filter-targets";

const animateValue = (element) => {
  const target = Number(element.dataset.count);
  let value = 0;
  const step = Math.max(1, Math.floor(target / 60));

  const tick = () => {
    value = Math.min(target, value + step);
    element.textContent = value.toLocaleString("es-MX");
    if (value < target) {
      requestAnimationFrame(tick);
    }
  };
  tick();
};

const loadTargets = () => {
  try {
    return JSON.parse(localStorage.getItem(storageKey)) ?? [];
  } catch (error) {
    console.warn("No se pudo cargar targets", error);
    return [];
  }
};

const saveTargets = (targets) => {
  localStorage.setItem(storageKey, JSON.stringify(targets));
};

const renderTargets = (targets) => {
  if (!targetsList) return;
  targetsList.innerHTML = "";

  targets.forEach((target, index) => {
    const row = document.createElement("div");
    row.className = "target";
    row.innerHTML = `
      <div class="target__meta">
        <p class="label">${target.name}</p>
        <p class="value">${target.location || "Sin ubicación"} · ${target.category || "Sin categoría"}</p>
        <p class="muted">${target.url}</p>
      </div>
      <div class="target__actions">
        <button class="btn btn--ghost btn--small" data-remove-target="${index}">Quitar</button>
      </div>
    `;
    targetsList.appendChild(row);
  });

  if (targets.length === 0) {
    targetsList.innerHTML = "<p class=\"muted\">Sin targets aún. Agrega uno desde el formulario.</p>";
  }
};

const renderReport = (targets) => {
  if (!reportList) return;
  reportList.innerHTML = "";

  targets.forEach((target) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <span class="report__title">${target.name}</span>
      <span class="muted">${target.url}</span>
      <span class="value">${target.category || "Categoría pendiente"} · ${target.location || "Ubicación pendiente"}</span>
    `;
    reportList.appendChild(item);
  });

  if (targets.length === 0) {
    reportList.innerHTML = "<li><span class=\"muted\">Sin datos aún. Los reportes aparecerán cuando agregues targets.</span></li>";
  }
};

const syncUI = (targets) => {
  renderTargets(targets);
  renderReport(targets);
};

const addTarget = (target) => {
  const targets = loadTargets();
  targets.push(target);
  saveTargets(targets);
  syncUI(targets);
};

const removeTarget = (index) => {
  const targets = loadTargets();
  targets.splice(index, 1);
  saveTargets(targets);
  syncUI(targets);
};

counters.forEach(animateValue);

if (runProgress) {
  let progress = 42;
  setInterval(() => {
    progress = (progress + 3) % 100;
    runProgress.style.width = `${progress}%`;
  }, 1500);
}

toggle?.addEventListener("click", () => {
  body.classList.toggle("theme--frost");
});

targetForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const formData = new FormData(targetForm);
  const target = {
    name: formData.get("name")?.toString().trim(),
    url: formData.get("url")?.toString().trim(),
    category: formData.get("category")?.toString().trim(),
    location: formData.get("location")?.toString().trim(),
  };
  if (!target.name || !target.url) {
    return;
  }
  addTarget(target);
  targetForm.reset();
});

targetsList?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-target]");
  if (!button) return;
  removeTarget(Number(button.dataset.removeTarget));
});

syncUI(loadTargets());
