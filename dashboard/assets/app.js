const toggle = document.querySelector("[data-theme-toggle]");
const body = document.body;

const counters = document.querySelectorAll("[data-count]");
const runProgress = document.querySelector("[data-progress]");

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
