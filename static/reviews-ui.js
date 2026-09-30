(() => {
  const form = document.getElementById('review-form');
  const list = document.getElementById('review-list');
  if (!form || !list) return;

  const api = (url, options = {}) => fetch(url, options).then(async response => {
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    return data;
  });
  const readIds = () => JSON.parse(localStorage.getItem('cloudcost-owned-reviews') || '[]');
  const rememberId = id => localStorage.setItem('cloudcost-owned-reviews', JSON.stringify([...new Set([...readIds(), id])]));
  let browserKey = localStorage.getItem('cloudcost-review-browser-key');
  if (!browserKey) {
    browserKey = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem('cloudcost-review-browser-key', browserKey);
  }
  const status = message => {
    const target = document.getElementById('page-status') || document.getElementById('msg');
    if (target) target.textContent = message;
  };
  const action = (label, callback, selected = false) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    if (selected) button.classList.add('selected');
    button.addEventListener('click', callback);
    return button;
  };

  async function refresh() {
    try {
      const items = await api(`/api/reviews?voter=${encodeURIComponent(browserKey)}`);
      list.replaceChildren();
      if (!items.length) {
        const empty = document.createElement('p');
        empty.className = 'section-lead';
        empty.textContent = 'No reviews yet. Share your experience to add the first review.';
        list.append(empty);
        return;
      }
      items.forEach(item => {
        const card = document.createElement('article');
        card.className = 'review-card';
        const title = document.createElement('div');
        title.className = 'review-title';
        const rating = document.createElement('div');
        rating.className = 'stars';
        rating.setAttribute('aria-label', `${item.rating} out of 5 stars`);
        rating.textContent = `${'★'.repeat(item.rating)}${'☆'.repeat(5 - item.rating)} ${item.rating}/5`;
        const date = document.createElement('span');
        date.className = 'review-meta';
        date.textContent = new Date(`${item.created_at}Z`).toLocaleDateString();
        title.append(rating, date);
        const quote = document.createElement('p');
        quote.className = 'review-text';
        quote.textContent = `“${item.review}”`;
        const byline = document.createElement('p');
        byline.className = 'review-meta';
        byline.textContent = `${item.name} · ${item.role}`;
        const actions = document.createElement('div');
        actions.className = 'review-actions';
        actions.append(
          action(`Like (${item.likes})`, () => vote(item.id, 'like'), item.my_vote === 'like'),
          action(`Dislike (${item.dislikes})`, () => vote(item.id, 'dislike'), item.my_vote === 'dislike')
        );
        if (item.can_edit || readIds().includes(item.id)) {
          actions.append(action('Edit', () => editForm(card, item)), action('Delete', () => remove(item.id)));
        }
        card.append(title, quote, byline, actions);
        list.append(card);
      });
    } catch (error) {
      status(error.message);
    }
  }

  async function vote(id, choice) {
    try {
      await api(`/api/reviews/${id}/vote`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({voter_key: browserKey, vote: choice})
      });
      await refresh();
    } catch (error) { status(error.message); }
  }

  function editForm(card, item) {
    const existing = card.querySelector('.review-edit');
    if (existing) { existing.remove(); return; }
    const editor = document.createElement('form');
    editor.className = 'review-edit';
    const name = document.createElement('input'); name.value = item.name; name.maxLength = 80; name.required = true; name.setAttribute('aria-label', 'Name');
    const role = document.createElement('input'); role.value = item.role; role.maxLength = 100; role.required = true; role.setAttribute('aria-label', 'Role or team');
    const rating = document.createElement('select'); rating.setAttribute('aria-label', 'Rating');
    for (let n = 5; n >= 1; n--) { const option = document.createElement('option'); option.value = n; option.textContent = `${n} stars`; rating.append(option); }
    rating.value = item.rating;
    const review = document.createElement('textarea'); review.value = item.review; review.maxLength = 1000; review.required = true; review.rows = 4; review.setAttribute('aria-label', 'Review text');
    const save = document.createElement('button'); save.type = 'submit'; save.textContent = 'Save changes';
    const cancel = action('Cancel', () => editor.remove());
    editor.append(name, role, rating, review, save, cancel);
    editor.addEventListener('submit', async event => {
      event.preventDefault(); save.disabled = true;
      try {
        await api(`/api/reviews/${item.id}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({owner_key:browserKey,name:name.value,role:role.value,rating:rating.value,review:review.value})});
        status('Review updated.'); await refresh();
      } catch (error) { status(error.message); save.disabled = false; }
    });
    card.append(editor);
  }

  async function remove(id) {
    if (!window.confirm('Delete your review? This cannot be undone.')) return;
    try {
      await api(`/api/reviews/${id}`, {method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({owner_key:browserKey})});
      localStorage.setItem('cloudcost-owned-reviews', JSON.stringify(readIds().filter(reviewId => reviewId !== id)));
      status('Review deleted.'); await refresh();
    } catch (error) { status(error.message); }
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const submit = form.querySelector('[type="submit"]'); submit.disabled = true;
    try {
      const item = await api('/api/reviews', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({owner_key:browserKey,name:document.getElementById('review-name').value,role:document.getElementById('review-role').value,rating:document.getElementById('review-rating').value,review:document.getElementById('review-text').value})});
      rememberId(item.id); form.reset(); status('Review submitted. You can edit or delete it from this browser.'); await refresh();
    } catch (error) { status(error.message); }
    finally { submit.disabled = false; }
  });

  refresh();
})();
