import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { AnimatedCounter } from '../components/AnimatedCounter';
import { revenueProjections, annualRevenue, unitEconomics } from '../data/financials';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { TrendingUp, DollarSign, BarChart3 } from 'lucide-react';

const formatRevenue = (value: number) => {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value}`;
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-surface-900/95 border border-white/10 rounded-lg px-4 py-3 backdrop-blur-md">
        <p className="text-slate-300 text-sm font-medium">{label}</p>
        <p className="text-cyan-400 text-lg font-bold">
          {formatRevenue(payload[0].value)}
        </p>
      </div>
    );
  }
  return null;
};

export default function Financials({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-6">
          {/* Headline */}
          <FadeInItem>
            <h1 className="slide-title">
              <span className="gradient-text">$900K Year 1.</span>{' '}
              <span className="text-slate-100">$13M Year 3.</span>
            </h1>
            <p className="slide-subtitle">
              Conservative projections based on tier-based SaaS pricing and
              tokenized revenue streams
            </p>
          </FadeInItem>

          {/* Main content: Chart + Metrics */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-4 md:gap-6 items-stretch">
              {/* Area Chart */}
              <div className="glass-card flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-4">
                  <TrendingUp className="w-5 h-5 text-cyan-400" />
                  <span className="text-sm font-medium text-slate-300 uppercase tracking-wider">
                    Quarterly Revenue Projection
                  </span>
                </div>
                <div className="w-full h-[180px] sm:h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={revenueProjections}
                      margin={{ top: 10, right: 10, left: 10, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="revenueGradient"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#00d4ff"
                            stopOpacity={0.4}
                          />
                          <stop
                            offset="50%"
                            stopColor="#3b82f6"
                            stopOpacity={0.15}
                          />
                          <stop
                            offset="100%"
                            stopColor="#3b82f6"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="rgba(255,255,255,0.05)"
                      />
                      <XAxis
                        dataKey="label"
                        tick={{ fill: '#94a3b8', fontSize: 12 }}
                        axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: '#94a3b8', fontSize: 12 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={formatRevenue}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Area
                        type="monotone"
                        dataKey="revenue"
                        stroke="#00d4ff"
                        strokeWidth={2.5}
                        fill="url(#revenueGradient)"
                        animationDuration={1500}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Right Side Metrics */}
              <div className="flex flex-col gap-4 w-full md:w-[240px] md:shrink-0">
                <div className="glass-card flex flex-col items-center justify-center text-center flex-1">
                  <DollarSign className="w-6 h-6 text-emerald-400 mb-2" />
                  <AnimatedCounter
                    value={unitEconomics.grossMargin}
                    suffix="%"
                    className="metric-value text-emerald-400"
                  />
                  <span className="metric-label">Gross Margin</span>
                </div>
                <div className="glass-card flex flex-col items-center justify-center text-center flex-1">
                  <BarChart3 className="w-6 h-6 text-cyan-400 mb-2" />
                  <div className="metric-value text-cyan-400 text-3xl md:text-4xl">
                    <AnimatedCounter
                      value={unitEconomics.cacPayback}
                      suffix="-mo"
                      className="metric-value text-cyan-400 text-3xl md:text-4xl"
                    />
                  </div>
                  <span className="metric-label">CAC Payback</span>
                </div>
                <div className="glass-card flex flex-col items-center justify-center text-center flex-1">
                  <TrendingUp className="w-6 h-6 text-purple-400 mb-2" />
                  <AnimatedCounter
                    value={unitEconomics.ltvCacRatio}
                    suffix="x"
                    decimals={1}
                    className="metric-value text-purple-400"
                  />
                  <span className="metric-label">LTV / CAC</span>
                </div>
              </div>
            </div>
          </FadeInItem>

          {/* Annual Totals */}
          <FadeInItem>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4">
              {annualRevenue.map((yr, i) => (
                <div
                  key={yr.year}
                  className="glass-card text-center py-5"
                >
                  <p className="text-sm text-slate-400 uppercase tracking-wider mb-1">
                    {yr.year}
                  </p>
                  <p
                    className={`text-3xl md:text-4xl font-extrabold tracking-tight ${
                      i === 2 ? 'gradient-text' : 'text-slate-100'
                    }`}
                  >
                    {yr.label}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">Annual Revenue</p>
                </div>
              ))}
            </div>
          </FadeInItem>
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
