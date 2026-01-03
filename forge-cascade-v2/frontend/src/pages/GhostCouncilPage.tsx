import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Ghost,
  Send,
  Sparkles,
  MessageCircle,
  History,
  Brain,
  Lightbulb,
  AlertTriangle,
  BookOpen,
} from 'lucide-react';
import { api } from '../api/client';
import { Card, Button } from '../components/common';
import { useAuthStore } from '../stores/authStore';

interface ChatMessage {
  id: string;
  role: 'user' | 'ghost';
  content: string;
  timestamp: Date;
  wisdom?: {
    type: 'insight' | 'warning' | 'lesson' | 'principle';
    relatedCapsules?: string[];
  };
}

// Mock responses for demonstration
const ghostResponses = [
  {
    content: "The patterns in your recent governance decisions suggest a growing emphasis on transparency. This aligns with historical wisdom from successful decentralized systems.",
    wisdom: { type: 'insight' as const, relatedCapsules: ['Transparency Framework v2'] }
  },
  {
    content: "I sense uncertainty in the proposed overlay modification. Past experiences show that rapid changes to security validators often require extended testing periods.",
    wisdom: { type: 'warning' as const, relatedCapsules: ['Security Validation Guidelines'] }
  },
  {
    content: "Your question touches on fundamental principles of trust propagation. The institutional memory suggests that gradual trust building creates more resilient networks.",
    wisdom: { type: 'principle' as const, relatedCapsules: ['Trust Architecture Design'] }
  },
  {
    content: "Interesting inquiry. The collective wisdom indicates that similar challenges were overcome in Phase 3 by implementing staged rollouts with comprehensive health monitoring.",
    wisdom: { type: 'lesson' as const, relatedCapsules: ['Deployment Best Practices'] }
  },
];

