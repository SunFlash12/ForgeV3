import { motion, AnimatePresence } from 'framer-motion';
import { ReactNode } from 'react';

interface SlideLayoutProps {
  children: ReactNode;
  slideKey: number;
  className?: string;
  background?: 'default' | 'gradient' | 'dark' | 'accent';
}

const bgStyles: Record<string, string> = {
  default: 'bg-surface-900',
  gradient: 'bg-gradient-to-br from-surface-900 via-surface-800 to-surface-700',
  dark: 'bg-[#050510]',
  accent: 'bg-gradient-to-br from-surface-900 via-forge-950 to-surface-800',
};

const slideVariants = {
  enter: {
    opacity: 0,
    y: 20,
  },
  center: {
    opacity: 1,
    y: 0,
  },
  exit: {
    opacity: 0,
    y: -20,
  },
};

export function SlideLayout({
  children,
  slideKey,
  className = '',
  background = 'gradient',
}: SlideLayoutProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={slideKey}
        variants={slideVariants}
        initial="enter"
        animate="center"
        exit="exit"
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className={`slide-container ${bgStyles[background]} ${className}`}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

// Stagger container for child animations
interface StaggerContainerProps {
  children: ReactNode;
  className?: string;
  delay?: number;
}

export function StaggerContainer({ children, className = '', delay = 0 }: StaggerContainerProps) {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: {
          transition: {
            staggerChildren: 0.12,
            delayChildren: delay,
          },
        },
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// Individual animated item
interface FadeInItemProps {
  children: ReactNode;
  className?: string;
}

export function FadeInItem({ children, className = '' }: FadeInItemProps) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 20 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } },
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
