import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { fundingAsk, useOfFunds, milestones } from '../data/financials';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { motion } from 'framer-motion';
import { Target, Rocket, DollarSign, Shield, Globe } from 'lucide-react';

const trackConfig: Record<string, { color: string; icon: typeof Target }> = {
  product: { color: '#3b82f6', icon: Rocket },
  revenue: { color: '#10b981', icon: DollarSign },
  web3: { color: '#f59e0b', icon: Globe },
  compliance: { color: '#a855f7', icon: Shield },
};

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-surface-900/95 border border-white/10 rounded-lg px-4 py-3 backdrop-blur-md">
        <p className="text-slate-200 text-sm font-semibold">{data.category}</p>
        <p className="text-cyan-400 text-lg font-bold">{data.percentage}%</p>
        <p className="text-slate-400 text-xs mt-1">{data.detail}</p>
      </div>
    );
  }
  return null;
};

export default function TheAsk({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="accent">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-6">
          {/* Headline */}
          <FadeInItem>
            <div className="text-center">
              <h1 className="slide-title">
                <span className="gradient-text">$8M</span>{' '}
                <span className="text-slate-100">to Capture the Market</span>
              </h1>
              <p className="slide-subtitle">
                {fundingAsk.stage} &mdash; {fundingAsk.runway} runway to $3M ARR
                and SOC 2 certification
              </p>
            </div>
          </FadeInItem>

          {/* Big Ask Number */}
          <FadeInItem>
            <div className="flex justify-center">
              <motion.div
                className="glass-card glow-blue px-10 py-4 text-center"
                initial={{ scale: 0.9 }}
                animate={{ scale: 1 }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
              >
                <p className="text-4xl sm:text-6xl md:text-7xl font-extrabold gradient-text tracking-tight">
                  {fundingAsk.formatted}
                </p>
                <p className="text-slate-300 text-base mt-1 font-medium tracking-wide">
                  {fundingAsk.stage}
                </p>
              </motion.div>
            </div>
          </FadeInItem>

          {/* Use of Funds (Pie) + Milestones (List) */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-4 md:gap-6 items-start">
              {/* Left: Donut Chart + Legend */}
              <div className="glass-card flex-1">
                <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                  Use of Funds
                </h3>
                <div className="flex items-center gap-4">
                  <div className="w-[160px] h-[160px] sm:w-[200px] sm:h-[200px] shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={useOfFunds}
                          cx="50%"
                          cy="50%"
                          innerRadius={55}
                          outerRadius={90}
                          paddingAngle={3}
                          dataKey="percentage"
                          animationDuration={1500}
                          stroke="none"
                        >
                          {useOfFunds.map((entry, i) => (
                            <Cell key={i} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Legend */}
                  <div className="flex flex-col gap-2 md:gap-2.5 flex-1">
                    {useOfFunds.map((fund, i) => (
                      <div key={i} className="flex items-center gap-2.5">
                        <div
                          className="w-3 h-3 rounded-sm shrink-0"
                          style={{ backgroundColor: fund.color }}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline justify-between gap-2">
                            <span className="text-xs text-slate-200 font-medium truncate">
                              {fund.category}
                            </span>
                            <span className="text-xs text-slate-400 font-bold shrink-0">
                              {fund.percentage}%
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right: Milestones */}
              <div className="glass-card flex-1">
                <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                  Key Milestones
                </h3>
                <div className="space-y-3">
                  {milestones.map((milestone, i) => {
                    const track = trackConfig[milestone.track];
                    const Icon = track.icon;
                    return (
                      <div key={i} className="flex items-start gap-3">
                        <div
                          className="w-2 h-2 rounded-full mt-1.5 shrink-0"
                          style={{ backgroundColor: track.color }}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline justify-between gap-2">
                            <span className="text-sm text-slate-200 font-medium">
                              {milestone.label}
                            </span>
                            <span className="text-xs text-slate-500 font-mono shrink-0">
                              {milestone.timeline}
                            </span>
                          </div>
                        </div>
                        <Icon
                          className="w-3.5 h-3.5 mt-0.5 shrink-0"
                          style={{ color: track.color }}
                        />
                      </div>
                    );
                  })}
                </div>

                {/* Track legend */}
                <div className="flex gap-4 mt-4 pt-3 border-t border-white/5">
                  {Object.entries(trackConfig).map(([key, cfg]) => (
                    <div key={key} className="flex items-center gap-1.5">
                      <div
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ backgroundColor: cfg.color }}
                      />
                      <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                        {key}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </FadeInItem>

          {/* Bottom Tagline */}
          <FadeInItem>
            <div className="text-center">
              <p className="text-sm text-slate-400 font-medium">
                <span className="text-cyan-400 font-semibold">
                  18-24 months runway
                </span>{' '}
                to{' '}
                <span className="text-emerald-400 font-semibold">$3M ARR</span>{' '}
                and{' '}
                <span className="text-purple-400 font-semibold">
                  SOC 2 certification
                </span>
              </p>
            </div>
          </FadeInItem>
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
