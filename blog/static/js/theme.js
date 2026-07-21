(() => {
  const key = 'theme-pref';
  const toggle = document.getElementById('theme-toggle');
  const sun = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>';
  const moon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  function apply() {
    const p = localStorage.getItem(key) || 'dark';
    document.documentElement.setAttribute('data-theme', p);
    if (toggle) toggle.innerHTML = p === 'dark' ? sun : moon;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else { apply(); }
  document.addEventListener('click', (e) => {
    if (e.target.closest('#theme-toggle')) {
      const cur = localStorage.getItem(key) || 'dark';
      const next = cur === 'dark' ? 'light' : 'dark';
      localStorage.setItem(key, next);
      apply();
    }
  });
})();
