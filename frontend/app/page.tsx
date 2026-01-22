'use client';

import { motion } from 'framer-motion';
import { 
  Database, 
  Cpu, 
  BarChart3, 
  Network, 
  GitMerge, 
  Calculator, 
  Zap, 
  Activity,
  Layers,
  ArrowRight
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } }
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
};

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground overflow-hidden selection:bg-purple-500/30">
      
      <nav className="fixed top-0 w-full z-50 border-b border-white/5 bg-background/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="text-sm font-medium tracking-widest uppercase text-white/80">FinDistill <span className="text-purple-500">v27.0</span></div>
          <div className="flex gap-6 text-sm text-gray-400">
            <a href="#architecture" className="hover:text-white transition-colors">Architecture</a>
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="https://github.com/project" className="hover:text-white transition-colors">GitHub</a>
          </div>
        </div>
      </nav>

      <section className="relative pt-32 pb-20 lg:pt-48 lg:pb-32 px-6">
        <div className="absolute inset-0 bg-grid-pattern -z-10 opacity-30 pointer-events-none" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[400px] bg-purple-900/20 blur-[120px] -z-10 rounded-full mix-blend-screen" />
        
        <div className="max-w-5xl mx-auto text-center">
          <motion.div 
            initial="hidden"
            animate="visible"
            variants={staggerContainer}
            className="space-y-6"
          >
            <motion.div variants={fadeInUp} className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-300 text-xs tracking-wider uppercase">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500"></span>
              </span>
              Autonomous Financial Intelligence Engine
            </motion.div>
            
            <motion.h1 variants={fadeInUp} className="text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight text-white glow-text">
              Golden Datasets. <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-gray-200 to-gray-500">Zero Chaos.</span>
            </motion.h1>
            
            <motion.p variants={fadeInUp} className="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto leading-relaxed">
              Convert raw, conflicting financial data into pristine, AI-ready intelligence. 
              Powered by recursive conflict resolution and algebraic recovery.
            </motion.p>
            
            <motion.div variants={fadeInUp} className="pt-8 flex flex-col sm:flex-row gap-4 justify-center items-center">
              <button className="px-8 py-4 rounded-lg bg-white text-black font-semibold hover:bg-gray-200 transition-all flex items-center gap-2 group">
                Deploy v27.0
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </button>
              <button className="px-8 py-4 rounded-lg border border-white/10 text-white hover:bg-white/5 transition-all">
                View Documentation
              </button>
            </motion.div>
          </motion.div>
        </div>
      </section>

      <section id="architecture" className="py-24 px-6 relative">
        <div className="max-w-7xl mx-auto">
          <div className="mb-12">
            <h2 className="text-3xl font-bold text-white mb-4">Core Architecture</h2>
            <p className="text-gray-400 max-w-xl">Modular, high-performance spokes powered by a central Math Engine.</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[250px]">
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              className="md:col-span-2 glass-card rounded-2xl p-8 relative overflow-hidden group"
            >
              <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                <Cpu size={120} />
              </div>
              <div className="relative z-10 h-full flex flex-col justify-between">
                <div>
                  <div className="w-12 h-12 rounded-lg bg-white/5 flex items-center justify-center mb-4 border border-white/10">
                    <Cpu className="text-purple-400" />
                  </div>
                  <h3 className="text-2xl font-semibold text-white mb-2">Hub: Math Engine</h3>
                  <p className="text-gray-400 max-w-md">Polars LazyFrame powered zero-copy processing. The central nervous system that orchestrates all data transformations with mathematical precision.</p>
                </div>
                <div className="flex gap-2 mt-4">
                   <span className="text-xs px-2 py-1 rounded bg-white/5 border border-white/10 text-gray-300">Zero-Copy</span>
                   <span className="text-xs px-2 py-1 rounded bg-white/5 border border-white/10 text-gray-300">Rust Core</span>
                </div>
              </div>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2 }}
              className="glass-card rounded-2xl p-8 relative overflow-hidden group"
            >
              <div className="absolute top-0 right-0 p-6 opacity-10 group-hover:opacity-20 transition-opacity">
                <Zap size={80} />
              </div>
              <div className="h-full flex flex-col justify-between relative z-10">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center mb-4 border border-blue-500/20">
                  <Zap className="text-blue-400" size={20} />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-1">Spoke A</h3>
                  <div className="text-sm text-blue-400 mb-2">AI Tuning Data</div>
                  <p className="text-sm text-gray-400">Chain-of-Thought JSONL generation for fine-tuning LLMs.</p>
                </div>
              </div>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3 }}
              className="glass-card rounded-2xl p-8 relative overflow-hidden group"
            >
              <div className="absolute top-0 right-0 p-6 opacity-10 group-hover:opacity-20 transition-opacity">
                <BarChart3 size={80} />
              </div>
              <div className="h-full flex flex-col justify-between relative z-10">
                 <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center mb-4 border border-green-500/20">
                  <BarChart3 className="text-green-400" size={20} />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-1">Spoke B</h3>
                  <div className="text-sm text-green-400 mb-2">Quant Data</div>
                  <p className="text-sm text-gray-400">Z-Ordered Parquet files optimized for high-speed timeseries analysis.</p>
                </div>
              </div>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.4 }}
              className="glass-card rounded-2xl p-8 relative overflow-hidden group"
            >
              <div className="absolute top-0 right-0 p-6 opacity-10 group-hover:opacity-20 transition-opacity">
                <Database size={80} />
              </div>
               <div className="h-full flex flex-col justify-between relative z-10">
                 <div className="w-10 h-10 rounded-lg bg-yellow-500/10 flex items-center justify-center mb-4 border border-yellow-500/20">
                  <Database className="text-yellow-400" size={20} />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-1">Spoke C</h3>
                  <div className="text-sm text-yellow-400 mb-2">RAG Data</div>
                  <p className="text-sm text-gray-400">Context Tree JSON structures for retrieval-augmented generation.</p>
                </div>
              </div>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.5 }}
              className="glass-card rounded-2xl p-8 relative overflow-hidden group"
            >
              <div className="absolute top-0 right-0 p-6 opacity-10 group-hover:opacity-20 transition-opacity">
                <Network size={80} />
              </div>
               <div className="h-full flex flex-col justify-between relative z-10">
                 <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center mb-4 border border-red-500/20">
                  <Network className="text-red-400" size={20} />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-1">Spoke D</h3>
                  <div className="text-sm text-red-400 mb-2">Risk Graph</div>
                  <p className="text-sm text-gray-400">Causal Triples JSON for mapping complex financial dependencies.</p>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      <section id="features" className="py-24 px-6 border-t border-white/5 bg-black/50">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-12">
            {[
              {
                icon: GitMerge,
                title: "Recursive Conflict Resolution",
                desc: "Automatically resolves discrepancies between Tier 1 (PDF) and Tier 2 (CSV) sources with audit trails."
              },
              {
                icon: Calculator,
                title: "Algebraic Recovery",
                desc: "Restores missing items using fundamental accounting identities (A = L + E) to ensure completeness."
              },
              {
                icon: Activity,
                title: "Self-Evolving Alpha",
                desc: "Generates predictive signals using Fractional Differentiation and Meta-Labeling techniques."
              },
              {
                icon: Zap,
                title: "Execution Optimization",
                desc: "Models slippage, latency, and market impact to calculate realistic, actionable Net Alpha."
              },
              {
                icon: Layers,
                title: "Auto-Tuning",
                desc: "Detects market regimes (e.g., High Volatility) and dynamically adjusts risk parameters."
              },
               {
                icon: Database,
                title: "Golden Datasets",
                desc: "The final output: pristine, normalized, and structured data ready for any downstream AI task."
              }
            ].map((feature, idx) => (
              <motion.div 
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
                className="flex flex-col gap-4 group"
              >
                <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center group-hover:bg-purple-500/10 group-hover:border-purple-500/20 transition-colors">
                  <feature.icon className="text-gray-400 group-hover:text-purple-400 transition-colors" size={24} />
                </div>
                <h3 className="text-xl font-bold text-white group-hover:text-purple-300 transition-colors">{feature.title}</h3>
                <p className="text-gray-400 leading-relaxed text-sm">{feature.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <footer className="py-12 px-6 border-t border-white/5">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center text-sm text-gray-500">
          <div>&copy; 2026 FinDistill Inc. All rights reserved.</div>
          <div className="flex gap-6 mt-4 md:mt-0">
             <a href="#" className="hover:text-white transition-colors">Privacy</a>
             <a href="#" className="hover:text-white transition-colors">Terms</a>
             <a href="#" className="hover:text-white transition-colors">Status</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
