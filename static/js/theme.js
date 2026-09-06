function initThemeToggle(btn) {
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("kc-theme", theme);
    btn.textContent = theme === "dark" ? "☀️" : "🌙";
  }

  const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  btn.textContent = current === "dark" ? "☀️" : "🌙";

  btn.addEventListener("click", () => {
    const now = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    apply(now);
  });
}
