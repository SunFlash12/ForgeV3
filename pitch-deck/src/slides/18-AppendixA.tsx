import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { motion } from 'framer-motion';
import {
  Layers,
  Shield,
  Lock,
  Key,
  Fingerprint,
  ArrowRight,
  Workflow,
  Network,
  Handshake,
  RefreshCw,
  GitMerge,
} from 'lucide-react';

const pipelinePhases = [
  { name: 'Ingestion', time: '~50ms', desc: 'Schema validation, normalization, deduplication', color: '#00d4ff' },
  { name: 'Analysis', time: '~100ms', desc: 'ML classification, embedding generation, entity extraction', color: '#3b82f6' },
  { name: 'Validation', time: '~50ms', desc: 'Trust scoring, security checks, compliance gates', color: '#6366f1' },
  { name: 'Consensus', time: '~300ms', desc: 'Ghost Council vote, constitutional compliance, quorum', color: '#7c3aed' },
  { name: 'Execution', time: '~200ms', desc: 'State mutation, graph updates, overlay triggers', color: '#a855f7' },
  { name: 'Propagation', time: '~100ms', desc: 'Cascade effects, event emission, subscriber notify', color: '#ec4899' },
  { name: 'Settlement', time: '~50ms', desc: 'Audit log, Merkle proof, Isnad chain append', color: '#f59e0b' },
];

const securityLayers = [
  { name: 'Authentication', detail: 'JWT + MFA, Ed25519 key pairs, session management', icon: Key, color: '#00d4ff' },
  { name: 'Authorization', detail: 'RBAC with 5 roles, resource-level ACLs, API scoping', icon: Lock, color: '#7c3aed' },
  { name: 'Trust System', detail: '4 trust tiers (0-100 score), behavioral analysis, anomaly detection', icon: Fingerprint, color: '#10b981' },
  { name: 'Data Integrity', detail: 'SHA-256 hashing, Merkle trees, Isnad lineage chains, tamper detection', icon: Shield, color: '#f59e0b' },
];

const federationSteps = [
  { step: 'Handshake', desc: 'Ed25519 key exchange, trust certificate validation, capability negotiation', icon: Handshake, color: '#00d4ff' },
  { step: 'Sync', desc: 'Differential sync with vector clocks, conflict-free replicated data types (CRDTs)', icon: RefreshCw, color: '#7c3aed' },
  { step: 'Resolution', desc: 'Last-writer-wins with trust weighting, manual override for high-value conflicts', icon: GitMerge, color: '#10b981' },
];

