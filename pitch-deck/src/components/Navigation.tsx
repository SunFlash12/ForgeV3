import { ChevronLeft, ChevronRight, Maximize } from 'lucide-react';

interface NavigationProps {
  currentSlide: number;
  totalSlides: number;
  mainSlideCount: number;
  onPrev: () => void;
  onNext: () => void;
  onGoTo: (index: number) => void;
  isFirst: boolean;
  isLast: boolean;
  progress: number;
}

export function Navigation({
  currentSlide,
  totalSlides,
  mainSlideCount,
  onPrev,
  onNext,
  onGoTo,
  isFirst,
  isLast,
  progress,
}: NavigationProps) {
  const isAppendix = currentSlide >= mainSlideCount;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 no-print">
      {/* Progress bar */}
      <div className="w-full h-0.5 bg-white/5">
        <div
          className="h-full bg-gradient-to-r from-cyber-blue to-forge-400 transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Navigation controls */}
      <div className="flex items-center justify-between px-6 py-3 bg-surface-900/80 backdrop-blur-md border-t border-white/5">
        <div className="flex items-center gap-4">
          <button
            onClick={onPrev}
            disabled={isFirst}
            className="p-2 rounded-lg hover:bg-white/5 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
            aria-label="Previous slide"
          >
            <ChevronLeft size={20} />
          </button>

          <span className="text-sm text-slate-400 font-mono tabular-nums min-w-[60px] text-center">
            {isAppendix
              ? `A${currentSlide - mainSlideCount + 1}`
              : currentSlide + 1}{' '}
            / {totalSlides}
          </span>

          <button
            onClick={onNext}
            disabled={isLast}
            className="p-2 rounded-lg hover:bg-white/5 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
            aria-label="Next slide"
          >
            <ChevronRight size={20} />
          </button>
        </div>

        {/* Slide dots with appendix separator */}
        <div className="hidden md:flex items-center gap-1.5">
          {Array.from({ length: totalSlides }, (_, i) => (
            <div key={i} className="flex items-center gap-1.5">
              {/* Appendix separator */}
              {i === mainSlideCount && (
                <div className="flex items-center gap-1.5 mr-0.5">
                  <div className="w-px h-3 bg-white/20" />
                  <span className="text-[9px] text-slate-500 uppercase tracking-wider font-medium">
                    App
                  </span>
                  <div className="w-px h-3 bg-white/20" />
                </div>
              )}
              <button
                onClick={() => onGoTo(i)}
                className={`w-2 h-2 rounded-full transition-all duration-300 ${
                  i === currentSlide
                    ? i >= mainSlideCount
                      ? 'bg-amber-400 w-6'
                      : 'bg-cyber-blue w-6'
                    : i < currentSlide
                    ? i >= mainSlideCount
                      ? 'bg-amber-400/50'
                      : 'bg-forge-400/60'
                    : 'bg-white/15 hover:bg-white/30'
                }`}
                aria-label={`Go to slide ${i + 1}`}
              />
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500 hidden sm:block">
            Arrow keys to navigate &middot; F for fullscreen
          </span>
          <button
            onClick={() => {
              if (document.fullscreenElement) {
                document.exitFullscreen();
              } else {
                document.documentElement.requestFullscreen();
              }
            }}
            className="p-2 rounded-lg hover:bg-white/5 transition-all"
            aria-label="Toggle fullscreen"
          >
            <Maximize size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
