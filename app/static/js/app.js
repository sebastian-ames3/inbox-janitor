/**
 * Inbox Janitor - Client-side JavaScript
 *
 * Minimal JavaScript for toast notifications, analytics, etc.
 * Most interactivity handled by HTMX and Alpine.js (loaded from CDN).
 */

// Toast notification helper
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `fixed top-4 right-4 px-6 py-3 rounded-md shadow-lg z-50 ${
    type === 'success' ? 'bg-success-600 text-white' :
    type === 'error' ? 'bg-danger-600 text-white' :
    type === 'warning' ? 'bg-warning-600 text-white' :
    'bg-gray-600 text-white'
  }`;
  toast.textContent = message;
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'polite');

  document.body.appendChild(toast);

  // Auto-dismiss after 3 seconds
  setTimeout(() => {
    toast.style.transition = 'opacity 0.3s';
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Expose globally for HTMX responses to trigger
window.showToast = showToast;

// Log when app.js is loaded (debugging)
console.log('Inbox Janitor app.js loaded');
