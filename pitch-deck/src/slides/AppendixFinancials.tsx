import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { AnimatedCounter } from '../components/AnimatedCounter';
import {
  revenueProjections,
  annualRevenue,
  unitEconomics,
  pricingTiers,
} from '../data/financials';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { Calculator, TrendingUp, DollarSign, Shield, Brain, Globe, Building2 } from 'lucide-react';

const formatRevenue = (value: number) => {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value}`;
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-surface-900/95 border border-white/10 rounded-lg px-3 py-2 backdrop-blur-md">
        <p className="text-slate-300 text-[10px] font-medium">{label}</p>
        <p className="text-cyan-400 text-sm font-bold">
          {formatRevenue(payload[0].value)}
        </p>
      </div>
    );
  }
  return null;
};

const gtmPhases = [
  {
    phase: 'LAND',
    title: 'Compliance-First Entry',
    targets: ['Legal Services', 'Biotech & Pharma', 'Financial Services'],
    icon: Shield,
    color: '#00d4ff',
  },
  {
    phase: 'EXPAND',
    title: 'Full Intelligence Platform',
    targets: ['Knowledge Mgmt', 'AI Governance', 'Decision Intelligence'],
    icon: Brain,
    color: '#7c3aed',
  },
  {
    phase: 'NETWORK',
    title: 'Ecosystem & Web3',
    targets: ['Cross-Org Federation', 'Knowledge Marketplace', 'Autonomous Agents'],
    icon: Globe,
    color: '#10b981',
  },
];

export default function AppendixFinancials({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="dark">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-3">
          {/* Title */}
          <FadeInItem>
            <div className="flex items-center gap-3 mb-1">
              <Calculator className="w-5 h-5 text-emerald-400" />
              <h1 className="text-lg md:text-xl lg:text-2xl font-bold text-slate-100">
                Appendix C:{' '}
                <span className="gradient-text">Financial Model &amp; Go-to-Market</span>
              </h1>
            </div>
          </FadeInItem>

          {/* Top: Revenue chart + 3 key metrics */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-2 md:gap-3">
              {/* Revenue AreaChart */}
              <div className="glass-card flex-1 py-2.5 px-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
                  <h3 className="text-[9px] font-bold text-slate-300 uppercase tracking-wider">
                    Quarterly Revenue Projection
                  </h3>
                </div>
                <div className="w-full h-[120px] sm:h-[150px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={revenueProjections}
                      margin={{ top: 5, right: 10, left: 10, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient id="finGtmRevenueGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.4} />
                          <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis
                        dataKey="label"
                        tick={{ fill: '#94a3b8', fontSize: 8 }}
                        axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: '#94a3b8', fontSize: 8 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={formatRevenue}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Area
                        type="monotone"
                        dataKey="revenue"
                        stroke="#00d4ff"
                        strokeWidth={2}
                        fill="url(#finGtmRevenueGrad)"
                        animationDuration={1500}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex gap-2 mt-1.5 pt-1.5 border-t border-white/5">
                  {annualRevenue.map((yr, i) => (
                    <div key={yr.year} className="flex-1 text-center">
                      <p className="text-[8px] text-slate-500 uppercase">{yr.year}</p>
                      <p className={`text-xs font-extrabold ${i === 2 ? 'gradient-text' : 'text-slate-200'}`}>
                        {yr.label}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* 3 key metrics + pricing tiers */}
              <div className="flex flex-col gap-2 w-full md:w-[200px] md:shrink-0">
                <div className="glass-card flex items-center gap-3 py-2.5 px-3">
                  <DollarSign className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div>
                    <AnimatedCounter
                      value={unitEconomics.grossMargin}
                      suffix="%"
                      className="metric-value text-emerald-400 text-xl"
                    />
                    <span className="metric-label text-[9px] block">Gross Margin</span>
                  </div>
                </div>
                <div className="glass-card flex items-center gap-3 py-2.5 px-3">
                  <DollarSign className="w-4 h-4 text-cyan-400 shrink-0" />
                  <div>
                    <div className="text-xl font-extrabold text-cyan-400">
                      ${unitEconomics.avgContractValue.toLocaleString()}
                    </div>
                    <span className="metric-label text-[9px] block">Avg Contract/yr</span>
                  </div>
                </div>
                <div className="glass-card flex items-center gap-3 py-2.5 px-3">
                  <TrendingUp className="w-4 h-4 text-purple-400 shrink-0" />
                  <div>
                    <AnimatedCounter
                      value={unitEconomics.ltvCacRatio}
                      suffix="x"
                      decimals={1}
                      className="metric-value text-purple-400 text-xl"
                    />
                    <span className="metric-label text-[9px] block">LTV / CAC</span>
                  </div>
                </div>
              </div>
            </div>
          </FadeInItem>

          {/* Middle: GTM 3-phase strip */}
          <FadeInItem>
            <div className="glass-card py-2.5 px-3">
              <div className="flex items-center gap-2 mb-2">
                <Building2 className="w-3.5 h-3.5 text-amber-400" />
                <h3 className="text-[9px] font-bold text-slate-300 uppercase tracking-wider">
                  Go-to-Market: Land &rarr; Expand &rarr; Network
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {gtmPhases.map((phase, i) => {
                  const Icon = phase.icon;
                  return (
                    <div
                      key={i}
                      className="flex items-start gap-2 bg-white/[0.03] rounded-lg px-2.5 py-2 border border-white/5"
                    >
                      <div
                        className="w-6 h-6 rounded flex items-center justify-center shrink-0 mt-0.5"
                        style={{ backgroundColor: `${phase.color}15` }}
                      >
                        <Icon className="w-3 h-3" style={{ color: phase.color }} />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span
                            className="text-[8px] font-extrabold uppercase tracking-widest"
                            style={{ color: phase.color }}
                          >
                            {phase.phase}
                          </span>
                          <span className="text-[9px] text-slate-300 font-semibold">
                            {phase.title}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-x-2 gap-y-0.5">
                          {phase.targets.map((t) => (
                            <span key={t} className="text-[8px] text-slate-500">
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </FadeInItem>

          {/* Bottom: Pricing tiers */}
          <FadeInItem>
            <div className="glass-card py-2.5 px-3">
              <h3 className="text-[9px] font-bold text-slate-300 uppercase tracking-wider mb-2">
                Pricing Tiers
              </h3>
              <div className="overflow-hidden rounded-lg border border-white/5">
                <table className="w-full text-left">
                  <thead>
                    <tr className="bg-white/5">
                      <th className="px-2 py-1 text-[8px] font-bold text-slate-400 uppercase tracking-wider">Tier</th>
                      <th className="px-2 py-1 text-[8px] font-bold text-slate-400 uppercase tracking-wider">$/mo</th>
                      <th className="px-2 py-1 text-[8px] font-bold text-slate-400 uppercase tracking-wider">Queries</th>
                      <th className="px-2 py-1 text-[8px] font-bold text-slate-400 uppercase tracking-wider">Target</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pricingTiers.map((tier, i) => (
                      <tr key={i} className="border-t border-white/5 hover:bg-white/[0.02]">
                        <td className="px-2 py-1 text-[9px] text-cyan-400 font-semibold">{tier.tier}</td>
                        <td className="px-2 py-1 text-[9px] text-slate-200 font-mono">${tier.price.toLocaleString()}</td>
                        <td className="px-2 py-1 text-[9px] text-slate-300">{tier.queries}</td>
                        <td className="px-2 py-1 text-[9px] text-slate-400">{tier.target}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </FadeInItem>
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