export default function AppendixA({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="dark">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-5">
          {/* Title */}
          <FadeInItem>
            <div className="flex items-center gap-3 mb-1">
              <Layers className="w-6 h-6 text-cyan-400" />
              <h1 className="text-xl md:text-2xl lg:text-3xl font-bold text-slate-100">
                Appendix A:{' '}
                <span className="gradient-text">
                  Technical Architecture Deep Dive
                </span>
              </h1>
            </div>
          </FadeInItem>

          {/* 7-Phase Pipeline */}
          <FadeInItem>
            <div className="glass-card py-4 px-5">
              <div className="flex items-center gap-2 mb-3">
                <Workflow className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  7-Phase Processing Pipeline &mdash; Total Latency: 1.2s
                </h3>
              </div>
              <div className="hidden lg:flex items-center gap-1">
                {pipelinePhases.map((phase, i) => (
                  <div key={i} className="flex items-center flex-1 min-w-0">
                    <div className="flex-1 min-w-0">
                      <div
                        className="rounded-lg px-2.5 py-2 border border-white/5"
                        style={{
                          backgroundColor: `${phase.color}10`,
                          borderColor: `${phase.color}25`,
                        }}
                      >
                        <p
                          className="text-[10px] font-bold truncate"
                          style={{ color: phase.color }}
                        >
                          {phase.name}
                        </p>
                        <p className="text-[9px] text-slate-500 font-mono">
                          {phase.time}
                        </p>
                        <p className="text-[9px] text-slate-400 leading-tight mt-0.5 line-clamp-2">
                          {phase.desc}
                        </p>
                      </div>
                    </div>
                    {i < pipelinePhases.length - 1 && (
                      <ArrowRight className="w-3 h-3 text-slate-600 shrink-0 mx-0.5" />
                    )}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 lg:hidden">
                {pipelinePhases.map((phase, i) => (
                  <div
                    key={i}
                    className="rounded-lg px-2.5 py-2 border border-white/5"
                    style={{
                      backgroundColor: `${phase.color}10`,
                      borderColor: `${phase.color}25`,
                    }}
                  >
                    <p
                      className="text-[10px] font-bold truncate"
                      style={{ color: phase.color }}
                    >
                      {phase.name}
                    </p>
                    <p className="text-[9px] text-slate-500 font-mono">
                      {phase.time}
                    </p>
                    <p className="text-[9px] text-slate-400 leading-tight mt-0.5 line-clamp-2">
                      {phase.desc}
                    </p>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-slate-500 mt-2">
                Each phase applies 10 overlay processors (compliance, security, audit, trust, governance, analytics, caching, federation, blockchain, ML) in parallel
              </p>
            </div>
          </FadeInItem>

          {/* Security Architecture + Federation Protocol side by side */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-3 md:gap-4">
              {/* Security Layers */}
              <div className="glass-card flex-1 py-4 px-5">
                <div className="flex items-center gap-2 mb-3">
                  <Shield className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Security Architecture (4 Layers)
                  </h3>
                </div>
                <div className="space-y-2.5">
                  {securityLayers.map((layer, i) => {
                    const Icon = layer.icon;
                    return (
                      <div key={i} className="flex items-start gap-3">
                        <div className="relative mt-0.5">
                          <div
                            className="w-7 h-7 rounded-md flex items-center justify-center"
                            style={{ backgroundColor: `${layer.color}15` }}
                          >
                            <Icon
                              className="w-3.5 h-3.5"
                              style={{ color: layer.color }}
                            />
                          </div>
                          {/* Connecting line */}
                          {i < securityLayers.length - 1 && (
                            <div className="absolute top-7 left-1/2 -translate-x-1/2 w-px h-2.5 bg-white/10" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p
                            className="text-xs font-bold"
                            style={{ color: layer.color }}
                          >
                            {layer.name}
                          </p>
                          <p className="text-[10px] text-slate-400 leading-relaxed">
                            {layer.detail}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Federation Protocol */}
              <div className="glass-card flex-1 py-4 px-5">
                <div className="flex items-center gap-2 mb-3">
                  <Network className="w-4 h-4 text-purple-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Federation Protocol
                  </h3>
                </div>
                <div className="space-y-4">
                  {federationSteps.map((step, i) => {
                    const Icon = step.icon;
                    return (
                      <motion.div
                        key={i}
                        className="flex items-start gap-3"
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.6 + i * 0.15 }}
                      >
                        <div
                          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                          style={{ backgroundColor: `${step.color}15` }}
                        >
                          <Icon
                            className="w-4 h-4"
                            style={{ color: step.color }}
                          />
                        </div>
                        <div className="flex-1">
                          <p
                            className="text-xs font-bold"
                            style={{ color: step.color }}
                          >
                            {i + 1}. {step.step}
                          </p>
                          <p className="text-[10px] text-slate-400 leading-relaxed mt-0.5">
                            {step.desc}
                          </p>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>

                {/* Additional detail */}
                <div className="mt-4 pt-3 border-t border-white/5">
                  <p className="text-[10px] text-slate-500 leading-relaxed">
                    <span className="text-slate-400 font-medium">Overlay System:</span>{' '}
                    10 processor overlays wrap every pipeline phase. Each overlay
                    implements pre-process, post-process, and error hooks. Overlays
                    include: ComplianceOverlay, SecurityOverlay, AuditOverlay,
                    TrustOverlay, GovernanceOverlay, AnalyticsOverlay, CacheOverlay,
                    FederationOverlay, BlockchainOverlay, MLOverlay.
                  </p>
                </div>
              </div>
            </div>
          </FadeInItem>
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
