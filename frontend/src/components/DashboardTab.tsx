import { useMemo } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ScatterChart, Scatter, ZAxis
} from 'recharts';
import { LayoutDashboard, CheckCircle, AlertCircle, Info, Lightbulb } from 'lucide-react';

interface DashboardTabProps {
  data: any[];
  activeMetric: string;
  level: string;
  summary?: string;
}

const COLORS = ['#10b981', '#ef4444', '#f59e0b', '#3b82f6'];

export default function DashboardTab({ data, activeMetric, level, summary }: DashboardTabProps) {
  const { summaryCards, barData, pieData, isMultiBinaryMode, multiStats, districtBreakdown, blockBreakdown, prioritySchools, radarData, scatterData } = useMemo(() => {
    if (!data || data.length === 0) return { summaryCards: null, barData: [], pieData: [], isMultiBinaryMode: false, multiStats: [], districtBreakdown: [], blockBreakdown: [], prioritySchools: [], radarData: [], scatterData: [] };

    const total = data.length;
    let positiveCount = 0;
    
    // Attempt to determine if activeMetric is binary
    const isBinary = data.some(d => {
      const v = d[activeMetric];
      return v === 1 || v === 0 || typeof v === 'string' && ['yes', 'no'].includes(v.toLowerCase());
    });
    const isPos = (v: any) => v === 1 || v === 1.0 || ['yes', 'true', 'functional', 'satisfactory', 'available', 'provided'].includes(String(v).toLowerCase().trim());
    const isNeg = (v: any) => v === 0 || v === 0.0 || ['no', 'false', 'unavailable', 'missing', 'none'].includes(String(v).toLowerCase().trim());
    const isIss = (v: any) => v === 2 || v === 2.0 || String(v).toLowerCase().includes('issue') || String(v).toLowerCase().includes('partial') || String(v).toLowerCase().includes('repair') || String(v).toLowerCase().includes('not functional');

    // Detect if Multi Binary Mode
    const keys = Object.keys(data[0] || {});
    const sKeys = new Set(['geometry', 'id', 'display_name', 'udise_code', 'udise_num', 'udisecode', 'geometry_wkt', 'sl_no', 'schname', 'school_name', 'schoolName', 'schoolname', 'block_name', 'district_name', 'cluster_name', 'village_name', 'pincode', 'pinc', 'serial', 'index', 'code', 'longitude', 'latitude', 'villageid', 'village_id', 'vcode', 'v_id', 'village_code', 'blockid', 'block_id', 'districtid', 'district_id', 'stateid', 'state_id', 'priority_rank', 'total_schools', 'block_total_schools', 'schools_per_sqkm', 'road_density_km_per_sqkm', 'block_area_sqkm', 'total_road_km', 'avg_road_density', 'avg_school_density']);
    const skipKeywords = ['id', 'code', 'udise', 'sl_no', 'serial', 'index', 'pinc', 'pincode', 'mobi', 'phone', 'latitude', 'longitude', 'geometry', 'accuracy', 'altitude', 'class', 'grade', 'year', 'month', 'boundary', 'shape'];
    const numericKeys = keys.filter(key => {
        const k = key.toLowerCase();
        if (skipKeywords.some(skip => k.includes(skip))) return false;
        const infraKeywords = ['solar', 'panel', 'electricity', 'water', 'toilet', 'computer', 'facility', 'internet', 'smart', 'ramp', 'playground', 'available', 'connection', 'provided'];
        if (infraKeywords.some(ik => k.includes(ik))) return true;
        return data.slice(0, 50).some(row => typeof row[key] === 'number' || (typeof row[key] === 'string' && row[key].trim() !== '' && !isNaN(Number(row[key]))));
    });

    const multiBinaryKeys = numericKeys.filter(k => k !== 'All Selected Facilities' && data.slice(0, 100).every(d => isPos(d[k]) || isNeg(d[k]) || isIss(d[k]) || d[k] == null));
    const isMultiBinaryMode = activeMetric === 'All Selected Facilities' && multiBinaryKeys.length > 1;

    const multiStats = isMultiBinaryMode ? multiBinaryKeys.map(k => ({
        key: k,
        label: k.replace(/_/g, ' '),
        yes: data.filter(d => isPos(d[k])).length
    })) : [];

    let noCount = 0;
    let issueCount = 0;

    if (isBinary) {
      positiveCount = data.filter(d => isPos(d[activeMetric])).length;
      noCount = data.filter(d => isNeg(d[activeMetric])).length;
      issueCount = data.filter(d => isIss(d[activeMetric])).length;
      
      if (issueCount === 0 && (positiveCount + noCount < total)) {
        issueCount = total - positiveCount - noCount;
      }
    } else {
      // If it's an aggregate like "number of schools", we can just sum them
      positiveCount = data.reduce((acc, d) => acc + (parseFloat(d[activeMetric]) || 0), 0);
    }

    const coveragePct = total > 0 && isBinary ? Math.round((positiveCount / total) * 100) : null;
    
    const cards = {
      totalRecords: total,
      primaryValue: positiveCount,
      noCount,
      issueCount,
      coverage: coveragePct,
      isBinary
    };

    // New Data for Status Distribution Chart
    const statusDistData = [
        { name: 'Available / Yes', value: positiveCount, color: '#10b981' },
        { name: 'Functional Issue', value: issueCount, color: '#f59e0b' },
        { name: 'Not Available / No', value: noCount, color: '#ef4444' }
    ].filter(d => d.value > 0);

    // Prepare Regional Breakdown (Separate Districts and Blocks)
    const { districtBreakdown, blockBreakdown } = (() => {
        const dists: Record<string, { name: string, no: number, issue: number, total: number, sum: number, valCount: number }> = {};
        const blocks: Record<string, { name: string, parent: string, no: number, issue: number, total: number, sum: number, valCount: number }> = {};
        
        data.forEach(d => {
            const block = d.block_name || d.BLOCK;
            const dist = d.district_name || d.DISTRICT;
            const val = parseFloat(d[activeMetric]);
            
            if (dist) {
                if (!dists[dist]) dists[dist] = { name: dist, no: 0, issue: 0, total: 0, sum: 0, valCount: 0 };
                dists[dist].total++;
                if (isBinary) {
                    if (isNeg(d[activeMetric])) dists[dist].no++;
                    else if (isIss(d[activeMetric])) dists[dist].issue++;
                } else if (!isNaN(val)) {
                    dists[dist].sum += val;
                    dists[dist].valCount++;
                }
            }
            
            if (block) {
                if (!blocks[block]) blocks[block] = { name: block, parent: dist || "Unknown", no: 0, issue: 0, total: 0, sum: 0, valCount: 0 };
                blocks[block].total++;
                if (isBinary) {
                    if (isNeg(d[activeMetric])) blocks[block].no++;
                    else if (isIss(d[activeMetric])) blocks[block].issue++;
                } else if (!isNaN(val)) {
                    blocks[block].sum += val;
                    blocks[block].valCount++;
                }
            }
        });

        const sortFn = (a: any, b: any) => {
            if (isBinary) return (b.no + b.issue) - (a.no + a.issue);
            const avgA = a.valCount > 0 ? a.sum / a.valCount : 0;
            const avgB = b.valCount > 0 ? b.sum / b.valCount : 0;
            return avgB - avgA;
        };

        return {
            districtBreakdown: Object.values(dists).sort(sortFn).slice(0, 5),
            blockBreakdown: Object.values(blocks).sort(sortFn).slice(0, 8)
        };
    })();

    // Prepare Priority Schools (Bottom 5 schools with most issues)
    const prioritySchools = isBinary ? data
        .filter(d => isNeg(d[activeMetric]) || isIss(d[activeMetric]))
        .slice(0, 5)
        .map(d => ({
            name: d.schoolName || d.display_name || d.schname || "School",
            block: d.block_name || d.BLOCK || "N/A",
            status: isNeg(d[activeMetric]) ? "Missing" : "Issue",
            color: isNeg(d[activeMetric]) ? "text-rose-600" : "text-amber-500"
        })) : [];

    // Prepare Radar Data (Benchmarking against State Average)
    // Prepare Radar Data (Benchmarking: Current Context Metrics)
    const radarData = data.length > 0 ? (multiBinaryKeys.length > 0 ? multiBinaryKeys : (activeMetric && activeMetric !== 'All Selected Facilities' ? [activeMetric] : []))
        .filter(k => !sKeys.has(k.toLowerCase()))
        .map(k => {
            const isKPositive = (v: any) => v === 1 || v === 1.0 || ['yes', 'true', 'functional', 'satisfactory', 'available', 'provided'].includes(String(v).toLowerCase().trim());
            const posCount = data.filter(d => isKPositive(d[k])).length;
            const avg = posCount / total * 100;
            return {
                subject: k.replace(/_/g, ' ').toUpperCase(),
                A: avg,
                fullMark: 100,
                isHighlighted: k === activeMetric
            };
        }) : [];

    // Prepare Scatter Data (Correlation: Computers vs Internet)
    const scatterData = (() => {
        const compKey = multiBinaryKeys.find(k => k.toLowerCase().includes('computer'));
        const netKey = multiBinaryKeys.find(k => k.toLowerCase().includes('internet') || k.toLowerCase().includes('smart'));
        if (compKey && netKey) {
            // Group by block to keep it performant
            const blockGroups: Record<string, { x: number, y: number, count: number }> = {};
            data.forEach(d => {
                const b = d.block_name || d.BLOCK || 'Other';
                if (!blockGroups[b]) blockGroups[b] = { x: 0, y: 0, count: 0 };
                if (isPos(d[compKey])) blockGroups[b].x++;
                if (isPos(d[netKey])) blockGroups[b].y++;
                blockGroups[b].count++;
            });
            return Object.entries(blockGroups).map(([name, stats]) => ({
                name,
                x: (stats.x / stats.count) * 100,
                y: (stats.y / stats.count) * 100,
                z: stats.count
            }));
        }
        return [];
    })();

    // Prepare Pie Data (if binary)
    const pieData = statusDistData.map(d => ({ name: d.name, value: d.value }));

    return { 
        summaryCards: cards, 
        barData: statusDistData, 
        pieData, 
        isMultiBinaryMode, 
        multiStats, 
        districtBreakdown, 
        blockBreakdown, 
        prioritySchools,
        radarData,
        scatterData
    };
  }, [data, activeMetric]);

  if (!data || data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full bg-slate-50 text-slate-400">
        <LayoutDashboard size={48} className="mb-4 opacity-50" />
        <p className="font-bold tracking-widest uppercase text-xs">No Data Available for Dashboard</p>
        <p className="font-medium text-xs mt-2 opacity-70">Execute a query to populate analytics.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 p-8 h-full overflow-y-auto bg-slate-50 z-10 w-full relative">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {summary && (
            <div className="bg-white p-6 rounded-[32px] border-2 border-blue-50 shadow-sm relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none"><Lightbulb size={64} className="text-blue-600" /></div>
                <h3 className="text-[10px] font-black text-blue-600 uppercase tracking-widest mb-3 flex items-center gap-2 italic">
                    <Lightbulb size={14} /> AI Analysis Snapshot
                </h3>
                <div className="text-slate-600 text-sm leading-relaxed font-medium">
                    {summary}
                </div>
            </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-3xl shadow-sm border border-slate-100 flex flex-col justify-center">
            <h3 className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1 flex items-center gap-2">Total Sample</h3>
            <p className="text-3xl font-black text-slate-800">{summaryCards?.totalRecords}</p>
          </div>
          
          <div className="bg-emerald-50 p-5 rounded-3xl border border-emerald-100 flex flex-col justify-center">
            <h3 className="text-[9px] font-black text-emerald-600 uppercase tracking-widest mb-1 flex items-center gap-2">Equipped</h3>
            <p className="text-3xl font-black text-emerald-600">{summaryCards?.primaryValue.toLocaleString()}</p>
          </div>

          <div className="bg-amber-50 p-5 rounded-3xl border border-amber-100 flex flex-col justify-center">
            <h3 className="text-[9px] font-black text-amber-600 uppercase tracking-widest mb-1 flex items-center gap-2">Needs Repair</h3>
            <p className="text-3xl font-black text-amber-600">{summaryCards?.issueCount.toLocaleString()}</p>
          </div>

          <div className="bg-rose-50 p-5 rounded-3xl border border-rose-100 flex flex-col justify-center">
            <h3 className="text-[9px] font-black text-rose-600 uppercase tracking-widest mb-1 flex items-center gap-2">Missing</h3>
            <p className="text-3xl font-black text-rose-600">{summaryCards?.noCount.toLocaleString()}</p>
          </div>
        </div>

        {isMultiBinaryMode && multiStats.length > 0 && (
          <div className="bg-indigo-50/50 p-6 rounded-3xl border border-indigo-100 mb-8">
            <h3 className="text-[10px] font-black text-indigo-600 uppercase tracking-widest mb-4">Constituent Metrics Breakdown</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {multiStats.map((ms: any, i: number) => (
                <div key={i} className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
                  <p className="text-[10px] font-bold text-slate-400 uppercase truncate mb-1">{ms.label}</p>
                  <p className="text-2xl font-black text-slate-800">{ms.yes} <span className="text-[10px] text-slate-400 font-bold ml-1">equipped</span></p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 min-h-[400px]">
            <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">Status Distribution (Dataset Wide)</h3>
            <div className="h-72 w-full grid grid-cols-1 md:grid-cols-2 gap-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{fontSize: 9, fill: '#64748b', fontWeight: 700}} />
                  <YAxis tick={{fontSize: 10, fill: '#94a3b8', fontWeight: 700}} />
                  <Tooltip cursor={{fill: 'transparent'}} wrapperClassName="text-xs font-bold shadow-xl border-0" contentStyle={{ borderRadius: '12px', border: 'none' }} />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]} barSize={50}>
                    {barData.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

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
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip wrapperClassName="text-xs font-bold" />
                  <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: '10px', fontWeight: 'bold' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 min-h-[400px]">
            <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">District Impact Analysis</h3>
            <div className="space-y-3">
              {districtBreakdown.length > 0 ? districtBreakdown.map((r: any, i: number) => (
                <div key={i} className="flex items-center justify-between p-3 bg-slate-50 rounded-2xl border border-slate-100/50">
                    <div className="flex flex-col">
                        <span className="text-[10px] font-black text-slate-800 uppercase leading-tight">{r.name}</span>
                        <span className="text-[8px] font-bold text-slate-400 uppercase tracking-wider">{r.total} Schools</span>
                    </div>
                    <div className="flex gap-4">
                        <div className="flex flex-col items-end">
                            {summaryCards?.isBinary ? (
                                <>
                                    <span className="text-xs font-black text-rose-600">{r.no}</span>
                                    <span className="text-[7px] font-bold text-slate-400 uppercase italic">Missing</span>
                                </>
                            ) : (
                                <>
                                    <span className="text-xs font-black text-blue-600">{r.valCount > 0 ? (r.sum / r.valCount).toFixed(3) : "0.000"}</span>
                                    <span className="text-[7px] font-bold text-slate-400 uppercase italic">Avg Value</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>
              )) : (
                <div className="flex flex-col items-center justify-center h-48 text-slate-300">
                    <Info size={24} className="mb-2" />
                    <p className="text-[10px] font-black uppercase tracking-widest">No District Data</p>
                </div>
              )}
            </div>
          </div>

          <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 min-h-[400px]">
            <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">Block Impact Analysis</h3>
            <div className="space-y-3">
              {blockBreakdown.length > 0 ? blockBreakdown.map((r: any, i: number) => (
                <div key={i} className="flex items-center justify-between p-3 bg-indigo-50/30 rounded-2xl border border-indigo-100/30">
                    <div className="flex flex-col">
                        <span className="text-[10px] font-black text-slate-800 uppercase leading-tight">{r.name}</span>
                        <span className="text-[8px] font-bold text-blue-500 uppercase tracking-wider">{r.parent}</span>
                    </div>
                    <div className="flex gap-4">
                        <div className="flex flex-col items-end">
                            {summaryCards?.isBinary ? (
                                <>
                                    <span className="text-xs font-black text-rose-600">{r.no}</span>
                                    <span className="text-[7px] font-bold text-slate-400 uppercase italic">Missing</span>
                                </>
                            ) : (
                                <>
                                    <span className="text-xs font-black text-blue-600">{r.valCount > 0 ? (r.sum / r.valCount).toFixed(3) : "0.000"}</span>
                                    <span className="text-[7px] font-bold text-slate-400 uppercase italic">Avg Value</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>
              )) : (
                <div className="flex flex-col items-center justify-center h-48 text-slate-300">
                    <Info size={24} className="mb-2" />
                    <p className="text-[10px] font-black uppercase tracking-widest">No Block Data</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {prioritySchools.length > 0 && (
          <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
             <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">High Priority Intervention Sites (Schools)</h3>
             <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
               {prioritySchools.map((s: any, i: number) => (
                 <div key={i} className="p-4 rounded-2xl border border-slate-100 bg-slate-50/50 flex flex-col justify-between">
                   <div>
                     <p className="text-[10px] font-black text-slate-800 line-clamp-2 uppercase min-h-[2.5em]">{s.name}</p>
                     <p className="text-[8px] font-bold text-slate-400 uppercase mt-1">{s.block} Block</p>
                   </div>
                   <div className={`text-[10px] font-black uppercase mt-4 ${s.color}`}>
                     {s.status}
                   </div>
                 </div>
               ))}
             </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 bg-blue-600 text-white p-6 rounded-[32px] flex items-center gap-6 shadow-xl relative overflow-hidden group">
                 <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:scale-110 transition-transform duration-700"><CheckCircle size={80} /></div>
                 <div>
                    <h4 className="text-[10px] font-black uppercase tracking-[0.2em] mb-2 opacity-70 italic">Recommendation Engine</h4>
                    <p className="text-sm font-medium leading-relaxed italic">
                        "Spatial analysis suggests immediate prioritization of <b>{districtBreakdown[0]?.name || 'the identified clusters'}</b> to resolve <b>{activeMetric.replace(/_/g, ' ')}</b> gaps, maximizing regional impact indices."
                    </p>
                 </div>
            </div>
            <div className="bg-slate-800 text-white p-6 rounded-[32px] shadow-xl relative overflow-hidden">
                <h4 className="text-[10px] font-black opacity-50 uppercase tracking-widest mb-3">Science Note: KDE</h4>
                <p className="text-[10px] leading-relaxed font-medium opacity-80">
                    The <b>Heatmap</b> visualization utilizes <b>Kernel Density Estimation (KDE)</b> to calculate the relative density of {activeMetric} features across the state.
                </p>
            </div>
        </div>

        {radarData.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
              <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">Infrastructure Fingerprint (State Benchmark)</h3>
              <div className="h-80 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                    <PolarGrid stroke="#e2e8f0" />
                    <PolarAngleAxis dataKey="subject" tick={{fontSize: 8, fontWeight: 700, fill: '#64748b'}} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{fontSize: 8}} />
                    <Radar
                      name="State Average"
                      dataKey="A"
                      stroke="#3b82f6"
                      fill="#3b82f6"
                      fillOpacity={0.6}
                    />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
              <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-6 border-b pb-4">Correlation: ICT vs. Connectivity</h3>
              <div className="h-80 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis type="number" dataKey="x" name="Computers" unit="%" label={{ value: 'Computers %', position: 'bottom', fontSize: 10, fontWeight: 800 }} />
                    <YAxis type="number" dataKey="y" name="Internet" unit="%" label={{ value: 'Internet %', angle: -90, position: 'insideLeft', fontSize: 10, fontWeight: 800 }} />
                    <ZAxis type="number" dataKey="z" range={[50, 400]} name="Schools" />
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                    <Scatter name="Blocks" data={scatterData} fill="#8884d8" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {summaryCards?.isBinary && (
            <div className="bg-slate-900 text-white p-8 rounded-[40px] shadow-2xl relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-64 h-64 bg-blue-600/20 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl group-hover:bg-blue-600/30 transition-all duration-700"></div>
                <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-8 text-center md:text-left">
                    <div className="space-y-2">
                        <h2 className="text-2xl font-black tracking-tight">{summaryCards?.coverage ?? 0}% Coverage Achieved</h2>
                        <p className="text-slate-400 text-sm font-medium">There is currently a <b>{100 - (summaryCards?.coverage ?? 0)}% gap</b> in universal access for {activeMetric.replace(/_/g, ' ')}.</p>
                    </div>
                    <div className="flex gap-6">
                        <div className="flex flex-col">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Equipped</span>
                            <span className="text-2xl font-black text-emerald-400">{summaryCards.primaryValue}</span>
                        </div>
                        <div className="flex flex-col">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Target Gap</span>
                            <span className="text-2xl font-black text-rose-400">{summaryCards.noCount + summaryCards.issueCount}</span>
                        </div>
                    </div>
                </div>
                <div className="absolute bottom-4 right-8 text-[10px] font-black text-white/20 uppercase tracking-[0.3em] pointer-events-none">
                    Email Security: Mocked Mode Active
                </div>
            </div>
        )}
        {summary && (
            <div className="mt-8 bg-blue-50 border border-blue-100 p-8 rounded-[40px] relative overflow-hidden">
                <div className="flex items-start gap-4">
                    <div className="bg-blue-500 p-3 rounded-2xl shadow-lg shadow-blue-200">
                        <Lightbulb className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex-1">
                        <h4 className="text-[10px] font-black text-blue-600 uppercase tracking-widest mb-2">Policy Recommendation</h4>
                        <div className="text-blue-900 leading-relaxed font-medium text-lg whitespace-pre-line">
                            {summary}
                        </div>
                    </div>
                </div>
            </div>
        )}
      </div>
    </div>
  );
}
