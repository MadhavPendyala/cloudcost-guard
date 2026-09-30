(() => {
  const header = document.querySelector('[data-auth-links]');
  if (!header) return;
  const login = header.querySelector('[data-login]');
  const signup = header.querySelector('[data-signup]');
  const name = header.querySelector('[data-user-name]');
  const logout = header.querySelector('[data-logout]');

  fetch('/api/auth/me').then(response => response.json()).then(data => {
    if (!data.authenticated) return;
    if (login) login.hidden = true;
    if (signup) signup.hidden = true;
    if (name) {
      name.hidden = false;
      name.textContent = data.user.name;
    }
    if (logout) logout.hidden = false;
  }).catch(() => {});

  logout?.addEventListener('click', async () => {
    logout.disabled = true;
    try {
      await fetch('/api/auth/logout', {method: 'POST'});
      window.location.reload();
    } finally {
      logout.disabled = false;
    }
  });
})();
