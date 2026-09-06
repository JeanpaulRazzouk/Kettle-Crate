(function () {
  if (!matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  const aurora = document.querySelector(".aurora");
  if (!aurora) return;

  let raf = null;
  document.addEventListener("mousemove", (e) => {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      const x = (e.clientX / window.innerWidth - 0.5) * 24;
      const y = (e.clientY / window.innerHeight - 0.5) * 24;
      aurora.style.setProperty("--parallax-x", x + "px");
      aurora.style.setProperty("--parallax-y", y + "px");
      raf = null;
    });
  });
})();
