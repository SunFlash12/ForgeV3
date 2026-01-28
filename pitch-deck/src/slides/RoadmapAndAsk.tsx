import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { fundingAsk, useOfFunds, milestones } from '../data/financials';
import { roadmapPhases } from '../data/features';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { motion } from 'framer-motion';
import { Target, Rocket, DollarSign, Shield, Globe, CheckCircle, Radio, Clock } from 'lucide-react';

const trackConfig: Record<string, { color: string; icon: typeof Target }> = {
  product: { color: '#3b82f6', icon: Rocket },
  revenue: { color: '#10b981', icon: DollarSign },
  web3: { color: '#f59e0b', icon: Globe },
  compliance: { color: '#a855f7', icon: Shield },
};

const statusConfig = {
  complete: { dotClass: 'bg-emerald-400', icon: CheckCircle, color: 'text-emerald-400', label: 'DONE' },
  current: { dotClass: 'bg-cyan-400', icon: Radio, color: 'text-cyan-400', label: 'NOW' },
  planned: { dotClass: 'bg-slate-500', icon: Clock, color: 'text-slate-500', label: 'NEXT' },
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

export default function RoadmapAndAsk({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="accent">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-4">
          {/* Headline + Big Ask */}
          <FadeInItem>
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
              <div>
                <h1 className="slide-title">
                  <span className="gradient-text">{fundingAsk.formatted}</span>{' '}
                  <span className="text-slate-100">to Capture the Market</span>
                </h1>
                <p className="text-sm text-slate-400 mt-1">
                  {fundingAsk.stage} &mdash; {fundingAsk.runway} runway to $3M ARR
                </p>
              </div>
              <motion.div
                className="glass-card glow-blue px-6 py-3 text-center shrink-0"
                initial={{ scale: 0.9 }}
                animate={{ scale: 1 }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
              >
                <p className="text-3xl sm:text-4xl md:text-5xl font-extrabold gradient-text tracking-tight">
                  {fundingAsk.formatted}
                </p>
                <p className="text-slate-400 text-xs mt-0.5 font-medium">
                  {fundingAsk.stage}
                </p>
              </motion.div>
            </div>
          </FadeInItem>

          {/* Condensed Roadmap Timeline */}
          <FadeInItem>
            <div className="relative">
              {/* Horizontal line */}
              <div className="hidden md:block absolute top-[18px] left-[calc(12.5%)] right-[calc(12.5%)] h-[2px] bg-gradient-to-r from-emerald-500/60 via-cyan-500/40 to-slate-600/30 z-0" />

              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 relative z-10">
                {roadmapPhases.map((phase, i) => {
                  const config = statusConfig[phase.status];
                  const isPlanned = phase.status === 'planned';
                  return (
                    <div key={i} className="flex flex-col items-center">
                      {/* Dot */}
                      <div className="mb-2">
                        {phase.status === 'current' ? (
                          <motion.div
                            className="w-3.5 h-3.5 rounded-full bg-cyan-400"
                            animate={{
                              boxShadow: [
                                '0 0 0 0 rgba(0, 212, 255, 0.4)',
                                '0 0 0 8px rgba(0, 212, 255, 0)',
                              ],
                            }}
                            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
                          />
                        ) : (
                          <div
                            className={`w-3.5 h-3.5 rounded-full ${config.dotClass} ${
                              phase.status === 'complete' ? 'ring-2 ring-emerald-400/30' : ''
                            }`}
                          />
                        )}
                      </div>

                      {/* Card */}
                      <div
                        className={`glass-card w-full py-2.5 px-3 ${
                          isPlanned ? 'opacity-60' : ''
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span
                            className={`text-[9px] font-bold uppercase tracking-widest ${config.color}`}
                          >
                            {config.label}
                          </span>
                        </div>
                        <h3
                          className={`text-[11px] font-bold mb-1.5 ${
                            isPlanned ? 'text-slate-400' : 'text-slate-100'
                          }`}
                        >
                          {phase.phase}
                        </h3>
                        <ul className="space-y-0.5">
                          {phase.items.slice(0, 3).map((item, j) => (
                            <li
                              key={j}
                              className={`text-[9px] leading-relaxed flex items-start gap-1 ${
                                isPlanned ? 'text-slate-500' : 'text-slate-300'
                              }`}
                            >
                              <span
                                className={`mt-1 w-1 h-1 rounded-full shrink-0 ${
                                  phase.status === 'complete'
                                    ? 'bg-emerald-400/60'
                                    : phase.status === 'current'
                                      ? 'bg-cyan-400/60'
                                      : 'bg-slate-600'
                                }`}
                              />
                              {item}
                            </li>
                          ))}
                          {phase.items.length > 3 && (
                            <li className="text-[9px] text-slate-500">
                              +{phase.items.length - 3} more
                            </li>
                          )}
                        </ul>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </FadeInItem>

          {/* Use of Funds + Milestones */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-3 md:gap-4 items-start">
              {/* Donut Chart + Legend */}
              <div className="glass-card flex-1">
                <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">
                  Use of Funds
                </h3>
                <div className="flex items-center gap-3">
                  <div className="w-[130px] h-[130px] sm:w-[150px] sm:h-[150px] shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={useOfFunds}
                          cx="50%"
                          cy="50%"
                          innerRadius={45}
                          outerRadius={70}
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
                  <div className="flex flex-col gap-1.5 flex-1">
                    {useOfFunds.map((fund, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <div
                          className="w-2.5 h-2.5 rounded-sm shrink-0"
                          style={{ backgroundColor: fund.color }}
                        />
                        <span className="text-[10px] text-slate-200 font-medium truncate flex-1">
                          {fund.category}
                        </span>
                        <span className="text-[10px] text-slate-400 font-bold shrink-0">
                          {fund.percentage}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Milestones */}
              <div className="glass-card flex-1">
                <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">
                  Key Milestones
                </h3>
                <div className="space-y-2">
                  {milestones.map((milestone, i) => {
                    const track = trackConfig[milestone.track];
                    return (
                      <div key={i} className="flex items-start gap-2">
                        <div
                          className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                          style={{ backgroundColor: track.color }}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline justify-between gap-2">
                            <span className="text-xs text-slate-200 font-medium">
                              {milestone.label}
                            </span>
                            <span className="text-[10px] text-slate-500 font-mono shrink-0">
                              {milestone.timeline}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </FadeInItem>

          {/* Bottom Tagline */}
          <FadeInItem>
            <div className="text-center">
              <p className="text-xs text-slate-400 font-medium">
                <span className="text-cyan-400 font-semibold">18-24 months runway</span>{' '}
                to{' '}
                <span className="text-emerald-400 font-semibold">$3M ARR</span>{' '}
                and{' '}
                <span className="text-purple-400 font-semibold">SOC 2 certification</span>
              </p>
            </div>
          </FadeInItem>
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
