/* Study Spot — shared front-end behaviour */
const toastEl = document.getElementById('toast');
let toastTimer;

function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2200);
}

/* ---- favorites: single delegated handler, works on every page ---- */
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.fav-btn');
  if (!btn) return;
  e.preventDefault();

  const id = btn.dataset.id;
  const res = await fetch(`/api/favorite/${id}`, { method: 'POST' });

  if (res.status === 401) {
    showToast('Log in to save favorites');
    setTimeout(() => {
      location.href = '/login?next=' + encodeURIComponent(location.pathname);
    }, 900);
    return;
  }
  if (!res.ok) { showToast('Something went wrong'); return; }

  const data = await res.json();
  document.querySelectorAll(`.fav-btn[data-id="${id}"]`).forEach((b) => {
    b.classList.toggle('favorited', data.favorited);
    const icon = b.querySelector('i');
    if (icon) {
      icon.classList.toggle('fas', data.favorited);
      icon.classList.toggle('far', !data.favorited);
    }
  });
  showToast(data.favorited ? '❤️ Added to favorites' : 'Removed from favorites');

  if (document.body.dataset.page === 'favorites') {
    setTimeout(() => location.reload(), 500);
  }
});

/* ---- restore favorite state on load ---- */
window.addEventListener('DOMContentLoaded', async () => {
  if (!window.IS_AUTH) return;
  try {
    const res = await fetch('/api/favorites');
    const data = await res.json();
    (data.favorites || []).forEach((id) => {
      document.querySelectorAll(`.fav-btn[data-id="${id}"]`).forEach((b) => {
        b.classList.add('favorited');
        const icon = b.querySelector('i');
        if (icon) { icon.classList.remove('far'); icon.classList.add('fas'); }
      });
    });
  } catch (_) { /* offline — ignore */ }
});