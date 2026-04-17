import { useMemo } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ScatterChart, Scatter, ZAxis
} from 'recharts';
import { LayoutDashboard, CheckCircle, AlertCircle, Info, Lightbulb, Sparkles, MapPin } from 'lucide-react';

interface DashboardTabProps {
  data: any[];
  activeMetric: string;
  level: string;
  summary?: any;
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
    
    // Helper to safely check boolean-ish values from the database
    const safeStr = (v: any) => v == null ? '' : String(v).toLowerCase().trim();
    const isPos = (v: any) => {
        const s = safeStr(v);
        return v === 1 || v === 1.0 || ['yes', 'true', 'functional', 'satisfactory', 'available', 'provided', 'both'].includes(s);
    };
    const isNeg = (v: any) => {
        const s = safeStr(v);
        return v === 0 || v === 0.0 || ['no', 'false', 'unavailable', 'missing', 'none', 'neither'].includes(s);
    };
    const isIss = (v: any) => {
        const s = safeStr(v);
        return v === 2 || v === 2.0 || s.includes('issue') || s.includes('partial') || s.includes('repair') || s.includes('not functional') || s.includes('only');
    };

    // Detect if metric is binary or numeric
    const isBinaryMetric = data.slice(0, 100).every(d => isPos(d[activeMetric]) || isNeg(d[activeMetric]) || isIss(d[activeMetric]) || d[activeMetric] == null);

    const positiveCount = data.filter(d => isPos(d[activeMetric])).length;
    const negativeCount = data.filter(d => isNeg(d[activeMetric])).length;
    const issueCount = data.filter(d => isIss(d[activeMetric])).length;

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

    // Dynamic key discovery for regions
    const sample = data[0] || {};
    const dKey = Object.keys(sample).find(k => k.toLowerCase() === 'district_n' || k.toLowerCase() === 'district' || k.toLowerCase() === 'district_name') || 'district_name';
    const bKey = Object.keys(sample).find(k => k.toLowerCase() === 'block_name' || k.toLowerCase() === 'block' || k.toLowerCase() === 'block_n') || 'block_name';

    data.forEach(d => {
        const d_name = d[dKey] || "Unknown";
        const b_name = d[bKey] || "Unknown";

        if (!distDataMap[d_name]) distDataMap[d_name] = { name: d_name, total: 0, missing: 0 };
        distDataMap[d_name].total++;
        if (isNeg(d[activeMetric])) distDataMap[d_name].missing++;

        if (!blockDataMap[b_name]) blockDataMap[b_name] = { name: b_name, district: d_name, total: 0, missing: 0 };
        blockDataMap[b_name].total++;
        if (isNeg(d[activeMetric])) blockDataMap[b_name].missing++;
    });

    const districtBreakdown = Object.values(distDataMap).sort((a: any, b: any) => b.missing - a.missing).slice(0, 5);
    const blockBreakdown = Object.values(blockDataMap).sort((a: any, b: any) => b.missing - a.missing).slice(0, 10);

    if (districtBreakdown[0]) gapAnalysis.worstDistrict = (districtBreakdown[0] as any).name;
    if (blockBreakdown[0]) gapAnalysis.worstBlock = (blockBreakdown[0] as any).name;

    // Charts preparation
    const statusData = [
        { name: 'Equipped', value: positiveCount, color: '#10b981' },
        { name: 'Missing', value: negativeCount, color: '#ef4444' },
        { name: 'Issues', value: issueCount, color: '#f59e0b' }
    ];

    // Build Scatter Data for Correlation
    const scatterData = Object.values(blockDataMap).map((b: any) => ({
        name: b.name,
        x: b.total > 0 ? Math.round(((b.total - b.missing) / b.total) * 100) : 0,
        y: b.missing,
        z: b.total
    })).slice(0, 15);

