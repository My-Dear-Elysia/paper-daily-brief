(() => {
  const key = 'theme-pref';
  const btn = document.getElementById('theme-toggle');
  function apply() {
    const p = localStorage.getItem(key) || 'dark';
    document.documentElement.setAttribute('data-theme', p);
    if (btn) btn.textContent = p === 'dark' ? '🌙' : '☀️';
  }
  apply();
  window.__toggleTheme = () => {
    const cur = localStorage.getItem(key) || 'dark';
    const next = cur === 'dark' ? 'light' : 'dark';
    localStorage.setItem(key, next);
    apply();
  };
})();
