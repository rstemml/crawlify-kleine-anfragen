export function formatDate(dateStr, fallback = '') {
  if (!dateStr) return fallback;
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  } catch {
    return dateStr;
  }
}

export function formatShortDate(dateStr, fallback = '-') {
  if (!dateStr) return fallback;
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('de-DE');
  } catch {
    return dateStr;
  }
}

export function formatNumber(value) {
  if (value === null || value === undefined) return '0';
  return Number(value).toLocaleString('de-DE');
}
