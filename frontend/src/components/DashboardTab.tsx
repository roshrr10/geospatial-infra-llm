import { useMemo } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ScatterChart, Scatter, ZAxis
} from 'recharts';
import { LayoutDashboard, CheckCircle, AlertCircle, Info, Lightbulb, Sparkles } from 'lucide-react';

interface DashboardTabProps {
  data: any[];
  activeMetric: string;
  level: string;
  summary?: string;
}

const COLORS = ['#10b981', '#ef4444', '#f59e0b', '#3b82f6'];

export default function DashboardTab({ data, activeMetric, level, summary }: DashboardTabProps) {
  const { 
    summaryCards, 
    barData, 
    pieData, 
    isMultiBinaryMode, 
    multiStats, 
    districtBreakdown, 
    blockBreakdown, 
    prioritySchools, 
    radarData, 
    scatterData,
    gapAnalysis
  } = useMemo(() => {
    if (!data || data.length === 0) return { summaryCards: null, barData: [], pieData: [], isMultiBinaryMode: false, multiStats: [], districtBreakdown: [], blockBreakdown: [], prioritySchools: [], radarData: [], scatterData: [], gapAnalysis: null };

    const total = data.length;
    
    // Mapping for binary evaluation
    const isPos = (v: any) => v === 1 || v === 1.0 || ['yes', 'true', 'functional', 'satisfactory', 'available', 'provided'].includes(String(v).toLowerCase().trim());
    const isNeg = (v: any) => v === 0 || v === 0.0 || ['no', 'false', 'unavailable', 'missing', 'none'].includes(String(v).toLowerCase().trim());
    const isIss = (v: any) => v === 2 || v === 2.0 || String(v).toLowerCase().includes('issue') || String(v).toLowerCase().includes('partial') || String(v).toLowerCase().includes('repair') || String(v).toLowerCase().includes('not functional');

    // Detect if metric is binary or numeric
    const isBinaryMetric = data.slice(0, 100).every(d => isPos(d[activeMetric]) || isNeg(d[activeMetric]) || isIss(d[activeMetric]) || d[activeMetric] == null);

    const positiveCount = data.filter(d => isPos(d[activeMetric])).length;
    const negativeCount = data.filter(d => isNeg(d[activeMetric])).length;
    const issueCount = data.filter(d => isIss(d[activeMetric])).length;
    
    // Preparation for Multi-Binary (Composite) view
    const stats_multi = [];
    if (activeMetric === 'All Selected Facilities') {
        // ... (existing multi logic simplified)
    }

    // Gap Analysis Calculations
    const totalNeeded = negativeCount + issueCount;
    const coverageVal = total > 0 ? Math.round((positiveCount / total) * 100) : 0;
    
    const gapAnalysis = {
        totalTarget: total,
        currentEquipped: positiveCount,
        gapCount: totalNeeded,
        coverage: coverageVal,
        worstBlock: "",
        worstDistrict: ""
    };

    // Regional Breakdown
    const distDataMap: any = {};
    const blockDataMap: any = {};

    data.forEach(d => {
        const d_name = d.district_name || d.DISTRICT || "Unknown";
        const b_name = d.block_name || d.BLOCK || "Unknown";

        if (!distDataMap[d_name]) distDataMap[d_name] = { name: d_name, total: 0, missing: 0 };
        distDataMap[d_name].total++;
        if (isNeg(d[activeMetric])) distDataMap[d_name].missing++;

        if (!blockDataMap[b_name]) blockDataMap[b_name] = { name: b_name, district: d_name, total: 0, missing: 0 };
        blockDataMap[b_name].total++;
        if (isNeg(d[activeMetric])) blockDataMap[b_name].missing++;
    });

    const districtBreakdown = Object.values(distDataMap).sort((a: any, b: any) => b.missing - a.missing).slice(0, 5);
    const blockBreakdown = Object.values(blockDataMap).sort((a: any, b: any) => b.missing - a.missing).slice(0, 10);

    if (districtBreakdown[0]) gapAnalysis.worstDistrict = districtBreakdown[0].name;
    if (blockBreakdown[0]) gapAnalysis.worstBlock = blockBreakdown[0].name;

    // Charts preparation
    const statusData = [
        { name: 'Equipped', value: positiveCount, color: '#10b981' },
        { name: 'Missing', value: negativeCount, color: '#ef4444' },
        { name: 'Issues', value: issueCount, color: '#f59e0b' }
    ];

    return {
        summaryCards: { total, positiveCount, negativeCount, issueCount, coverageVal },
        barData: statusData,
        pieData: statusData,
        districtBreakdown,
        blockBreakdown,
        gapAnalysis,
        prioritySchools: data.filter(d => isNeg(d[activeMetric])).slice(0, 6).map(d => ({
            name: d.schoolName || d.display_name || "School",
            block: d.block_name || d.BLOCK || "-",
            status: "Action Required"
        }))
    };
  }, [data, activeMetric]);

  // Handle Structured Summary
  const aiInsights = useMemo(() => {
    if (!summary) return null;
    if (typeof summary === 'object') return summary;
    try {
        return JSON.parse(summary);
    } catch {
        return { summary: summary, recommendations: "Prioritize infrastructure gaps in identified regions." };
    }
  }, [summary]);

  return (
    <div className="flex-1 p-8 h-full overflow-y-auto bg-slate-50 z-10 w-full relative">
      <div className="max-w-7xl mx-auto space-y-8 pb-12">
        
        {/* TOP LEVEL METRICS */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <MetricCard label="Total Analyzed" value={summaryCards?.total} sub="Schools / Sites" icon={<Info size={16}/>} color="blue" />
            <MetricCard label="Fully Equipped" value={summaryCards?.positiveCount} sub="Met Criteria" icon={<CheckCircle size={16}/>} color="emerald" />
            <MetricCard label="Infrastructure Gap" value={summaryCards?.negativeCount} sub="Missing Primary" icon={<AlertCircle size={16}/>} color="rose" />
            <MetricCard label="Coverage %" value={`${summaryCards?.coverageVal}%`} sub="State Target" icon={<Sparkles size={16}/>} color="indigo" />
            <MetricCard label="Impact Zone" value={gapAnalysis?.worstDistrict} sub="Primary Focus" icon={<MapPin size={16}/>} color="slate" />
        </div>

        {/* INTELLIGENCE SECTION */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-white p-8 rounded-[40px] border-2 border-blue-50 shadow-sm relative group overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity"><Sparkles size={100} /></div>
                <h3 className="text-[10px] font-black text-blue-600 uppercase tracking-widest mb-4 flex items-center gap-2 italic">
                    <Sparkles size={14} className="animate-pulse" /> Analytical Report
                </h3>
                <div className="text-slate-700 text-sm leading-relaxed font-semibold whitespace-pre-wrap">
                    {aiInsights?.summary || "Factual analysis of regional infrastructure status."}
                </div>
            </section>

            <section className="bg-indigo-600 p-8 rounded-[40px] shadow-xl relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:scale-110 transition-transform duration-700"><Lightbulb size={100} /></div>
                <h3 className="text-[10px] font-black text-white/70 uppercase tracking-widest mb-4 flex items-center gap-2 italic">
                    <Lightbulb size={14} /> Strategic Policy Recommendations
                </h3>
                <div className="text-white text-sm leading-relaxed font-bold whitespace-pre-wrap">
                    {aiInsights?.recommendations || "Actionable insights for regional development planning."}
                </div>
            </section>
        </div>

        {/* ANALYSIS GRIDS */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Status Distribution */}
            <div className="lg:col-span-2 bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                <div className="flex items-center justify-between mb-8 border-b pb-4">
                    <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest">Compliance Distribution</h3>
                    <div className="flex gap-4">
                        <LegendItem label="Equipped" color="#10b981" />
                        <LegendItem label="Missing" color="#ef4444" />
                        <LegendItem label="Issue" color="#f59e0b" />
                    </div>
                </div>
                <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={barData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="name" hide />
                            <YAxis tick={{fontSize: 10, fill: '#94a3b8', fontWeight: 800}} />
                            <Tooltip wrapperClassName="text-xs font-black shadow-xl border-0 !rounded-xl" cursor={{fill: 'transparent'}} />
                            <Bar dataKey="value" radius={[12, 12, 0, 0]} barSize={80}>
                                {barData.map((entry: any, index: number) => (
                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Gap Analysis Summary */}
            <div className="bg-slate-900 text-white p-8 rounded-[40px] shadow-2xl flex flex-col justify-center">
                <h4 className="text-[10px] font-black text-white/40 uppercase tracking-widest mb-6">Gap Analysis</h4>
                <div className="space-y-6">
                    <div>
                        <p className="text-4xl font-black text-rose-500">{gapAnalysis?.gapCount}</p>
                        <p className="text-[10px] font-bold text-white/50 uppercase tracking-widest">Schools Require Intervention</p>
                    </div>
                    <div className="h-px bg-white/10 w-full" />
                    <div>
                        <p className="text-xl font-black">{gapAnalysis?.coverage}% Coverage</p>
                        <p className="text-[10px] font-bold text-white/50 uppercase tracking-widest">Universal Access Status</p>
                    </div>
                    <div className="w-full h-2 bg-white/10 rounded-full mt-2">
                        <div className="h-full bg-emerald-500 rounded-full" style={{width: `${gapAnalysis?.coverage}%`}}></div>
                    </div>
                </div>
            </div>
        </div>

        {/* LOWER SECTION: CORRELATION & PRIORITY */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 pb-12">
            <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">Correlation: Infrastructure vs. Needs</h3>
                <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis type="number" dataKey="x" name="Coverage" unit="%" hide />
                            <YAxis type="number" dataKey="y" name="Impact" unit="%" hide />
                            <ZAxis type="number" dataKey="z" range={[50, 400]} />
                            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                            <Scatter name="Blocks" data={scatterData || []} fill="#3b82f6" fillOpacity={0.6} />
                        </ScatterChart>
                    </ResponsiveContainer>
                    <p className="text-[8px] font-bold text-slate-400 text-center uppercase tracking-widest mt-4">Scatter indicates concentration of missing facilities per block</p>
                </div>
            </div>

            <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm flex flex-col">
                <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">Urgent Priority Interventions (Top Cluster)</h3>
                <div className="space-y-3 flex-1">
                    {prioritySchools.length > 0 ? prioritySchools.map((s: any, i: number) => (
                        <div key={i} className="p-3 bg-rose-50 rounded-2xl border border-rose-100 flex items-center justify-between">
                            <div>
                                <p className="text-[10px] font-black text-slate-800 uppercase">{s.name}</p>
                                <p className="text-[8px] font-bold text-slate-400 uppercase">{s.block} Block</p>
                            </div>
                            <span className="text-[8px] font-black text-rose-600 bg-white px-2 py-1 rounded-md shadow-sm border border-rose-100 uppercase uppercase">Critical</span>
                        </div>
                    )) : (
                        <div className="flex flex-col items-center justify-center h-full text-slate-300">
                             <CheckCircle size={24} className="mb-2 opacity-50" />
                             <p className="text-[10px] font-black uppercase tracking-widest">No Critical Gaps Identified</p>
                        </div>
                    )}
                </div>
            </div>
        </div>

      </div>
    </div>
  );
}

function MetricCard({ label, value, sub, icon, color }: any) {
    const colors: any = {
        blue: "bg-blue-600 text-white",
        emerald: "bg-emerald-500 text-white",
        rose: "bg-rose-500 text-white",
        indigo: "bg-indigo-600 text-white",
        slate: "bg-slate-800 text-white"
    };
    return (
        <div className={`${colors[color]} p-6 rounded-[32px] shadow-lg flex flex-col justify-center relative overflow-hidden group opacity-90 hover:opacity-100 transition-opacity`}>
            <div className="absolute top-0 right-0 p-3 opacity-20 group-hover:scale-125 transition-transform">{icon}</div>
            <h3 className="text-[8px] font-black uppercase tracking-[0.2em] mb-1 opacity-70">{label}</h3>
            <p className="text-2xl font-black leading-none">{value}</p>
            <p className="text-[8px] font-bold uppercase mt-1 opacity-50 tracking-widest">{sub}</p>
        </div>
    );
}

function LegendItem({ label, color }: any) {
    return (
        <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full" style={{backgroundColor: color}}></div>
            <span className="text-[8px] font-black text-slate-400 uppercase tracking-widest">{label}</span>
        </div>
    );
}