    // Venn-Logic / Multi-Metric Detection
    const infra_keywords = ['electricity', 'water', 'toilet', 'computer', 'classroom', 'library', 'ramp', 'solar', 'playground', 'internet', 'extinguisher'];
    const binaryCols = Object.keys(sample).filter(k => 
        infra_keywords.some(kw => k.toLowerCase().includes(kw)) && 
        !['id', 'udise_code', 'udise_num', 'geometry'].includes(k) &&
        data.slice(0, 10).every(d => isPos(d[k]) || isNeg(d[k]) || isIss(d[k]) || d[k] == null)
    );
    const isMultiBinaryMode = binaryCols.length === 2;
    const multiStats: any[] = [];
    
    if (isMultiBinaryMode) {
        const s1 = binaryCols[0];
        const s2 = binaryCols[1];
        
        // Find a status column if it exists (e.g. comp_smart_attainment)
        const statusKey = Object.keys(sample).find(k => k.toLowerCase().includes('_attainment') || k.toLowerCase().includes('_status'));

        let both = 0, onlyX = 0, onlyY = 0, neither = 0;
        data.forEach(d => {
            // Check if backend already provided a calculated status
            const sVal = safeStr(d[statusKey || 'status']);
            if (sVal === 'both') both++;
            else if (sVal.includes('only') && sVal.includes(s1.split('_')[0])) onlyX++;
            else if (sVal.includes('only') && sVal.includes(s2.split('_')[0])) onlyY++;
            else if (sVal === 'neither' || sVal === 'none') neither++;
            else {
                // Fallback to manual calc
                const p1 = isPos(d[s1]);
                const p2 = isPos(d[s2]);
                if (p1 && p2) both++;
                else if (p1 && !p2) onlyX++;
                else if (!p1 && p2) onlyY++;
                else neither++;
            }
        });

        multiStats.push(
            { name: 'Both', value: both, color: '#10b981', label: 'Joint Compliance' },
            { name: s1.split('_')[0].charAt(0).toUpperCase() + s1.split('_')[0].slice(1), value: onlyX, color: '#3b82f6', label: `${s1.split('_')[0]} only` },
            { name: s2.split('_')[0].charAt(0).toUpperCase() + s2.split('_')[0].slice(1), value: onlyY, color: '#f59e0b', label: `${s2.split('_')[0]} only` },
            { name: 'None', value: neither, color: '#ef4444', label: 'No Facility' }
        );
    }

