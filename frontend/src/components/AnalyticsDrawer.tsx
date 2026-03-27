"use client";

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { X, TrendingUp, BarChart3, PieChartIcon, Lightbulb, Download, Target, MapPin, Navigation } from 'lucide-react';

interface AnalyticsDrawerProps {
    data: any[];
    isOpen: boolean;
    onClose: () => void;
    title: string;
    summary?: string;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

// Sub-component to handle nearest facility logic to keep state localized
function NearestFacilityButton({ facility, udiseCode }: { facility: string, udiseCode: string }) {
    const [nearest, setNearest] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(false);

    const findNearest = async () => {
        setLoading(true);
        setError(false);
        try {
            const res = await fetch(`http://127.0.0.1:8000/nearest/${facility}/${udiseCode}`);
            if (!res.ok) throw new Error();
            const json = await res.json();
            if (json.data && json.data.length > 0) {
                setNearest(json.data[0]);
            } else {
                setNearest('none');
            }
        } catch {
            setError(true);
        } finally {
            setLoading(false);
        }
    };

    if (nearest === 'none') return <div className="px-4 py-2 bg-slate-50 text-[10px] text-slate-500 font-bold border-t border-slate-100">No nearby facility found.</div>;
    if (error) return <div className="px-4 py-2 bg-rose-50 text-[10px] text-rose-500 font-bold border-t border-rose-100">Failed to find nearest.</div>;

    if (nearest) {
        return (
            <div className="px-4 py-2 bg-blue-50 border-t border-blue-100 flex items-center justify-between">
                <div className="flex items-center gap-1.5 min-w-0 pr-2">
                    <Navigation size={12} className="text-blue-500 shrink-0" />
                    <p className="text-[10px] font-bold text-blue-700 truncate">Nearest: {nearest.schoolName}</p>
                </div>
                <span className="text-[10px] font-black text-blue-600 bg-blue-100 px-2 py-0.5 rounded-full shrink-0">{nearest.distance_km} km</span>
            </div>
        );
    }

    return (
        <button
            onClick={findNearest}
            disabled={loading}
            className="w-full px-4 py-2 bg-slate-50 hover:bg-slate-100 text-[10px] font-bold text-slate-500 transition-colors border-t border-slate-100 flex items-center justify-center gap-1 disabled:opacity-50"
        >
            <MapPin size={12} />
            {loading ? 'Searching...' : 'Find Nearest Alternative'}
        </button>
    );
}

// Sub-component for side-by-side Natural Language Comparison
function ComparisonResults({ data, entityType }: { data: any[], entityType: string }) {
    const [compData, setCompData] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    React.useEffect(() => {
        const fetchCompare = async () => {
            setLoading(true);
            try {
                const nameKey = entityType === 'Districts' ? 'district_name' : 'block_name';
                const level = entityType === 'Districts' ? 'district' : 'block';
                const name1 = data[0][nameKey];
                const name2 = data[1][nameKey];

                if (!name1 || !name2) return;

                const res = await fetch(`http://127.0.0.1:8000/compare/${level}/${encodeURIComponent(name1)}/${encodeURIComponent(name2)}`);
                if (res.ok) {
                    const json = await res.json();
                    setCompData(json.data);
                }
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        };
        fetchCompare();
    }, [data, entityType]);

    if (loading) return <div className="p-8 text-center text-xs font-bold text-slate-400 animate-pulse">Running Comparative Analysis...</div>;
    if (!compData || !compData.comparison || compData.comparison.length === 0) return null;

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2">
                <Target size={18} className="text-slate-400" />
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Head-to-Head Comparison</h3>
            </div>

            <div className="flex justify-between items-center px-4 py-3 bg-slate-800 text-white rounded-t-2xl">
                <p className="font-bold flex-1 text-center truncate">{compData.name1}</p>
                <div className="px-3 py-1 bg-slate-700 rounded-full text-[10px] font-black tracking-widest uppercase mx-2">VS</div>
                <p className="font-bold flex-1 text-center truncate">{compData.name2}</p>
            </div>

            <div className="bg-white/50 border border-slate-100 rounded-b-2xl overflow-hidden space-y-[1px] bg-slate-100">
                {compData.comparison.map((c: any, i: number) => {
                    const is1Winner = c.winner === compData.name1;
                    const is2Winner = c.winner === compData.name2;
                    const diffStr = c.diff > 0 ? `+${c.diff}` : c.diff;
                    return (
                        <div key={i} className="flex bg-white items-center py-3 px-2 transition-colors hover:bg-slate-50">
                            <div className={`flex-1 text-center text-sm font-black ${is1Winner ? 'text-emerald-600' : 'text-slate-400'}`}>
                                {c.region1}
                            </div>
                            <div className="w-1/2 px-2 flex flex-col items-center justify-center text-center">
                                <p className="text-[9px] font-bold text-slate-400 uppercase leading-tight">{c.metric}</p>
                                <p className="text-[8px] font-black text-slate-300 mt-0.5 tracking-widest">DIFF: {diffStr}</p>
                            </div>
                            <div className={`flex-1 text-center text-sm font-black ${is2Winner ? 'text-emerald-600' : 'text-slate-400'}`}>
                                {c.region2}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}


export default function AnalyticsDrawer({ data, isOpen, onClose, title, summary }: AnalyticsDrawerProps) {
    const [isExporting, setIsExporting] = useState(false);
    if (!data || data.length === 0) return null;

    // Collect keys from first 100 rows (handles sparse data where some keys are NULL in early rows)
    const allKeysSet = new Set<string>();
    data.slice(0, 100).forEach((row: any) => Object.keys(row).forEach(k => allKeysSet.add(k)));
    const keys = Array.from(allKeysSet);
    
    const skipKeywords = [
        'id', 'code', 'udise', 'sl_no', 'serial', 'index', 'pinc', 'pincode',
        'mobi', 'phone', 'latitude', 'longitude', 'geometry', 'accuracy', 'altitude',
        'class', 'grade', 'year', 'month', 'boundary', 'shape'
    ];

    const numericKeys = keys.filter(key => {
        const k = key.toLowerCase();
        if (skipKeywords.some(skip => k.includes(skip))) return false;

        // Force include infrastructure binary fields
        const infraKeywords = ['solar', 'panel', 'electricity', 'water', 'toilet', 'computer', 'facility', 'internet', 'smart', 'ramp', 'playground', 'available', 'connection', 'provided'];
        if (infraKeywords.some(ik => k.includes(ik))) return true;

        // Check first 50 rows for data type
        return data.slice(0, 50).some(row => {
            const val = row[key];
            if (typeof val === 'number') return true;
            if (typeof val === 'string' && val.trim() !== '' && !isNaN(Number(val))) return true;
            return false;
        });
    }).sort((a, b) => {
        const score = (k: string) => {
            const kl = k.toLowerCase();
            if (kl.includes('solar') || kl.includes('panel')) return 200;
            if (kl.includes('electricity') || kl.includes('eletricity')) return 150;
            if (kl.includes('water') || kl.includes('computer')) return 140;
            if (kl.includes('available') || kl.includes('facility') || kl.includes('connection')) return 130;
            if (kl.includes('class') || kl.includes('grade')) return -100;
            return 0;
        };
        return score(b) - score(a);
    });

    const labelKey =
        keys.find(k => k.toLowerCase() === 'schoolname' || k.toLowerCase() === 'school_name' || k.toLowerCase() === 'schname') ||
        keys.find(k => k.toLowerCase() === 'block_name') ||
        keys.find(k => k.toLowerCase() === 'district_name') ||
        keys.find(k => k.toLowerCase().includes('name') && !k.toLowerCase().includes('udise')) ||
        keys[0];

    const chartData = data.slice(0, 10).map(item => ({
        name: item[labelKey],
        ...item
    }));

    // Helper for robust binary checking mirroring backend logic
    const checkVal = (val: any, target: 'yes' | 'no' | 'issue') => {
        if (val === null || val === undefined) return false;
        const v = String(val).toLowerCase().trim();
        if (v === '' || v === 'n/a' || v === 'null' || v === 'nan') return false;

        if (target === 'yes') {
            return val === 1 || val === 1.0 || v === '1' || v === '1.0' || ['yes', 'true', 'functional', 'satisfactory', 'available', 'provided'].includes(v);
        }
        if (target === 'no') {
            return val === 0 || val === 0.0 || v === '0' || v === '0.0' || ['no', 'false', 'not functional', 'unavailable', 'none'].includes(v);
        }
        if (target === 'issue') {
            return val === 2 || val === 2.0 || v === '2' || v.includes('issue') || v.includes('partial') || v.includes('repair');
        }
        return false;
    };

    // Detect if the primary metric is binary (0, 1, 2 or Yes/No)
    const primaryKey = numericKeys[0] || labelKey; // Fallback to labelKey if no numeric metric found
    const isBinaryField = primaryKey && (
        primaryKey.toLowerCase().includes('solar') ||
        primaryKey.toLowerCase().includes('panel') ||
        primaryKey.toLowerCase().includes('electricity') ||
        primaryKey.toLowerCase().includes('eletricity') ||
        primaryKey.toLowerCase().includes('available') ||
        primaryKey.toLowerCase().includes('connection') ||
        primaryKey.toLowerCase().includes('facility') ||
        primaryKey.toLowerCase().includes('provided') ||
        data.slice(0, 100).every(d => {
            const val = d[primaryKey];
            return checkVal(val, 'yes') || checkVal(val, 'no') || checkVal(val, 'issue') || val === null || val === undefined;
        })
    );

    const binaryStats = isBinaryField ? {
        yes: data.filter(d => checkVal(d[primaryKey], 'yes')).length,
        no: data.filter(d => checkVal(d[primaryKey], 'no')).length,
        issue: data.filter(d => checkVal(d[primaryKey], 'issue')).length,
        total: data.length
    } : null;

    // Detect entity type from the data
    const multiBinaryKeys = numericKeys.filter(k => k !== 'All Selected Facilities' && data.slice(0, 100).every(d => checkVal(d[k], 'yes') || checkVal(d[k], 'no') || checkVal(d[k], 'issue') || d[k] == null));
    const isMultiBinaryMode = multiBinaryKeys.length > 1;

    const multiStats = isMultiBinaryMode ? multiBinaryKeys.map(k => ({
        key: k,
        label: k.replace(/_/g, ' '),
        yes: data.filter(d => checkVal(d[k], 'yes')).length
    })) : [];

    const hasSchool = keys.some(k => k.toLowerCase().includes('schoolname') || k.toLowerCase() === 'school_name');
    const hasBlock = keys.some(k => k.toLowerCase() === 'block_name');
    const hasDistrict = keys.some(k => k.toLowerCase() === 'district_name');
    const entityType = hasSchool ? 'Schools' : hasBlock ? 'Blocks' : hasDistrict ? 'Districts' : 'Records';

    // Check if it's a comparative query (exactly 2 districts or blocks)
    const isComparisonQuery = data.length === 2 && (hasDistrict || hasBlock) && !hasSchool;

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial={{ x: "100%" }}
                    animate={{ x: 0 }}
                    exit={{ x: "100%" }}
                    transition={{ type: "spring", damping: 25, stiffness: 200 }}
                    className="fixed right-0 top-0 h-full w-[500px] glass z-[9999] shadow-2xl flex flex-col p-6 overflow-y-auto"
                >
                    <div className="flex items-center justify-between mb-8">
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">{title}</h2>
                            <p className="text-sm text-slate-500">Visual Insights & Trends</p>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-slate-200 rounded-full transition-colors"
                        >
                            <X size={20} />
                        </button>
                    </div>

                    <div className="space-y-8">
                        {/* Comparison Results (Side-by-side NLQ) */}
                        {isComparisonQuery && <ComparisonResults data={data} entityType={entityType} />}

                        {/* Summary Cards */}
                        {!isComparisonQuery && (
                            <div className="grid grid-cols-2 gap-4">
                                <div className="p-4 bg-blue-50 rounded-2xl border border-blue-100">
                                    <p className="text-[10px] font-bold text-blue-600 uppercase tracking-widest mb-1 flex items-center gap-1">
                                        <TrendingUp size={12} /> Total {entityType}
                                    </p>
                                    <p className="text-2xl font-black text-blue-900">{data.length}</p>
                                </div>
                                <div className="p-4 bg-emerald-50 rounded-2xl border border-emerald-100">
                                    <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-widest mb-1 flex items-center gap-1">
                                        <Lightbulb size={12} /> Metric
                                    </p>
                                    <p className="text-lg font-black text-emerald-900 capitalize">
                                        {primaryKey ? primaryKey.replace(/_/g, ' ') : 'N/A'}
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Status Cards for Binary Metrics - always show full breakdown */}
                        {isBinaryField && binaryStats && (
                            <div className="space-y-4">
                                <div className="flex items-center gap-2">
                                    <BarChart3 size={18} className="text-slate-400" />
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Status Breakdown</h3>
                                </div>
                                
                                {isMultiBinaryMode && (
                                    <div className="mb-4 space-y-3 bg-indigo-50/50 p-4 rounded-2xl border border-indigo-100">
                                        <p className="text-[10px] font-black text-indigo-600 uppercase tracking-widest shadow-sm">All Requirements Met (Both)</p>
                                        <div className="flex items-center gap-4">
                                            <p className="text-3xl font-black text-indigo-900">{data.filter(d => checkVal(d['All Selected Facilities'], 'yes')).length}</p>
                                            <p className="text-xs font-bold text-indigo-500">schools have all selected facilities.</p>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2 mt-2">
                                            {multiStats.map((ms, i) => (
                                                <div key={i} className="p-3 bg-white rounded-xl shadow-sm flex flex-col">
                                                    <p className="text-[9px] font-black text-slate-500 uppercase truncate">{ms.label}</p>
                                                    <p className="text-lg font-black text-slate-800">{ms.yes} <span className="text-[10px] text-slate-400 font-bold ml-1">fully equipped</span></p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {(() => {
                                    // Dynamic labels based on the metric name
                                    const ml = primaryKey.toLowerCase();
                                    let yesLabel = 'Available';
                                    let noLabel = 'Not Available';
                                    let issueLabel = 'Functional Issue';
                                    if (ml.includes('solar') || ml.includes('panel')) {
                                        yesLabel = 'With Solar Panel';
                                        noLabel = 'Without Solar Panel';
                                        issueLabel = 'Panel Issue';
                                    } else if (ml.includes('electricity') || ml.includes('eletricity') || ml.includes('connection')) {
                                        yesLabel = 'With Electricity';
                                        noLabel = 'Without Electricity';
                                        issueLabel = 'Connection Issue';
                                    } else if (ml.includes('water') || ml.includes('drinking')) {
                                        yesLabel = 'Water Available';
                                        noLabel = 'No Water';
                                        issueLabel = 'Water Issue';
                                    } else if (ml.includes('toilet')) {
                                        yesLabel = 'Toilet Available';
                                        noLabel = 'No Toilet';
                                        issueLabel = 'Toilet Issue';
                                    } else if (ml.includes('library')) {
                                        yesLabel = 'Has Library';
                                        noLabel = 'No Library';
                                        issueLabel = 'Library Issue';
                                    } else if (ml.includes('computer') || ml.includes('ict')) {
                                        yesLabel = 'Has Computers';
                                        noLabel = 'No Computers';
                                        issueLabel = 'Lab Issue';
                                    } else if (ml.includes('internet')) {
                                        yesLabel = 'Internet Available';
                                        noLabel = 'No Internet';
                                        issueLabel = 'Connection Issue';
                                    } else if (ml.includes('ramp')) {
                                        yesLabel = 'Ramp Available';
                                        noLabel = 'No Ramp';
                                        issueLabel = 'Ramp Issue';
                                    } else if (ml.includes('playground')) {
                                        yesLabel = 'Has Playground';
                                        noLabel = 'No Playground';
                                        issueLabel = 'Playground Issue';
                                    }
                                    return (
                                        <div className="grid grid-cols-3 gap-3">
                                            <div className="p-4 bg-emerald-50 rounded-2xl border border-emerald-100 flex flex-col items-center text-center">
                                                <p className="text-[9px] font-bold text-emerald-600 uppercase mb-1 leading-tight">{yesLabel}</p>
                                                <p className="text-xl font-black text-emerald-900">{binaryStats.yes}</p>
                                                <p className="text-[10px] text-emerald-500">({binaryStats.total > 0 ? ((binaryStats.yes / binaryStats.total) * 100).toFixed(1) : 0}%)</p>
                                            </div>
                                            <div className="p-4 bg-rose-50 rounded-2xl border border-rose-100 flex flex-col items-center text-center">
                                                <p className="text-[9px] font-bold text-rose-600 uppercase mb-1 leading-tight">{noLabel}</p>
                                                <p className="text-xl font-black text-rose-900">{binaryStats.no}</p>
                                                <p className="text-[10px] text-rose-500">({binaryStats.total > 0 ? ((binaryStats.no / binaryStats.total) * 100).toFixed(1) : 0}%)</p>
                                            </div>
                                            <div className="p-4 bg-amber-50 rounded-2xl border border-amber-100 flex flex-col items-center text-center">
                                                <p className="text-[9px] font-bold text-amber-600 uppercase mb-1 leading-tight">{issueLabel}</p>
                                                <p className="text-xl font-black text-amber-900">{binaryStats.issue}</p>
                                                <p className="text-[10px] text-amber-500">({binaryStats.total > 0 ? ((binaryStats.issue / binaryStats.total) * 100).toFixed(1) : 0}%)</p>
                                            </div>
                                        </div>
                                    );
                                })()}
                            </div>
                        )}

                        {/* Gap Analysis Card */}
                        {isBinaryField && binaryStats && binaryStats.no > 0 && (
                            <div className="p-5 bg-gradient-to-br from-indigo-50 to-violet-50 rounded-2xl border border-indigo-100">
                                <div className="flex items-center gap-2 mb-3">
                                    <Target size={18} className="text-indigo-500" />
                                    <h3 className="text-xs font-bold text-indigo-500 uppercase tracking-widest">Coverage Gap Analysis</h3>
                                </div>
                                <p className="text-sm text-slate-700 mb-3">
                                    <span className="text-2xl font-black text-indigo-700">{binaryStats.no + binaryStats.issue}</span>
                                    <span className="ml-1">more schools need <span className="font-bold">{primaryKey.replace(/_/g, ' ')}</span> to reach <span className="font-black text-indigo-700">100% coverage</span></span>
                                </p>
                                {/* Progress bar */}
                                <div className="w-full bg-indigo-100 rounded-full h-3 overflow-hidden">
                                    <div
                                        className="bg-gradient-to-r from-indigo-500 to-violet-500 h-3 rounded-full transition-all duration-700"
                                        style={{ width: `${binaryStats.total > 0 ? (binaryStats.yes / binaryStats.total * 100) : 0}%` }}
                                    />
                                </div>
                                <p className="text-[10px] text-indigo-400 mt-2 font-bold">
                                    Current coverage: {binaryStats.total > 0 ? (binaryStats.yes / binaryStats.total * 100).toFixed(1) : 0}%
                                </p>
                            </div>
                        )}

                        {/* Bar Chart (Only for non-binary or secondary metrics) */}
                        {numericKeys.length > 0 && !isBinaryField && (
                            <div className="space-y-4">
                                <div className="flex items-center gap-2">
                                    <BarChart3 size={18} className="text-slate-400" />
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Comparison (Top 10)</h3>
                                </div>
                                <div className="h-[250px] w-full bg-white/50 p-4 rounded-2xl border border-slate-100">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={chartData}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                            <XAxis
                                                dataKey="name"
                                                fontSize={10}
                                                tickLine={false}
                                                axisLine={false}
                                                interval={0}
                                                angle={-45}
                                                textAnchor="end"
                                                height={60}
                                            />
                                            <YAxis fontSize={10} tickLine={false} axisLine={false} />
                                            <Tooltip
                                                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }}
                                            />
                                            <Bar dataKey={numericKeys[0]} fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        )}

                        {/* Data Table Preview */}
                        {primaryKey && (
                            <div className="space-y-4 pb-12">
                                <div className="flex items-center gap-2">
                                    <PieChartIcon size={18} className="text-slate-400" />
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Detailed Breakdown</h3>
                                </div>
                                <div className="space-y-2">
                                    {data.slice(0, 30).map((item, i) => {
                                        const val = item[primaryKey];
                                        let displayVal = val;
                                        const isPositive = checkVal(val, 'yes');
                                        const isNegative = checkVal(val, 'no');
                                        const isIssue = checkVal(val, 'issue');

                                        if (isBinaryField) {
                                            if (isPositive) displayVal = "Yes";
                                            else if (isNegative) displayVal = "No";
                                            else if (isIssue) displayVal = "Issue";
                                        } else if (typeof val === 'number') {
                                            displayVal = val.toLocaleString();
                                        }

                                        const borderColor = isBinaryField
                                            ? (isPositive ? 'border-l-emerald-500' : isIssue ? 'border-l-amber-500' : 'border-l-rose-500')
                                            : 'border-l-blue-500';
                                        const badgeColor = isBinaryField
                                            ? (isPositive ? 'bg-emerald-100 text-emerald-700' : isIssue ? 'bg-amber-100 text-amber-700' : 'bg-rose-100 text-rose-700')
                                            : 'bg-blue-100 text-blue-700';

                                        // Only show Find Nearest button for schools that lack the facility and have a valid UDISE
                                        let udise = item.udiseCode || item.udisecode || item.udise_num || item.udise_code;
                                        if (!udise && String(item.id).length > 6) udise = item.id; // Fallback only if item.id looks like a UDISE (e.g. 11 digits)
                                        const canFindNearest = isBinaryField && (isNegative || isIssue) && udise;

                                        return (
                                            <div key={i} className={`flex flex-col bg-white/50 rounded-xl border border-slate-100 border-l-4 ${borderColor} overflow-hidden`}>
                                                <div className="px-4 py-3 flex justify-between items-center">
                                                    <div className="flex-1 min-w-0 mr-3">
                                                        <p className="text-sm font-bold text-slate-800 truncate">{item[labelKey]}</p>
                                                        <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest mt-0.5">{primaryKey.replace(/_/g, ' ')}</p>
                                                    </div>
                                                    <span className={`px-3 py-1 rounded-full text-xs font-black shrink-0 ${badgeColor}`}>
                                                        {displayVal}
                                                    </span>
                                                </div>

                                                {canFindNearest && (
                                                    <NearestFacilityButton facility={primaryKey} udiseCode={udise} />
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}

                        {/* PDF Export Button */}
                        <div className="pb-6">
                            <button
                                onClick={async () => {
                                    setIsExporting(true);
                                    try {
                                        const res = await fetch('http://127.0.0.1:8000/report', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({
                                                metric: primaryKey || 'general',
                                                data: data,
                                                summary: summary || title
                                            })
                                        });
                                        if (!res.ok) throw new Error('Export failed');
                                        const blob = await res.blob();
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = `GeoAI_Report_${primaryKey || 'analysis'}.pdf`;
                                        document.body.appendChild(a);
                                        a.click();
                                        document.body.removeChild(a);
                                        URL.revokeObjectURL(url);
                                    } catch (err) {
                                        console.error('PDF Export failed:', err);
                                    } finally {
                                        setIsExporting(false);
                                    }
                                }}
                                disabled={isExporting}
                                className="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold rounded-2xl flex items-center justify-center gap-2 hover:from-blue-700 hover:to-indigo-700 transition-all shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <Download size={16} />
                                {isExporting ? 'Generating Report...' : 'Download PDF Report'}
                            </button>
                        </div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
