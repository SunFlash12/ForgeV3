import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { microservices, techStack } from '../data/features';
import { motion } from 'framer-motion';
import {
  Server,
  Database,
  HardDrive,
  ArrowDown,
  Code2,
  Monitor,
  Cloud,
  Link,
  Lock,
} from 'lucide-react';

const stackIcons: Record<string, typeof Code2> = {
  backend: Code2,
  frontend: Monitor,
  infrastructure: Cloud,
  blockchain: Link,
  security: Lock,
};

const stackColors: Record<string, string> = {
  backend: '#00d4ff',
  frontend: '#7c3aed',
  infrastructure: '#10b981',
  blockchain: '#f59e0b',
  security: '#ec4899',
};

const stackLabels: Record<string, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  infrastructure: 'Infrastructure',
  blockchain: 'Blockchain',
  security: 'Security',
};

export default function Architecture() {
  return (
    <SlideLayout slideKey={13} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center gap-5">
        {/* Title */}
        <StaggerContainer className="text-center mb-1">
          <FadeInItem>
            <h1 className="slide-title">
              <span className="gradient-text">3 Microservices.</span>{' '}
              <span className="text-white">1 Unified Graph.</span>
            </h1>
            <p className="slide-subtitle">
              Production-grade architecture with 50,000+ lines of battle-tested code
            </p>
          </FadeInItem>
        </StaggerContainer>

        {/* Architecture Diagram */}
        <FadeInItem>
          <div className="glass-card">
            <div className="flex flex-col items-center gap-4">
              {/* 3 Microservices */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 md:gap-4 w-full">
                {microservices.map((svc, idx) => (
                  <motion.div
                    key={svc.name}
                    className="bg-white/5 border border-white/10 rounded-xl p-4 text-center"
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 + idx * 0.15 }}
                  >
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center mx-auto mb-2"
                      style={{ backgroundColor: `${svc.color}20` }}
                    >
                      <Server size={20} style={{ color: svc.color }} />
                    </div>
                    <h4 className="text-sm font-bold text-white">{svc.name}</h4>
                    <p className="text-[10px] text-slate-500 mt-0.5">Port {svc.port}</p>
                    <p className="text-xs text-slate-400 mt-1">{svc.description}</p>
                  </motion.div>
                ))}
              </div>

              {/* Connection arrows */}
              <motion.div
                className="flex items-center gap-3 text-slate-500"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.9 }}
              >
                <ArrowDown size={18} />
                <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">
                  Shared Data Layer
                </span>
                <ArrowDown size={18} />
              </motion.div>

              {/* Data stores */}
              <div className="grid grid-cols-2 gap-2 md:gap-4 w-full max-w-md">
                <motion.div
                  className="bg-white/5 border border-white/10 rounded-xl p-3 text-center"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 1.1 }}
                >
                  <Database size={22} className="text-cyan-400 mx-auto mb-1" />
                  <h4 className="text-sm font-bold text-white">Neo4j 5.x</h4>
                  <p className="text-[10px] text-slate-400">Knowledge Graph</p>
                </motion.div>
                <motion.div
                  className="bg-white/5 border border-white/10 rounded-xl p-3 text-center"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 1.2 }}
                >
                  <HardDrive size={22} className="text-red-400 mx-auto mb-1" />
                  <h4 className="text-sm font-bold text-white">Redis 7.x</h4>
                  <p className="text-[10px] text-slate-400">Cache & Pub/Sub</p>
                </motion.div>
              </div>
            </div>
          </div>
        </FadeInItem>

        {/* Tech Stack Grid */}
        <FadeInItem>
          <div className="glass-card">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 text-center">
              Technology Stack
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2 md:gap-3">
              {(Object.keys(techStack) as Array<keyof typeof techStack>).map((category) => {
                const Icon = stackIcons[category];
                const color = stackColors[category];
                return (
                  <div key={category} className="bg-white/5 rounded-xl p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Icon size={14} style={{ color }} />
                      <h4
                        className="text-xs font-bold uppercase tracking-wider"
                        style={{ color }}
                      >
                        {stackLabels[category]}
                      </h4>
                    </div>
                    <ul className="space-y-1">
                      {techStack[category].map((tech) => (
                        <li key={tech.name} className="text-xs text-slate-300">
                          {tech.name}
                          <span className="text-slate-600 text-[10px] ml-1">
                            {tech.category}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          </div>
        </FadeInItem>
      </div>
    </SlideLayout>
  );
}