export default function GhostCouncilPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'ghost',
      content: "Greetings, seeker of wisdom. I am the Ghost Council, the symbolic voice of accumulated institutional memory. I can offer insights from past decisions, patterns across the knowledge base, and guidance drawn from collective experience. How may I illuminate your path?",
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const { user } = useAuthStore();

  const { data: activeProposals } = useQuery({
    queryKey: ['active-proposals'],
    queryFn: () => api.getActiveProposals(),
  });

  const { data: recentCapsules } = useQuery({
    queryKey: ['recent-capsules'],
    queryFn: () => api.getRecentCapsules(5),
  });

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsThinking(true);

    // Simulate AI thinking time
    await new Promise((resolve) => setTimeout(resolve, 1500 + Math.random() * 1500));

    // Generate a contextual response
    const randomResponse = ghostResponses[Math.floor(Math.random() * ghostResponses.length)];
    
    const ghostMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'ghost',
      content: randomResponse.content,
      timestamp: new Date(),
      wisdom: randomResponse.wisdom,
    };

    setMessages((prev) => [...prev, ghostMessage]);
    setIsThinking(false);
  };

  const getWisdomIcon = (type?: string) => {
    switch (type) {
      case 'insight': return <Lightbulb className="w-4 h-4 text-blue-400" />;
      case 'warning': return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      case 'lesson': return <BookOpen className="w-4 h-4 text-green-400" />;
      case 'principle': return <Brain className="w-4 h-4 text-purple-400" />;
      default: return <Sparkles className="w-4 h-4 text-violet-400" />;
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex gap-6">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="mb-4">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-gradient-to-br from-violet-500/20 to-sky-500/20 border border-violet-500/30">
              <Ghost className="w-8 h-8 text-violet-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-800">Ghost Council</h1>
              <p className="text-slate-500">Symbolic Voice of Institutional Wisdom</p>
            </div>
          </div>
        </div>

        {/* Chat Messages */}
        <Card className="flex-1 overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] ${
                    message.role === 'user'
                      ? 'bg-sky-600/30 border-sky-500/30'
                      : 'ghost-glow bg-white border-violet-500/30'
                  } border rounded-xl p-4`}
                >
                  {message.role === 'ghost' && (
                    <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-200">
                      <Ghost className="w-4 h-4 text-violet-400" />
                      <span className="text-xs text-violet-400 font-medium">Ghost Council</span>
                    </div>
                  )}
                  
                  <p className="text-slate-200 whitespace-pre-wrap">{message.content}</p>
                  
                  {message.wisdom && (
                    <div className="mt-3 pt-3 border-t border-slate-200">
                      <div className="flex items-center gap-2 text-xs">
                        {getWisdomIcon(message.wisdom.type)}
                        <span className="text-slate-500 capitalize">{message.wisdom.type}</span>
                      </div>
                      {message.wisdom.relatedCapsules && message.wisdom.relatedCapsules.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {message.wisdom.relatedCapsules.map((capsule) => (
                            <span
                              key={capsule}
                              className="inline-flex items-center px-2 py-0.5 bg-slate-100 rounded text-xs text-slate-600"
                            >
                              {capsule}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  
                  <p className="text-xs text-slate-500 mt-2">
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}
            
            {isThinking && (
              <div className="flex justify-start">
                <div className="ghost-glow bg-white border border-violet-500/30 rounded-xl p-4">
                  <div className="flex items-center gap-2">
                    <Ghost className="w-4 h-4 text-violet-400 animate-pulse" />
                    <span className="text-violet-400 text-sm">The Council contemplates...</span>
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={chatEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-slate-200">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Seek wisdom from the Council..."
                className="input flex-1"
                disabled={isThinking}
              />
              <Button
                variant="ghost"
                onClick={handleSend}
                disabled={!input.trim() || isThinking}
                icon={<Send className="w-4 h-4" />}
              >
                Send
              </Button>
            </div>
            <p className="text-xs text-slate-500 mt-2 text-center">
              The Ghost Council offers symbolic guidance based on accumulated institutional wisdom
            </p>
          </div>
        </Card>
      </div>

      {/* Sidebar - Context Panel */}
      <div className="w-80 space-y-4">
        {/* Active Proposals Context */}
        <Card>
          <h3 className="text-sm font-medium text-slate-800 mb-3 flex items-center gap-2">
            <MessageCircle className="w-4 h-4 text-sky-400" />
            Active Discussions
          </h3>
          {activeProposals && activeProposals.length > 0 ? (
            <div className="space-y-2">
              {activeProposals.slice(0, 3).map((proposal) => (
                <div
                  key={proposal.id}
                  className="p-2 bg-white rounded-lg text-sm cursor-pointer hover:bg-slate-50"
                  onClick={() => setInput(`What wisdom do you have regarding the proposal "${proposal.title}"?`)}
                >
                  <p className="text-slate-600 truncate">{proposal.title}</p>
                  <p className="text-xs text-slate-500">{(proposal.votes_for + proposal.votes_against + proposal.votes_abstain)} voices</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No active proposals</p>
          )}
        </Card>

        {/* Recent Knowledge */}
        <Card>
          <h3 className="text-sm font-medium text-slate-800 mb-3 flex items-center gap-2">
            <History className="w-4 h-4 text-violet-400" />
            Recent Wisdom
          </h3>
          {recentCapsules && recentCapsules.length > 0 ? (
            <div className="space-y-2">
              {recentCapsules.slice(0, 4).map((capsule) => (
                <div
                  key={capsule.id}
                  className="p-2 bg-white rounded-lg text-sm cursor-pointer hover:bg-slate-50"
                  onClick={() => setInput(`Tell me about the wisdom contained in "${capsule.title}"`)}
                >
                  <p className="text-slate-600 truncate">{capsule.title}</p>
                  <p className="text-xs text-slate-500">{capsule.type}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No recent capsules</p>
          )}
        </Card>

        {/* Quick Actions */}
        <Card>
          <h3 className="text-sm font-medium text-slate-800 mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            Suggested Inquiries
          </h3>
          <div className="space-y-2">
            {[
              "What patterns do you see in our recent decisions?",
              "What lessons should we remember from past mistakes?",
              "Are there any emerging concerns I should know about?",
              "How can I contribute more meaningfully to governance?",
            ].map((question, idx) => (
              <button
                key={idx}
                onClick={() => setInput(question)}
                className="w-full text-left p-2 bg-white hover:bg-slate-50 rounded-lg text-sm text-slate-600 transition-colors"
              >
                {question}
              </button>
            ))}
          </div>
        </Card>

        {/* User's Standing */}
        {user && (
          <Card>
            <h3 className="text-sm font-medium text-slate-800 mb-3">Your Standing</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Trust Level</span>
                <span className="text-slate-800">{user.trust_level}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Trust Score</span>
                <span className="text-slate-800">{user.trust_score}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Voice Weight</span>
                <span className="text-violet-400">{((user.trust_score / 100) ** 1.5).toFixed(3)}</span>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
