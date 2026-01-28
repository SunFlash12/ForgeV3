import { useState, useEffect, useCallback } from 'react';

export function useSlideNavigation(totalSlides: number) {
  const [currentSlide, setCurrentSlide] = useState(() => {
    const hash = window.location.hash.replace('#', '');
    const num = parseInt(hash, 10);
    return num >= 0 && num < totalSlides ? num : 0;
  });

  const goTo = useCallback(
    (index: number) => {
      if (index >= 0 && index < totalSlides) {
        setCurrentSlide(index);
        window.location.hash = `#${index}`;
      }
    },
    [totalSlides]
  );

  const next = useCallback(() => goTo(currentSlide + 1), [currentSlide, goTo]);
  const prev = useCallback(() => goTo(currentSlide - 1), [currentSlide, goTo]);
  const goToFirst = useCallback(() => goTo(0), [goTo]);
  const goToLast = useCallback(() => goTo(totalSlides - 1), [goTo, totalSlides]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      switch (e.key) {
        case 'ArrowRight':
        case 'ArrowDown':
        case ' ':
        case 'PageDown':
          e.preventDefault();
          next();
          break;
        case 'ArrowLeft':
        case 'ArrowUp':
        case 'PageUp':
          e.preventDefault();
          prev();
          break;
        case 'Home':
          e.preventDefault();
          goToFirst();
          break;
        case 'End':
          e.preventDefault();
          goToLast();
          break;
        case 'f':
        case 'F':
          if (!e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            if (document.fullscreenElement) {
              document.exitFullscreen();
            } else {
              document.documentElement.requestFullscreen();
            }
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [next, prev, goToFirst, goToLast]);

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      const num = parseInt(hash, 10);
      if (num >= 0 && num < totalSlides) {
        setCurrentSlide(num);
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [totalSlides]);

  return {
    currentSlide,
    goTo,
    next,
    prev,
    goToFirst,
    goToLast,
    isFirst: currentSlide === 0,
    isLast: currentSlide === totalSlides - 1,
    progress: ((currentSlide + 1) / totalSlides) * 100,
  };
}
