import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import {
  tokenDistribution,
  revenueDistribution,
  feeStructure,
} from '../data/tokenomics';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { Flame, Coins, ArrowRight } from 'lucide-react';

const RADIAN = Math.PI / 180;

function renderDistributionLabel({
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
  const radius = innerRadius + (outerRadius - innerRadius) * 1.55;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text
      x={x}
      y={y}
      fill="#cbd5e1"
      textAnchor={x > cx ? 'start' : 'end'}
      dominantBaseline="central"
      fontSize={11}
      fontWeight={500}
    >
      {name} ({percentage}%)
    </text>
  );
}

export default function Tokenomics() {
  return (
    <SlideLayout slideKey={9} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center gap-3 md:gap-5">
        {/* Title */}
        <StaggerContainer className="text-center mb-1">
          <FadeInItem>
            <h1 className="slide-title">
              <span className="gradient-text">Tokenized Knowledge.</span>{' '}
              <span className="text-white">Deflationary Economics.</span>
            </h1>
            <p className="slide-subtitle">
              Every interaction creates value. 25% is permanently burned.
            </p>
          </FadeInItem>
        </StaggerContainer>

        {/* Top section: Token Distribution + Revenue Flow */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-5">
          {/* Token Distribution Donut */}
          <FadeInItem>
            <div className="glass-card flex flex-col items-center">
              <div className="flex items-center gap-2 mb-2">
                <Coins size={16} className="text-cyber-blue" />
                <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
                  Token Distribution (1B Supply)
                </h3>
              </div>
              <div className="h-[180px] sm:h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={tokenDistribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={85}
                    paddingAngle={3}
                    dataKey="percentage"
                    nameKey="name"
                    animationDuration={1500}
                    label={renderDistributionLabel}
                    labelLine={false}
                    stroke="none"
                  >
                    {tokenDistribution.map((entry, index) => (
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
                    formatter={(value: number, _name: string, props: { payload?: { tokens?: number } }) => [
                      `${value}% (${((props.payload?.tokens ?? 0) / 1_000_000).toFixed(0)}M tokens)`,
                      'Allocation',
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>
              </div>
            </div>
          </FadeInItem>

          {/* Revenue Distribution Flow */}
          <FadeInItem>
            <div className="glass-card">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 text-center">
                Revenue Flow
              </h3>
              <StaggerContainer className="flex flex-col gap-3" delay={0.4}>
                {revenueDistribution.map((item) => (
                  <FadeInItem key={item.name}>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2 w-full">
                        <ArrowRight size={14} style={{ color: item.color }} className="shrink-0" />
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-slate-200">{item.name}</span>
                            <span className="text-sm font-bold" style={{ color: item.color }}>
                              {item.percentage}%
                            </span>
                          </div>
                          <div className="w-full bg-white/5 rounded-full h-2">
                            <div
                              className="h-2 rounded-full transition-all duration-1000"
                              style={{
                                width: `${item.percentage * (100 / 30)}%`,
                                backgroundColor: item.color,
                              }}
                            />
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">{item.description}</p>
                        </div>
                      </div>
                    </div>
                  </FadeInItem>
                ))}
              </StaggerContainer>
            </div>
          </FadeInItem>
        </div>

        {/* Burn callout */}
        <FadeInItem>
          <div className="glass-card border-red-500/30 bg-red-500/5 flex items-center justify-center gap-3 py-4">
            <Flame size={24} className="text-red-400" />
            <p className="text-lg font-bold text-white">
              25% of <span className="text-red-400">ALL</span> revenue permanently burned
            </p>
            <span className="text-slate-400 text-sm">&mdash; Deflationary by design</span>
            <Flame size={24} className="text-red-400" />
          </div>
        </FadeInItem>

        {/* Fee structure */}
        <FadeInItem>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {feeStructure.map((fee) => (
              <div
                key={fee.type}
                className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-center"
              >
                <p className="text-xs text-slate-400">{fee.type}</p>
                <p className="text-sm font-semibold text-white">{fee.rate}</p>
              </div>
            ))}
          </div>
        </FadeInItem>
      </div>
    </SlideLayout>
  );
}