    return {
        summaryCards: { total, positiveCount, negativeCount, issueCount, coverageVal },
        barData: isMultiBinaryMode ? multiStats : statusData,
        pieData: isMultiBinaryMode ? multiStats : statusData,
        isMultiBinaryMode,
        multiStats,
        districtBreakdown,
        blockBreakdown,
        gapAnalysis,
        scatterData,
        prioritySchools: data.filter(d => isNeg(d[activeMetric])).slice(0, 6).map(d => ({
            name: d.schoolName || d.display_name || d.schname || "School",
            block: d[bKey] || "-",
            status: "Critical"
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
                <div className="space-y-4">
                    {(() => {
                        const points = Array.isArray(aiInsights?.summary) ? aiInsights.summary : [aiInsights?.summary || "Factual analysis of regional infrastructure status."];
                        return points.map((pt: string, i: number) => (
                            <p key={i} className="text-slate-700 text-sm leading-relaxed font-semibold flex gap-2">
                                <span className="text-blue-600 font-extrabold">•</span>
                                <span>{pt}</span>
                            </p>
                        ));
                    })()}
                </div>
            </section>

            <section className="bg-indigo-600 p-8 rounded-[40px] shadow-xl relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:scale-110 transition-transform duration-700"><Lightbulb size={100} /></div>
                <h3 className="text-[10px] font-black text-white/70 uppercase tracking-widest mb-4 flex items-center gap-2 italic">
                    <Lightbulb size={14} /> Strategic Policy Recommendations
                </h3>
                <div className="space-y-4">
                    {(() => {
                        const points = Array.isArray(aiInsights?.recommendations) ? aiInsights.recommendations : [aiInsights?.recommendations || "Actionable insights for regional development planning."];
                        return points.map((pt: any, i: number) => (
                            <p key={i} className="text-white text-sm leading-relaxed font-bold flex gap-2">
                                <span className="text-white/50 font-extrabold">•</span>
                                <span>{pt}</span>
                            </p>
                        ));
                    })()}
                </div>
            </section>
        </div>

        {/* COMPARATIVE ANALYTICS (Venn Mode) */}
        {isMultiBinaryMode && multiStats.length > 0 && (
            <div className="space-y-6 pt-4 border-t border-slate-100 mt-12">
                <div className="flex items-center gap-3">
                    <div className="h-8 w-1 bg-indigo-600 rounded-full" />
                    <h2 className="text-xl font-black text-slate-800 tracking-tight">Comparative Infrastructure Insight</h2>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <MetricCard label="Both Facilities" value={multiStats[0].value} sub="High Capability" icon={<Sparkles size={16}/>} color="emerald" />
                    <MetricCard label={`${multiStats[1].name}`} value={multiStats[1].value} sub="Partial Coverage" icon={<Info size={16}/>} color="blue" />
                    <MetricCard label={`${multiStats[2].name}`} value={multiStats[2].value} sub="Partial Coverage" icon={<Info size={16}/>} color="amber" />
                    <MetricCard label="Neither Facility" value={multiStats[3].value} sub="Critical Gap" icon={<AlertCircle size={16}/>} color="rose" />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div className="lg:col-span-2 bg-slate-900 rounded-[40px] p-8 text-white shadow-2xl overflow-hidden relative border border-white/5">
                         <div className="absolute top-0 right-0 p-12 opacity-5 scale-150 rotate-12"><LayoutDashboard size={200} /></div>
                         <h3 className="text-[10px] font-black text-white/40 uppercase tracking-widest mb-8">Structural Overlap Analysis</h3>
                         <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
                            <div className="space-y-8 border-l border-white/10 pl-8">
                                <div>
                                    <p className="text-5xl font-black text-emerald-400 leading-none">
                                        {Math.round((multiStats[0].value / (summaryCards?.total || 1)) * 100)}%
                                    </p>
                                    <p className="text-xs font-bold text-white/50 uppercase tracking-widest mt-2">Joint Accessibility Rate</p>
                                </div>
                                <div className="space-y-4">
                                    <div className="flex items-center justify-between text-[11px]">
                                        <span className="flex items-center gap-2 font-bold"><div className="w-2 h-2 rounded-full bg-blue-500" /> Only {multiStats[1].name.split(' ').slice(1).join(' ')}</span>
                                        <span className="font-black text-blue-300">{multiStats[1].value}</span>
                                    </div>
                                    <div className="flex items-center justify-between text-[11px]">
                                        <span className="flex items-center gap-2 font-bold"><div className="w-2 h-2 rounded-full bg-amber-500" /> Only {multiStats[2].name.split(' ').slice(1).join(' ')}</span>
                                        <span className="font-black text-amber-300">{multiStats[2].value}</span>
                                    </div>
                                    <div className="flex items-center justify-between text-[11px] pt-2 border-t border-white/5">
                                        <span className="flex items-center gap-2 font-bold opacity-60"><div className="w-2 h-2 rounded-full bg-rose-500" /> No Priority Specs</span>
                                        <span className="font-black text-rose-300">{multiStats[3].value}</span>
                                    </div>
                                </div>
                            </div>
                            <div className="h-64 relative flex items-center justify-center">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie data={multiStats} cx="50%" cy="50%" innerRadius={70} outerRadius={95} paddingAngle={8} dataKey="value" stroke="none">
                                            {multiStats.map((entry: any, index: number) => (
                                                <Cell key={`cell-${index}`} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <Tooltip contentStyle={{backgroundColor: '#0f172a', border: 'none', borderRadius: '12px', fontSize: '10px'}} />
                                    </PieChart>
                                </ResponsiveContainer>
                                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                    <span className="text-3xl font-black text-white leading-none">{multiStats[0].value}</span>
                                    <span className="text-[10px] font-black text-white/30 uppercase tracking-[0.2em] mt-2">Both Met</span>
                                </div>
                            </div>
                         </div>
                    </div>

                    <div className="bg-white rounded-[40px] p-8 border border-slate-100 shadow-sm flex flex-col justify-between relative overflow-hidden group">
                        <div className="absolute -top-10 -right-10 p-12 opacity-[0.03] rotate-12 group-hover:rotate-0 transition-transform duration-1000"><CheckCircle size={150} /></div>
                        <div>
                            <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-6">Strategic Opportunity</h3>
                            <p className="text-sm text-slate-600 leading-relaxed font-semibold">
                                System identifies <span className="text-rose-600 font-bold">{multiStats[1].value + multiStats[2].value}</span> schools in a "Partial Feature" state. 
                                Completing individual facility pairs represents the <span className="text-indigo-600 font-bold uppercase underline decoration-2 underline-offset-4">fastest path</span> to state-wide 100% enablement.
                            </p>
                        </div>
                        <div className="mt-8 pt-8 border-t border-slate-50 flex items-center gap-3">
                             <div className="bg-indigo-50 p-2 rounded-xl text-indigo-600"><AlertCircle size={16} /></div>
                             <p className="text-[10px] font-black text-indigo-600 leading-tight uppercase tracking-widest">
                                Policy Focus: Align {multiStats[1].name.split(' ')[1]} upgrades with {multiStats[2].name.split(' ')[1]} availability.
                             </p>
                        </div>
                    </div>
                </div>
            </div>
        )}

        {/* ANALYSIS GRIDS */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
            {/* Status Distribution (Bar) */}
            <div className="lg:col-span-2 bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                <div className="flex items-center justify-between mb-8 border-b pb-4">
                    <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest">Compliance Distribution (Volume)</h3>
                    <div className="flex gap-4">
                        {isMultiBinaryMode ? (
                            multiStats.map((s: any, i: number) => (
                                <LegendItem key={i} label={s.name} color={s.color} />
                            ))
                        ) : (
                            <>
                                <LegendItem label="Equipped" color="#10b981" />
                                <LegendItem label="Missing" color="#ef4444" />
                                <LegendItem label="Issue" color="#f59e0b" />
                            </>
                        )}
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

            {/* Status Breakdown (Pie) */}
            <div className="lg:col-span-1 bg-white p-6 rounded-3xl border border-slate-100 shadow-sm flex flex-col">
                <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-8 border-b pb-4">Proportional Gaps</h3>
                <div className="flex-1 min-h-[220px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={pieData}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={80}
                                paddingAngle={5}
                                dataKey="value"
                            >
                                {pieData.map((entry: any, index: number) => (
                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                            </Pie>
                            <Tooltip wrapperClassName="text-[10px] font-black !rounded-xl border-0 shadow-2xl" />
                        </PieChart>
                    </ResponsiveContainer>
                </div>
                <div className="text-center mt-2">
                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-tighter">Status Share %</p>
                </div>
            </div>

            {/* Gap Analysis Summary */}
            <div className="lg:col-span-1 bg-slate-900 text-white p-8 rounded-[40px] shadow-2xl flex flex-col justify-center">
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

        {/* GEOGRAPHIC DRILLDOWN */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">District-wise Impact</h3>
                <div className="space-y-2 max-h-[250px] overflow-y-auto pr-2 custom-scrollbar">
                    {districtBreakdown.map((d: any, i: number) => (
                        <div key={i} className="flex items-center justify-between p-3 bg-slate-50 rounded-2xl group hover:bg-rose-50 transition-colors">
                            <span className="text-[10px] font-black uppercase text-slate-600 group-hover:text-rose-600 transition-colors">{d.name}</span>
                            <div className="flex items-center gap-3">
                                <span className="text-sm font-black text-slate-800">{d.missing}</span>
                                <span className="text-[8px] font-bold text-slate-400 uppercase italic">Gaps</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
                <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">Top 10 High Intensity Blocks (Gaps)</h3>
                <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart layout="vertical" data={blockBreakdown}>
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                            <XAxis type="number" hide />
                            <YAxis dataKey="name" type="category" tick={{fontSize: 7, fontWeight: 700}} width={80} />
                            <Tooltip wrapperClassName="text-xs font-bold" cursor={{fill: 'rgba(239, 68, 68, 0.05)'}} />
                            <Bar dataKey="missing" fill="#ef4444" radius={[0, 8, 8, 0]} barSize={12} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>

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

