import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { AnimatedCounter } from '../components/AnimatedCounter';
import {
  revenueProjections,
  pricingTiers,
  unitEconomics,
  technicalAssetValue,
} from '../data/financials';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Line,
  ComposedChart,
  Legend,
} from 'recharts';
import { Calculator, Server, DollarSign, Database } from 'lucide-react';

const formatRevenue = (value: number) => {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value}`;
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-surface-900/95 border border-white/10 rounded-lg px-4 py-3 backdrop-blur-md">
        <p className="text-slate-300 text-xs font-medium mb-1">{label}</p>
        {payload.map((p: any, i: number) => (
          <p key={i} style={{ color: p.color }} className="text-xs font-semibold">
            {p.name === 'revenue'
              ? `Revenue: ${formatRevenue(p.value)}`
              : `Customers: ${p.value}`}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const techAssets = [
  { label: 'Lines of Code', value: '50,000+', sublabel: 'Production-ready' },
  { label: 'Backend Modules', value: '93', sublabel: 'Microservices arch' },
  { label: 'API Endpoints', value: '25', sublabel: '3 API services' },
  { label: 'Compliance Controls', value: '400+', sublabel: '25+ jurisdictions' },
  { label: 'Security Audits', value: '4', sublabel: 'All passed' },
  { label: 'Test Cases', value: '195+', sublabel: 'Comprehensive suite' },
  { label: 'Frontend Pages', value: '23', sublabel: '2 applications' },
  { label: 'Smart Contracts', value: '3', sublabel: 'Deployed on-chain' },
];

export default function AppendixC({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="dark">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-4">
          {/* Title */}
          <FadeInItem>
            <div className="flex items-center gap-3 mb-1">
              <Calculator className="w-6 h-6 text-emerald-400" />
              <h1 className="text-xl md:text-2xl lg:text-3xl font-bold text-slate-100">
                Appendix C:{' '}
                <span className="gradient-text">Extended Financial Model</span>
              </h1>
            </div>
          </FadeInItem>

          {/* Top Row: Revenue Chart + Pricing Tiers */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-3 md:gap-4">
              {/* Quarterly Revenue Bar Chart with Customer Line Overlay */}
              <div className="glass-card flex-1 py-4 px-5">
                <div className="flex items-center gap-2 mb-3">
                  <DollarSign className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Quarterly Revenue &amp; Customer Growth
                  </h3>
                </div>
                <div className="w-full h-[160px] sm:h-[200px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={revenueProjections}
                      margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="rgba(255,255,255,0.05)"
                      />
                      <XAxis
                        dataKey="label"
                        tick={{ fill: '#94a3b8', fontSize: 10 }}
                        axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                        tickLine={false}
                      />
                      <YAxis
                        yAxisId="revenue"
                        tick={{ fill: '#94a3b8', fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={formatRevenue}
                      />
                      <YAxis
                        yAxisId="customers"
                        orientation="right"
                        tick={{ fill: '#94a3b8', fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend
                        wrapperStyle={{ fontSize: '10px', color: '#94a3b8' }}
                      />
                      <Bar
                        yAxisId="revenue"
                        dataKey="revenue"
                        name="revenue"
                        fill="#00d4ff"
                        radius={[3, 3, 0, 0]}
                        opacity={0.7}
                        animationDuration={1500}
                      />
                      <Line
                        yAxisId="customers"
                        type="monotone"
                        dataKey="customers"
                        name="customers"
                        stroke="#10b981"
                        strokeWidth={2}
                        dot={false}
                        animationDuration={1500}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Pricing Tiers Table */}
              <div className="glass-card w-full md:w-[340px] shrink-0 py-4 px-5">
                <div className="flex items-center gap-2 mb-3">
                  <Server className="w-4 h-4 text-purple-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Pricing Tiers
                  </h3>
                </div>
                <div className="overflow-hidden rounded-lg border border-white/5">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="bg-white/5">
                        <th className="px-3 py-1.5 text-[9px] font-bold text-slate-400 uppercase tracking-wider">
                          Tier
                        </th>
                        <th className="px-3 py-1.5 text-[9px] font-bold text-slate-400 uppercase tracking-wider">
                          Price/mo
                        </th>
                        <th className="px-3 py-1.5 text-[9px] font-bold text-slate-400 uppercase tracking-wider">
                          Queries
                        </th>
                        <th className="px-3 py-1.5 text-[9px] font-bold text-slate-400 uppercase tracking-wider">
                          Target
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {pricingTiers.map((tier, i) => (
                        <tr
                          key={i}
                          className="border-t border-white/5 hover:bg-white/[0.02] transition-colors"
                        >
                          <td className="px-3 py-1.5 text-[10px] text-cyan-400 font-semibold">
                            {tier.tier}
                          </td>
                          <td className="px-3 py-1.5 text-[10px] text-slate-200 font-mono">
                            ${tier.price.toLocaleString()}
                          </td>
                          <td className="px-3 py-1.5 text-[10px] text-slate-300">
                            {tier.queries}
                          </td>
                          <td className="px-3 py-1.5 text-[10px] text-slate-400">
                            {tier.target}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </FadeInItem>

          {/* Bottom Row: Unit Economics + Technical Asset Value */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-3 md:gap-4">
              {/* Unit Economics */}
              <div className="glass-card py-4 px-5 w-full md:w-[280px] shrink-0">
                <div className="flex items-center gap-2 mb-3">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Unit Economics
                  </h3>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-baseline border-b border-white/5 pb-2">
                    <span className="text-[10px] text-slate-400">
                      Gross Margin
                    </span>
                    <span className="text-sm text-emerald-400 font-bold">
                      {unitEconomics.grossMargin}%
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline border-b border-white/5 pb-2">
                    <span className="text-[10px] text-slate-400">
                      Avg Contract Value
                    </span>
                    <span className="text-sm text-slate-200 font-bold">
                      ${unitEconomics.avgContractValue.toLocaleString()}/yr
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline border-b border-white/5 pb-2">
                    <span className="text-[10px] text-slate-400">
                      CAC Payback
                    </span>
                    <span className="text-sm text-cyan-400 font-bold">
                      {unitEconomics.cacPayback} months
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline border-b border-white/5 pb-2">
                    <span className="text-[10px] text-slate-400">
                      Customer LTV
                    </span>
                    <span className="text-sm text-slate-200 font-bold">
                      ${unitEconomics.ltv.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline border-b border-white/5 pb-2">
                    <span className="text-[10px] text-slate-400">
                      LTV / CAC Ratio
                    </span>
                    <span className="text-sm text-purple-400 font-bold">
                      {unitEconomics.ltvCacRatio}x
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline border-b border-white/5 pb-2">
                    <span className="text-[10px] text-slate-400">
                      Cost per Query
                    </span>
                    <span className="text-sm text-slate-200 font-bold font-mono">
                      ${unitEconomics.costPerQuery}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline">
                    <span className="text-[10px] text-slate-400">
                      Inference Margin
                    </span>
                    <span className="text-sm text-emerald-400 font-bold">
                      {unitEconomics.inferenceMargin}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Technical Asset Value */}
              <div className="glass-card flex-1 py-4 px-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-amber-400" />
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                      Technical Asset Value
                    </h3>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-xs text-slate-400">
                      Replacement Cost:
                    </span>
                    <span className="text-base font-extrabold gradient-text">
                      $4.5M
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 md:gap-2.5">
                  {techAssets.map((asset, i) => (
                    <div
                      key={i}
                      className="rounded-lg px-3 py-2.5 bg-white/[0.03] border border-white/5 text-center"
                    >
                      <p className="text-lg font-extrabold text-cyan-400 tracking-tight">
                        {asset.value}
                      </p>
                      <p className="text-[10px] text-slate-300 font-medium mt-0.5">
                        {asset.label}
                      </p>
                      <p className="text-[9px] text-slate-500">{asset.sublabel}</p>
                    </div>
                  ))}
                </div>

                {/* Infrastructure cost note */}
                <div className="mt-3 pt-3 border-t border-white/5">
                  <div className="flex gap-4">
                    <div className="flex-1">
                      <p className="text-[10px] text-slate-400 font-semibold mb-1">
                        Engineering Estimate
                      </p>
                      <p className="text-[9px] text-slate-500 leading-relaxed">
                        {technicalAssetValue.engineeringMonths} engineer-months
                        (15 senior engineers x 12 months). Current codebase represents
                        significant pre-seed technical advantage over any potential
                        competitor starting from scratch.
                      </p>
                    </div>
                    <div className="flex-1">
                      <p className="text-[10px] text-slate-400 font-semibold mb-1">
                        Infrastructure Costs
                      </p>
                      <p className="text-[9px] text-slate-500 leading-relaxed">
                        Estimated $8-12K/month cloud infrastructure at scale (Neo4j
                        Aura, Redis Cloud, 3 API services, monitoring stack).
                        Unit cost decreases 40% at 500+ customers due to shared
                        inference and caching layers.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </FadeInItem>
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
