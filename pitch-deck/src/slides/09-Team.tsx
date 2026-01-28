import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { teamMembers, teamStats } from '../data/team';
import { motion } from 'framer-motion';

export default function Team({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        {/* Headline */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="text-center mb-8"
        >
          <h2 className="slide-title mb-3">
            Built to Win.{' '}
            <span className="gradient-text">Ready to Scale.</span>
          </h2>
          <p className="slide-subtitle">
            Deep expertise in AI, Web3, and knowledge systems
          </p>
        </motion.div>

        {/* Team member cards — 2 columns */}
        <StaggerContainer
          className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6 max-w-4xl mx-auto w-full mb-8"
          delay={0.3}
        >
          {teamMembers.map((member) => (
            <FadeInItem key={member.name}>
              <div className="glass-card flex flex-col items-center text-center py-6 md:py-8 px-5 h-full">
                {/* Circular initials avatar */}
                <div
                  className="w-16 h-16 md:w-20 md:h-20 rounded-full flex items-center justify-center mb-4"
                  style={{ backgroundColor: `${member.color}20` }}
                >
                  <span
                    className="text-xl md:text-2xl font-extrabold"
                    style={{ color: member.color }}
                  >
                    {member.initials}
                  </span>
                </div>

                {/* Name */}
                <h3 className="text-lg md:text-xl font-bold text-white mb-1">
                  {member.name}
                </h3>

                {/* Role */}
                <p
                  className="text-sm font-semibold mb-3"
                  style={{ color: member.color }}
                >
                  {member.role}
                </p>

                {/* Background */}
                <p className="text-sm text-slate-400 leading-relaxed mb-4">
                  {member.background}
                </p>

                {/* Highlights */}
                <div className="w-full pt-3 mt-auto border-t border-white/10 space-y-2">
                  {member.highlights.map((highlight) => (
                    <div
                      key={highlight}
                      className="flex items-start gap-2 text-left"
                    >
                      <div
                        className="w-1.5 h-1.5 rounded-full shrink-0 mt-1.5"
                        style={{ backgroundColor: member.color }}
                      />
                      <span className="text-xs text-slate-300 leading-relaxed">
                        {highlight}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </FadeInItem>
          ))}
        </StaggerContainer>

        {/* Team stats */}
        <StaggerContainer
          className="grid grid-cols-3 gap-3 md:gap-4 max-w-3xl mx-auto w-full"
          delay={0.6}
        >
          {teamStats.map((stat) => (
            <FadeInItem key={stat.label}>
              <div className="glass-card text-center py-4">
                <p
                  className={`font-extrabold text-white tracking-tight mb-1 ${
                    stat.value.length > 5
                      ? 'text-sm md:text-base'
                      : 'text-2xl md:text-3xl'
                  }`}
                >
                  {stat.value}
                </p>
                <p className="text-xs text-slate-400 uppercase tracking-wider">
                  {stat.label}
                </p>
              </div>
            </FadeInItem>
          ))}
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
