import { SlideLayout } from '../components/SlideLayout';
import { NetworkBackground } from '../components/NetworkBackground';
import { motion } from 'framer-motion';

export default function TitleSlide() {
  return (
    <SlideLayout slideKey={1} background="dark">
      <NetworkBackground />

      <div className="slide-content flex flex-col items-center justify-center text-center h-full">
        {/* Main Title */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        >
          <h1 className="text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tight leading-none">
            <span className="gradient-text">Forge</span>
          </h1>
        </motion.div>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3, ease: 'easeOut' }}
          className="text-base sm:text-xl md:text-2xl lg:text-3xl font-light text-slate-200 mt-4 tracking-wide"
        >
          The Institutional Memory Engine
        </motion.p>

        {/* Tagline */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6, ease: 'easeOut' }}
          className="mt-8 flex items-center gap-2 md:gap-3 text-sm md:text-base lg:text-lg font-medium tracking-[0.2em] uppercase text-slate-400"
        >
          <span>Persistent</span>
          <span className="w-1.5 h-1.5 rounded-full bg-cyber-blue" />
          <span>Traceable</span>
          <span className="w-1.5 h-1.5 rounded-full bg-forge-400" />
          <span>Governable</span>
        </motion.div>

        {/* Knowledge Infrastructure line */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.9, ease: 'easeOut' }}
          className="mt-6 text-sm sm:text-base md:text-lg text-slate-500 font-light italic"
        >
          Knowledge Infrastructure for the AI Age
        </motion.p>

        {/* Bottom: Round / Year */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 1.2, ease: 'easeOut' }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2"
        >
          <p className="text-sm md:text-base text-slate-500 tracking-widest uppercase font-medium">
            Seed / Pre-Series A &middot; 2026
          </p>
        </motion.div>
      </div>
    </SlideLayout>
  );
}
