import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import {
  tokenDistribution,
  feeStructure,
  bondingCurve,
  graduationTiers,
  acpFeatures,
} from '../data/tokenomics';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import { Coins, TrendingUp, Layers, Zap } from 'lucide-react';

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
  const radius = innerRadius + (outerRadius - innerRadius) * 1.6;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text
      x={x}
      y={y}
      fill="#cbd5e1"
      textAnchor={x > cx ? 'start' : 'end'}
      dominantBaseline="central"
      fontSize={9}
      fontWeight={500}
    >
      {name} ({percentage}%)
    </text>
  );
}

const BondingTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-surface-900/95 border border-white/10 rounded-lg px-3 py-2 backdrop-blur-md">
        <p className="text-slate-400 text-[10px]">
          Supply: {Number(label).toLocaleString()}
        </p>
        <p className="text-cyan-400 text-xs font-bold">
          Price: {payload[0].value.toFixed(4)} VIRTUAL
        </p>
      </div>
    );
  }
  return null;
};

export default function AppendixTokenomics({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="dark">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-3">
          {/* Title */}
          <FadeInItem>
            <div className="flex items-center gap-3 mb-1">
              <Coins className="w-6 h-6 text-amber-400" />
              <h1 className="text-xl md:text-2xl lg:text-3xl font-bold text-slate-100">
                Appendix C:{' '}
                <span className="gradient-text">Tokenomics &amp; Virtuals Protocol</span>
              </h1>
            </div>
          </FadeInItem>

          {/* Main content: Left (Donut + Fees) | Right (Bonding Curve + Tiers) */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-3 md:gap-4">
              {/* Left column: Token distribution donut + fee structure */}
              <div className="flex flex-col gap-3 flex-1">
                {/* Donut chart */}
                <div className="glass-card py-3 px-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Coins size={14} className="text-cyber-blue" />
                    <h3 className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                      Token Distribution (1B Supply)
                    </h3>
                  </div>
                  <div className="h-[150px] sm:h-[170px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={tokenDistribution}
                          cx="50%"
                          cy="50%"
                          innerRadius={40}
                          outerRadius={65}
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
                            fontSize: '11px',
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

                {/* Fee structure compact grid */}
                <div className="glass-card py-3 px-4">
                  <h3 className="text-[10px] font-bold text-slate-300 uppercase tracking-wider mb-2">
                    Fee Structure
                  </h3>
                  <div className="grid grid-cols-2 gap-1.5">
                    {feeStructure.map((fee) => (
                      <div
                        key={fee.type}
                        className="bg-white/5 rounded-lg px-2.5 py-1.5"
                      >
                        <p className="text-[9px] text-slate-400">{fee.type}</p>
                        <p className="text-[10px] font-semibold text-white">{fee.rate}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right column: Bonding curve + graduation tiers */}
              <div className="flex flex-col gap-3 flex-1">
                {/* Bonding curve chart */}
                <div className="glass-card py-3 px-4">
                  <div className="flex items-center gap-2 mb-1">
                    <TrendingUp className="w-4 h-4 text-cyan-400" />
                    <h3 className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                      Bonding Curve
                    </h3>
                  </div>
                  <p className="text-[9px] text-slate-500 mb-2 font-mono">
                    {bondingCurve.formula}
                  </p>
                  <div className="w-full h-[120px] sm:h-[150px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={bondingCurve.dataPoints}
                        margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="rgba(255,255,255,0.05)"
                        />
                        <XAxis
                          dataKey="supply"
                          tick={{ fill: '#94a3b8', fontSize: 9 }}
                          axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                          tickLine={false}
                          tickFormatter={(v) =>
                            v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v
                          }
                        />
                        <YAxis
                          dataKey="price"
                          tick={{ fill: '#94a3b8', fontSize: 9 }}
                          axisLine={false}
                          tickLine={false}
                          tickFormatter={(v) => v.toFixed(3)}
                        />
                        <Tooltip content={<BondingTooltip />} />
                        <Line
                          type="monotone"
                          dataKey="price"
                          stroke="#00d4ff"
                          strokeWidth={2}
                          dot={false}
                          activeDot={{
                            r: 3,
                            fill: '#00d4ff',
                            stroke: '#0a0a1a',
                            strokeWidth: 2,
                          }}
                          animationDuration={1500}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Graduation tiers */}
                <div className="glass-card py-3 px-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Layers className="w-4 h-4 text-purple-400" />
                    <h3 className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                      Graduation Tiers
                    </h3>
                  </div>
                  <div className="space-y-2">
                    {graduationTiers.map((tier, i) => (
                      <div
                        key={i}
                        className="rounded-lg px-3 py-2 border border-white/5"
                        style={{ backgroundColor: `${tier.color}08` }}
                      >
                        <div className="flex items-baseline justify-between">
                          <span
                            className="text-[10px] font-bold"
                            style={{ color: tier.color }}
                          >
                            {tier.tier}
                          </span>
                          <span className="text-[9px] text-slate-400 font-mono">
                            {tier.threshold.toLocaleString()} VIRTUAL
                          </span>
                        </div>
                        <p className="text-[9px] text-slate-400">
                          {tier.benefit}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </FadeInItem>

          {/* Bottom: ACP features */}
          <FadeInItem>
            <div className="glass-card py-3 px-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-amber-400" />
                <h3 className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                  Agent Commerce Protocol (ACP)
                </h3>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {acpFeatures.map((feature, i) => (
                  <div key={i} className="bg-white/5 rounded-lg px-2.5 py-2">
                    <p className="text-[10px] text-cyan-400 font-semibold mb-0.5">
                      {feature.name}
                    </p>
                    <p className="text-[9px] text-slate-500 leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </FadeInItem>
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
