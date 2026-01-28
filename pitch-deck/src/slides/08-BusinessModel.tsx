import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { AnimatedCounter } from '../components/AnimatedCounter';
import { revenueStreams, pricingTiers, unitEconomics } from '../data/financials';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { DollarSign, TrendingUp, BarChart3 } from 'lucide-react';

const RADIAN = Math.PI / 180;

function renderCustomLabel({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percentage,
  name,
}: {
  cx: number;
  cy: number;
  midAngle: number;
  innerRadius: number;
  outerRadius: number;
  percentage: number;
  name: string;
}) {
  const radius = innerRadius + (outerRadius - innerRadius) * 1.4;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text
      x={x}
      y={y}
      fill="#cbd5e1"
      textAnchor={x > cx ? 'start' : 'end'}
      dominantBaseline="central"
      fontSize={12}
      fontWeight={500}
    >
      {name} ({percentage}%)
    </text>
  );
}

const keyMetrics = [
  {
    icon: TrendingUp,
    value: unitEconomics.grossMargin,
    suffix: '%',
    label: 'Gross Margin',
    color: '#10b981',
  },
  {
    icon: DollarSign,
    value: unitEconomics.avgContractValue,
    prefix: '$',
    label: 'Avg Contract',
    color: '#00d4ff',
  },
  {
    icon: BarChart3,
    value: unitEconomics.ltvCacRatio,
    suffix: 'x',
    label: 'LTV / CAC',
    color: '#7c3aed',
  },
];

export default function BusinessModel({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center gap-6">
        {/* Title */}
        <StaggerContainer className="text-center mb-2">
          <FadeInItem>
            <h1 className="slide-title">
              <span className="gradient-text">5 Revenue Streams.</span>{' '}
              <span className="text-white">85% Gross Margin.</span>
            </h1>
            <p className="slide-subtitle">Diversified monetization with SaaS-grade economics</p>
          </FadeInItem>
        </StaggerContainer>

        {/* Main content: Chart + Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
          {/* Left: Donut chart */}
          <FadeInItem>
            <div className="glass-card flex flex-col items-center">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Revenue Mix
              </h3>
              <div className="h-[200px] sm:h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={revenueStreams}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={3}
                    dataKey="percentage"
                    nameKey="name"
                    animationDuration={1500}
                    label={renderCustomLabel}
                    labelLine={false}
                    stroke="none"
                  >
                    {revenueStreams.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(15, 15, 35, 0.95)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '12px',
                      color: '#e2e8f0',
                    }}
                    formatter={(value: number) => [`${value}%`, 'Share']}
                  />
                </PieChart>
              </ResponsiveContainer>
              </div>
            </div>
          </FadeInItem>

          {/* Right: Key metrics */}
          <StaggerContainer className="flex flex-col gap-4" delay={0.3}>
            {keyMetrics.map((metric) => (
              <FadeInItem key={metric.label}>
                <div className="glass-card flex items-center gap-5">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                    style={{ backgroundColor: `${metric.color}20` }}
                  >
                    <metric.icon size={24} style={{ color: metric.color }} />
                  </div>
                  <div>
                    <AnimatedCounter
                      value={metric.value}
                      prefix={metric.prefix}
                      suffix={metric.suffix}
                      className="metric-value text-3xl md:text-4xl"
                      decimals={metric.suffix === 'x' ? 1 : 0}
                    />
                    <p className="metric-label">{metric.label}</p>
                  </div>
                </div>
              </FadeInItem>
            ))}
          </StaggerContainer>
        </div>

        {/* Bottom: Pricing tiers */}
        <FadeInItem>
          <div className="glass-card mt-2">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 text-center">
              Pricing Tiers
            </h3>
            <div className="flex flex-wrap justify-center gap-2 md:gap-3">
              {pricingTiers.map((tier, idx) => (
                <div key={tier.tier} className="flex items-center gap-2">
                  <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-center min-w-[100px] sm:min-w-[120px]">
                    <p className="text-xs text-slate-400 mb-0.5">{tier.tier}</p>
                    <p className="text-lg font-bold text-white">
                      ${tier.price.toLocaleString()}
                      <span className="text-xs text-slate-400 font-normal">/mo</span>
                    </p>
                    <p className="text-[10px] text-slate-500">{tier.target}</p>
                  </div>
                  {idx < pricingTiers.length - 1 && (
                    <span className="text-slate-600 text-lg">&rarr;</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </FadeInItem>
      </div>
    </SlideLayout>
  );
}
