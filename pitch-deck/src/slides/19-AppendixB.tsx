import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import {
  bondingCurve,
  graduationTiers,
  acpFeatures,
  feeStructure,
} from '../data/tokenomics';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { Coins, TrendingUp, Layers, Receipt } from 'lucide-react';

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-surface-900/95 border border-white/10 rounded-lg px-4 py-3 backdrop-blur-md">
        <p className="text-slate-400 text-xs">
          Supply: {Number(label).toLocaleString()}
        </p>
        <p className="text-cyan-400 text-sm font-bold">
          Price: {payload[0].value.toFixed(4)} VIRTUAL
        </p>
      </div>
    );
  }
  return null;
};

export default function AppendixB({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="dark">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-4">
          {/* Title */}
          <FadeInItem>
            <div className="flex items-center gap-3 mb-1">
              <Coins className="w-6 h-6 text-amber-400" />
              <h1 className="text-xl md:text-2xl lg:text-3xl font-bold text-slate-100">
                Appendix B:{' '}
                <span className="gradient-text">Detailed Tokenomics</span>
              </h1>
            </div>
          </FadeInItem>

          {/* Top Row: Bonding Curve Chart + Graduation Tiers */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-3 md:gap-4">
              {/* Bonding Curve Chart */}
              <div className="glass-card flex-1 py-4 px-5">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Bonding Curve
                  </h3>
                </div>
                <p className="text-[10px] text-slate-500 mb-3 font-mono">
                  {bondingCurve.formula}
                </p>
                <div className="w-full h-[140px] sm:h-[180px]">
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
                        tick={{ fill: '#94a3b8', fontSize: 10 }}
                        axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                        tickLine={false}
                        tickFormatter={(v) =>
                          v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v
                        }
                        label={{
                          value: 'Supply',
                          position: 'insideBottom',
                          offset: -2,
                          fill: '#64748b',
                          fontSize: 10,
                        }}
                      />
                      <YAxis
                        dataKey="price"
                        tick={{ fill: '#94a3b8', fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => v.toFixed(3)}
                        label={{
                          value: 'Price (VIRTUAL)',
                          angle: -90,
                          position: 'insideLeft',
                          offset: 0,
                          fill: '#64748b',
                          fontSize: 10,
                        }}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Line
                        type="monotone"
                        dataKey="price"
                        stroke="#00d4ff"
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{
                          r: 4,
                          fill: '#00d4ff',
                          stroke: '#0a0a1a',
                          strokeWidth: 2,
                        }}
                        animationDuration={1500}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-[10px] text-slate-500 mt-2">
                  {bondingCurve.description}
                </p>
              </div>

              {/* Graduation Tiers */}
              <div className="glass-card w-full md:w-[300px] shrink-0 py-4 px-5">
                <div className="flex items-center gap-2 mb-4">
                  <Layers className="w-4 h-4 text-purple-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Graduation Tiers
                  </h3>
                </div>
                <div className="space-y-3">
                  {graduationTiers.map((tier, i) => (
                    <div
                      key={i}
                      className="rounded-lg px-3 py-2.5 border border-white/5"
                      style={{ backgroundColor: `${tier.color}08` }}
                    >
                      <div className="flex items-baseline justify-between mb-1">
                        <span
                          className="text-xs font-bold"
                          style={{ color: tier.color }}
                        >
                          {tier.tier}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {tier.threshold.toLocaleString()} VIRTUAL
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400">
                        {tier.benefit}
                      </p>
                    </div>
                  ))}
                </div>

                {/* ACP Features */}
                <div className="mt-4 pt-3 border-t border-white/5">
                  <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                    Agent Commerce Protocol
                  </h4>
                  <div className="space-y-2">
                    {acpFeatures.map((feature, i) => (
                      <div key={i}>
                        <p className="text-[10px] text-cyan-400 font-semibold">
                          {feature.name}
                        </p>
                        <p className="text-[9px] text-slate-500 leading-relaxed">
                          {feature.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </FadeInItem>

          {/* Fee Structure Table */}
          <FadeInItem>
            <div className="glass-card py-4 px-5">
              <div className="flex items-center gap-2 mb-3">
                <Receipt className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Complete Fee Structure
                </h3>
              </div>
              <div className="overflow-hidden rounded-lg border border-white/5">
                <table className="w-full text-left">
                  <thead>
                    <tr className="bg-white/5">
                      <th className="px-4 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        Fee Type
                      </th>
                      <th className="px-4 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        Rate
                      </th>
                      <th className="px-4 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        Description
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {feeStructure.map((fee, i) => (
                      <tr
                        key={i}
                        className="border-t border-white/5 hover:bg-white/[0.02] transition-colors"
                      >
                        <td className="px-4 py-2 text-xs sm:text-sm text-cyan-400 font-medium">
                          {fee.type}
                        </td>
                        <td className="px-4 py-2 text-xs sm:text-sm text-slate-200 font-mono">
                          {fee.rate}
                        </td>
                        <td className="px-4 py-2 text-xs sm:text-sm text-slate-400">
                          {fee.description}
                        </td>
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
