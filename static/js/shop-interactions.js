(function () {
  const timers = new WeakMap();
  const slideActive = ['opacity-100', 'scale-100', 'z-[2]'];
  const slideInactive = ['opacity-0', 'scale-[.985]', 'z-0'];
  const dotBase = ['h-2', 'rounded-full', 'transition-all', 'duration-200'];
  const dotActive = ['w-6', 'bg-green-700'];
  const dotInactive = ['w-2', 'bg-slate-900/25'];
  const thumbActive = ['opacity-100', 'border-green-600', '-translate-y-0.5'];
  const thumbInactive = ['opacity-70', 'border-slate-200'];

  function swapClasses(el, removeClasses, addClasses) {
    el.classList.remove(...removeClasses);
    el.classList.add(...addClasses);
  }

  function setSlideActive(slide, active) {
    swapClasses(slide, active ? slideInactive : slideActive, active ? slideActive : slideInactive);
    slide.dataset.active = active ? 'true' : 'false';
    slide.classList.toggle('is-active', active);
  }

  function getSlides(carousel) {
    return Array.from(carousel.querySelectorAll('[data-carousel-slide]'));
  }

  function getActiveIndex(slides) {
    const current = slides.findIndex((slide) => slide.dataset.active === 'true' || slide.classList.contains('is-active'));
    return current >= 0 ? current : 0;
  }

  function syncDots(carousel, index, total) {
    const dotsWrap = carousel.querySelector('[data-carousel-dots]');
    if (!dotsWrap) return;
    if (dotsWrap.children.length !== total) {
      dotsWrap.innerHTML = '';
      for (let i = 0; i < total; i += 1) {
        const dot = document.createElement('span');
        dot.className = [...dotBase, ...dotInactive].join(' ');
        dotsWrap.appendChild(dot);
      }
    }
    Array.from(dotsWrap.children).forEach((dot, i) => {
      swapClasses(dot, i === index ? dotInactive : dotActive, i === index ? dotActive : dotInactive);
    });
  }

  function syncThumbs(root, index) {
    const container = root.closest('main, section, article') || document;
    container.querySelectorAll('[data-carousel-thumb]').forEach((thumb) => {
      const active = Number(thumb.dataset.carouselThumb) === index;
      swapClasses(thumb, active ? thumbInactive : thumbActive, active ? thumbActive : thumbInactive);
      thumb.classList.toggle('is-active', active);
    });
  }

  function showSlide(carousel, index) {
    const slides = getSlides(carousel);
    if (!slides.length) return;
    const next = (index + slides.length) % slides.length;
    slides.forEach((slide, i) => setSlideActive(slide, i === next));
    carousel.dataset.activeIndex = String(next);
    syncDots(carousel, next, slides.length);
    syncThumbs(carousel, next);
  }

  function restartTimer(carousel) {
    const previous = timers.get(carousel);
    if (previous) window.clearInterval(previous);
    const slides = getSlides(carousel);
    if (slides.length <= 1) return;
    const interval = Number(carousel.dataset.interval || 7000);
    const timer = window.setInterval(() => {
      if (!document.body.contains(carousel)) {
        window.clearInterval(timer);
        return;
      }
      showSlide(carousel, getActiveIndex(getSlides(carousel)) + 1);
    }, interval);
    timers.set(carousel, timer);
  }

  function initCarousel(carousel) {
    if (carousel.dataset.carouselReady === 'true') return;
    carousel.dataset.carouselReady = 'true';
    const slides = getSlides(carousel);
    if (!slides.length) return;
    showSlide(carousel, getActiveIndex(slides));

    const prev = carousel.querySelector('[data-carousel-prev]');
    const next = carousel.querySelector('[data-carousel-next]');
    if (prev) {
      prev.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        showSlide(carousel, getActiveIndex(getSlides(carousel)) - 1);
        restartTimer(carousel);
      });
    }
    if (next) {
      next.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        showSlide(carousel, getActiveIndex(getSlides(carousel)) + 1);
        restartTimer(carousel);
      });
    }

    const scope = carousel.parentElement || document;
    scope.querySelectorAll('[data-carousel-thumb]').forEach((thumb) => {
      thumb.addEventListener('click', (event) => {
        event.preventDefault();
        showSlide(carousel, Number(thumb.dataset.carouselThumb || 0));
        restartTimer(carousel);
      });
    });

    carousel.addEventListener('mouseenter', () => {
      const timer = timers.get(carousel);
      if (timer) window.clearInterval(timer);
    });
    carousel.addEventListener('mouseleave', () => restartTimer(carousel));
    restartTimer(carousel);
  }

  function initAllCarousels(root) {
    (root || document).querySelectorAll('[data-product-carousel]').forEach(initCarousel);
  }

  function persistGridColumns() {
    const select = document.getElementById('columnsSelect');
    if (!select) return;
    const saved = window.localStorage.getItem('powerpay-grid-columns');
    const url = new URL(window.location.href);
    if (saved && !url.searchParams.has('columns') && ['3', '4', '5'].includes(saved)) {
      select.value = saved;
      const hiddenGrid = document.getElementById('productsGrid');
      if (hiddenGrid) hiddenGrid.style.setProperty('--grid-columns', saved);
    }
    select.addEventListener('change', () => window.localStorage.setItem('powerpay-grid-columns', select.value));
  }

  document.addEventListener('DOMContentLoaded', () => {
    initAllCarousels(document);
    persistGridColumns();
  });

  document.body.addEventListener('htmx:afterSwap', (event) => {
    initAllCarousels(event.target);
    persistGridColumns();
  });
})();
