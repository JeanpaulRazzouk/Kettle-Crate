function confettiBurst(originX, originY, count) {
  const colors = ["#2f6f4e", "#d97748", "#e0a339", "#3b7ce0", "#7cd9a5"];
  count = count || 50;
  const x = originX ?? window.innerWidth / 2;
  const y = originY ?? window.innerHeight * 0.3;

  for (let i = 0; i < count; i++) {
    const el = document.createElement("div");
    el.className = "confetti-piece";
    el.style.left = x + (Math.random() * 240 - 120) + "px";
    el.style.top = y + "px";
    el.style.background = colors[Math.floor(Math.random() * colors.length)];
    el.style.setProperty("--drift", Math.random() * 320 - 160 + "px");
    el.style.setProperty("--spin", Math.random() * 720 - 360 + "deg");
    el.style.animationDuration = 1.8 + Math.random() * 1.4 + "s";
    if (Math.random() > 0.5) el.style.borderRadius = "50%";
    document.body.appendChild(el);
    el.addEventListener("animationend", () => el.remove());
  }
}

function animateCount(el, target, duration) {
  duration = duration || 900;
  const start = Number(el.dataset.value || 0);
  const startTime = performance.now();

  function tick(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = Math.round(start + (target - start) * eased);
    el.textContent = value;
    if (progress < 1) requestAnimationFrame(tick);
    else el.dataset.value = target;
  }
  requestAnimationFrame(tick);
}
