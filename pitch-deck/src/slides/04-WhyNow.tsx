import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { AnimatedCounter } from '../components/AnimatedCounter';
import { Shield, Brain, Coins, AlertTriangle } from 'lucide-react';
import { whyNowReasons } from '../data/market';
import { motion } from 'framer-motion';

const iconMap: Record<string, React.FC<{ size?: number; style?: React.CSSProperties }>> = {
  shield: Shield,
  brain: Brain,
  coins: Coins,
  alert: AlertTriangle,
};

const colorMap: Record<string, string> = {
  shield: '#00d4ff',
  brain: '#7c3aed',
  coins: '#10b981',
  alert: '#f59e0b',
};

function parseStatValue(stat: string): { value: number; prefix: string; suffix: string } {
  if (stat === '\u20AC35M') return { value: 35, prefix: '\u20AC', suffix: 'M' };
  if (stat === '72%') return { value: 72, prefix: '', suffix: '%' };
  if (stat === '40%') return { value: 40, prefix: '', suffix: '%' };
  if (stat === '$31.5B') return { value: 31.5, prefix: '$', suffix: 'B' };
  return { value: 0, prefix: '', suffix: '' };
}

export default function WhyNowSlide() {
  return (
    <SlideLayout slideKey={4} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        {/* Headline */}
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="slide-title text-center mb-12"
        >
          Four Forces{' '}
          <span className="gradient-text">Converging Now</span>
        </motion.h2>

        {/* Cards grid */}
        <StaggerContainer className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5" delay={0.3}>
          {whyNowReasons.map((reason) => {
            const Icon = iconMap[reason.icon];
            const color = colorMap[reason.icon];
            const parsed = parseStatValue(reason.stat);

            return (
              <FadeInItem key={reason.title}>
                <div className="glass-card flex flex-col items-center text-center h-full">
                  {/* Icon */}
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
                    style={{ backgroundColor: `${color}15` }}
                  >
                    {Icon && <Icon size={24} style={{ color }} />}
                  </div>

                  {/* Animated stat */}
                  <AnimatedCounter
                    value={parsed.value}
                    prefix={parsed.prefix}
                    suffix={parsed.suffix}
                    decimals={parsed.value % 1 !== 0 ? 1 : 0}
                    className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-slate-100"
                  />

                  {/* Title */}
                  <h3 className="text-base font-semibold text-slate-200 mt-3 mb-2">
                    {reason.title}
                  </h3>

                  {/* Description */}
                  <p className="text-sm text-slate-400 leading-relaxed">
                    {reason.detail}
                  </p>
                </div>
              </FadeInItem>
            );
          })}
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
