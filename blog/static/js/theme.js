(() => {
  const key = 'theme-pref';
  function apply() {
    const p = localStorage.getItem(key) || 'dark';
    document.documentElement.setAttribute('data-theme', p);
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = p === 'dark' ? '🌙' : '☀️';
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else {
    apply();
  }
  document.addEventListener('click', (e) => {
    if (e.target.id === 'theme-toggle') {
      const cur = localStorage.getItem(key) || 'dark';
      const next = cur === 'dark' ? 'light' : 'dark';
      localStorage.setItem(key, next);
      apply();
    }
  });
})();
