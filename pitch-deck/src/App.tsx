import { useSlideNavigation } from './hooks/useSlideNavigation';
import { Navigation } from './components/Navigation';
import { AnimatePresence } from 'framer-motion';

// Main deck (9 slides)
import TitleSlide from './slides/01-Title';
import ProblemSlide from './slides/02-Problem';
import SolutionSlide from './slides/03-Solution';
import ProductSlide from './slides/05-Product';
import MarketSizeSlide from './slides/07-MarketSize';
import BusinessModelSlide from './slides/08-BusinessModel';
import CompetitiveEdgeSlide from './slides/08-CompetitiveEdge';
import TeamSlide from './slides/09-Team';
import RoadmapAndAskSlide from './slides/RoadmapAndAsk';

// Appendix (3 slides)
import AppendixCapabilitiesSlide from './slides/AppendixCapabilities';
import AppendixTokenomicsSlide from './slides/AppendixTokenomics';
import AppendixFinancialsSlide from './slides/AppendixFinancials';

const TOTAL_SLIDES = 12;
const MAIN_SLIDE_COUNT = 9;

export default function App() {
  const { currentSlide, goTo, next, prev, isFirst, isLast, progress } =
    useSlideNavigation(TOTAL_SLIDES);

  const slides = [
    // Main deck
    <TitleSlide key={0} />,
    <ProblemSlide key={1} />,
    <SolutionSlide key={2} />,
    <ProductSlide key={3} />,
    <MarketSizeSlide key={4} slideKey={5} />,
    <BusinessModelSlide key={5} slideKey={6} />,
    <CompetitiveEdgeSlide key={6} slideKey={7} />,
    <TeamSlide key={7} slideKey={8} />,
    <RoadmapAndAskSlide key={8} slideKey={9} />,
    // Appendix
    <AppendixCapabilitiesSlide key={9} slideKey={10} />,
    <AppendixTokenomicsSlide key={10} slideKey={11} />,
    <AppendixFinancialsSlide key={11} slideKey={12} />,
  ];

  return (
    <div className="w-full h-full bg-surface-900 overflow-hidden">
      <AnimatePresence mode="wait">
        {slides[currentSlide]}
      </AnimatePresence>

      <Navigation
        currentSlide={currentSlide}
        totalSlides={TOTAL_SLIDES}
        mainSlideCount={MAIN_SLIDE_COUNT}
        onPrev={prev}
        onNext={next}
        onGoTo={goTo}
        isFirst={isFirst}
        isLast={isLast}
        progress={progress}
      />
    </div>
  );
}
