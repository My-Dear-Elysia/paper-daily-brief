(() => {
  const key = 'theme-pref';
  const mq = window.matchMedia('(prefers-color-scheme:dark)');
  function apply() {
    const p = localStorage.getItem(key) || 'system';
    const d = p === 'dark' || (p === 'system' && mq.matches);
    document.documentElement.setAttribute('data-theme', d ? 'dark' : 'light');
    document.querySelectorAll('.theme-switch a').forEach(el => {
      el.classList.toggle('active', el.id === 't-' + p);
    });
  }
  apply();
  mq.addEventListener('change', apply);
  window.__setTheme = (val) => {
    localStorage.setItem(key, val);
    apply();
  };
})();
