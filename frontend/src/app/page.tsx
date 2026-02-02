import StatsCard from "@/components/dashboard/StatsCard";
import { 
  Plus, 
  Search, 
  Filter, 
  ArrowUpRight,
  ChevronRight
} from "lucide-react";

export default function Home() {
  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Intelligence Overview</h2>
          <p className="text-muted text-sm">Real-time status of your financial data pipeline</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={14} />
            <input 
              type="text" 
              placeholder="Search intelligence..." 
              className="bg-glass border border-border rounded-lg pl-9 pr-4 py-2 text-sm w-64 focus:outline-none focus:border-primary transition-colors"
            />
          </div>
          <button className="flex items-center gap-2 bg-primary hover:bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            <Plus size={16} />
            New Case
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard 
          label="Total Cases" 
          value="1,284" 
          description="Active across all sectors" 
          trend={{ value: "+12.5%", positive: true }}
        />
        <StatsCard 
          label="Data Precision" 
          value="99.92%" 
          description="Pillar 1 Self-Reflection score" 
          trend={{ value: "+0.04%", positive: true }}
        />
        <StatsCard 
          label="Simulation Depth" 
          value="8-Hop" 
          description="Causal counterfactual horizon" 
        />
        <StatsCard 
          label="System Health" 
          value="Stable" 
          description="All spokes operational" 
          trend={{ value: "99.9% Uptime", positive: true }}
        />
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Recent Cases */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex justify-between items-center px-1">
            <h3 className="font-bold text-lg">Active High-Priority Cases</h3>
            <button className="text-primary text-xs font-semibold flex items-center gap-1 hover:underline">
              View All <ChevronRight size={14} />
            </button>
          </div>
          <div className="glass-panel overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border bg-white/[0.01]">
                  <th className="px-6 py-4 text-xs font-bold text-muted uppercase tracking-widest">Entity</th>
                  <th className="px-6 py-4 text-xs font-bold text-muted uppercase tracking-widest">Status</th>
                  <th className="px-6 py-4 text-xs font-bold text-muted uppercase tracking-widest">Confidence</th>
                  <th className="px-6 py-4 text-xs font-bold text-muted uppercase tracking-widest">Last Event</th>
                  <th className="px-6 py-4"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[
                  { name: "Tesla Inc.", ticker: "TSLA", status: "Refining", conf: "98.2%", time: "2m ago" },
                  { name: "NVIDIA Corp.", ticker: "NVDA", status: "Decision", conf: "94.5%", time: "12m ago" },
                  { name: "Apple Inc.", ticker: "AAPL", status: "Completed", conf: "99.1%", time: "1h ago" },
                  { name: "Microsoft", ticker: "MSFT", status: "Simulation", conf: "89.4%", time: "3h ago" },
                ].map((row, i) => (
                  <tr key={i} className="hover:bg-glass transition-colors group cursor-pointer">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="text-sm font-bold">{row.name}</span>
                        <span className="text-[10px] text-muted tracking-widest uppercase font-semibold">{row.ticker}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                        <span className="text-xs font-medium">{row.status}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 font-mono text-xs font-semibold text-secondary">
                      {row.conf}
                    </td>
                    <td className="px-6 py-4 text-xs text-muted">
                      {row.time}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <ArrowUpRight size={14} className="text-muted group-hover:text-primary transition-colors" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Audit Vault Quick View */}
        <div className="space-y-4">
          <div className="flex justify-between items-center px-1">
            <h3 className="font-bold text-lg">System Audit Vault</h3>
          </div>
          <div className="glass-panel p-6 space-y-6">
            <div className="space-y-4">
              {[
                { stage: "Distill", msg: "Reflected 12 facts for NVDA", time: "2m ago" },
                { stage: "Oracle", msg: "Simulated 5 what-if scenarios", time: "15m ago" },
                { stage: "Robot", msg: "Decision recommendation signed", time: "1h ago" },
                { stage: "System", msg: "Database indexing completed", time: "2h ago" },
              ].map((log, i) => (
                <div key={i} className="flex gap-4 items-start">
                  <div className="w-1 h-8 bg-border group-hover:bg-primary transition-colors rounded-full" />
                  <div className="flex-1">
                    <div className="flex justify-between items-center">
                      <span className="text-[10px] font-bold text-primary uppercase tracking-widest">{log.stage}</span>
                      <span className="text-[10px] text-muted">{log.time}</span>
                    </div>
                    <p className="text-xs font-medium mt-1">{log.msg}</p>
                  </div>
                </div>
              ))}
            </div>
            <button className="w-full py-2 bg-glass hover:bg-white/[0.05] border border-border rounded-lg text-xs font-bold transition-all">
              Launch Full Audit Vault
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
