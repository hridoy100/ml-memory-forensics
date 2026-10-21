// Code blocks remain readable when the Clipboard API is unavailable.
if (navigator.clipboard && window.isSecureContext) {
  document.querySelectorAll('.copy-button').forEach((button) => {
    button.hidden = false;
    button.addEventListener('click', async () => {
      const code = button.closest('.code-block').querySelector('code');
      try {
        await navigator.clipboard.writeText(code.textContent);
        button.textContent = 'Copied';
      } catch {
        button.textContent = 'Select text to copy';
      }
      setTimeout(() => { button.textContent = 'Copy'; }, 2000);
    });
  });
}

const contentsLinks = [...document.querySelectorAll('.contents a')];
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver((entries) => {
    const visible = entries.find((entry) => entry.isIntersecting);
    if (!visible) return;
    contentsLinks.forEach((link) => {
      if (link.hash === `#${visible.target.id}`) {
        link.setAttribute('aria-current', 'location');
      } else {
        link.removeAttribute('aria-current');
      }
    });
  }, {rootMargin: '-10% 0px -60% 0px'});
  document.querySelectorAll('article section[id]').forEach((section) => observer.observe(section));
}
