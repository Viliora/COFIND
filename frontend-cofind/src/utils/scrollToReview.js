/** Scroll ke wrapper `#review-{id}` dan sorot sebentar. */
export function scrollToReviewById(reviewId, { behavior = 'smooth', highlight = true } = {}) {
  if (reviewId == null || reviewId === '') return false;
  const el = document.getElementById(`review-${reviewId}`);
  if (!el) return false;
  el.scrollIntoView({ behavior, block: 'center' });
  if (highlight) {
    el.classList.add('ring-2', 'ring-amber-500', 'ring-offset-2', 'dark:ring-offset-zinc-900');
    window.setTimeout(() => {
      el.classList.remove('ring-2', 'ring-amber-500', 'ring-offset-2', 'dark:ring-offset-zinc-900');
    }, 2200);
  }
  return true;
}

export function parseReviewIdFromHash(hash) {
  const match = String(hash || '').match(/^#review-(\d+)$/);
  return match ? match[1] : null;
}
