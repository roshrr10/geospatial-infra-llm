"use client";

import { useState } from "react";
import { ChevronDown, Layers, Map as MapIcon, Filter, Activity } from "lucide-react";

export type MetricOption = {
    id: string;
    label: string;
    category: "health" | "infra" | "road" | "priority";
};

const METRICS: MetricOption[] = [
    { id: "priority_score", label: "Priority Score (AI)", category: "priority" },
    { id: "electricity", label: "Electricity Availability", category: "infra" },
    { id: "drinking_water", label: "Drinking Water", category: "infra" },
    { id: "computers", label: "Computer Facilities", category: "infra" },
    { id: "ramp", label: "Ramp Accessibility", category: "infra" },
    { id: "avg_road_density", label: "Road Density", category: "road" },
    { id: "total_schools", label: "Total Schools", category: "infra" },
];

interface LayerControlProps {
    activeMetric: string;
    onMetricChange: (metricId: string) => void;
    viewMode: "polygon" | "heatmap";
    onModeChange: (mode: "polygon" | "heatmap") => void;
    adminLevel: "district" | "block" | "school";
    onLevelChange: (level: "district" | "block" | "school") => void;
    dynamicOptions?: {id: string, label: string}[];
}

export default function LayerControl({
    activeMetric,
    onMetricChange,
    viewMode,
    onModeChange,
    adminLevel,
    onLevelChange,
    dynamicOptions
}: LayerControlProps) {
    const [isOpen, setIsOpen] = useState(false);

    const activeMetricLabel = dynamicOptions?.find(m => m.id === activeMetric)?.label || METRICS.find(m => m.id === activeMetric)?.label || "Select Metric";

    return (
        <div className="absolute top-6 right-6 z-[1000] flex flex-col gap-3 items-end">
            {/* Main Control Panel */}
            <div className={`glass rounded-2xl transition-all duration-300 overflow-hidden shadow-2xl ${isOpen ? 'w-64 p-4' : 'w-12 h-12 p-0 flex items-center justify-center cursor-pointer hover:bg-white/80'}`}
                onClick={() => !isOpen && setIsOpen(true)}>

                {!isOpen ? (
                    <Layers className="w-5 h-5 text-slate-600" />
                ) : (
                    <div className="flex flex-col gap-4">
                        <div className="flex justify-between items-center border-b border-slate-200 pb-2">
                            <span className="text-sm font-bold text-slate-800 flex items-center gap-2">
                                <Layers className="w-4 h-4" /> Layers & Metrics
                            </span>
                            <button onClick={(e) => { e.stopPropagation(); setIsOpen(false); }} className="text-slate-400 hover:text-slate-600">
                                <ChevronDown className="w-4 h-4 rotate-180" />
                            </button>
                        </div>

                        {/* Administrative Level Toggle */}
                        <div className="flex flex-col gap-2">
                            <label className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Administrative Level</label>
                            <div className="grid grid-cols-3 bg-slate-100 p-1 rounded-lg">
                                <button
                                    onClick={() => onLevelChange("district")}
                                    className={`py-1 text-xs rounded-md transition-all ${adminLevel === "district" ? 'bg-white shadow-sm text-blue-600 font-bold' : 'text-slate-500 hover:text-slate-700'}`}
                                >
                                    District
                                </button>
                                <button
                                    onClick={() => onLevelChange("block")}
                                    className={`py-1 text-xs rounded-md transition-all ${adminLevel === "block" ? 'bg-white shadow-sm text-blue-600 font-bold' : 'text-slate-500 hover:text-slate-700'}`}
                                >
                                    Block
                                </button>
                                <button
                                    onClick={() => onLevelChange("school")}
                                    className={`py-1 text-xs rounded-md transition-all ${adminLevel === "school" ? 'bg-white shadow-sm text-blue-600 font-bold' : 'text-slate-500 hover:text-slate-700'}`}
                                >
                                    School
                                </button>
                            </div>
                        </div>

                        {/* View Mode Toggle */}
                        <div className="flex flex-col gap-2">
                            <label className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Visualization</label>
                            <div className="grid grid-cols-2 bg-slate-100 p-1 rounded-lg">
                                <button
                                    onClick={() => onModeChange("polygon")}
                                    className={`py-1 text-xs rounded-md transition-all flex items-center justify-center gap-1 ${viewMode === "polygon" ? 'bg-white shadow-sm text-blue-600 font-bold' : 'text-slate-500 hover:text-slate-700'}`}
                                >
                                    <MapIcon className="w-3 h-3" /> Area
                                </button>
                                <button
                                    onClick={() => onModeChange("heatmap")}
                                    className={`py-1 text-xs rounded-md transition-all flex items-center justify-center gap-1 ${viewMode === "heatmap" ? 'bg-white shadow-sm text-blue-600 font-bold' : 'text-slate-500 hover:text-slate-700'}`}
                                >
                                    <Activity className="w-3 h-3" /> Heatmap
                                </button>
                            </div>
                        </div>

                        {/* Metric Selector */}
                        <div className="flex flex-col gap-2">
                            <label className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Metric</label>
                            <div className="flex flex-col gap-1 max-h-56 overflow-y-auto pr-1">
                                {dynamicOptions && dynamicOptions.length > 0 && (
                                    <>
                                        <div className="text-[9px] font-black text-emerald-500 uppercase tracking-widest pl-2 mb-1">Query Matches</div>
                                        {dynamicOptions.map(m => (
                                            <button
                                                key={m.id}
                                                onClick={() => onMetricChange(m.id)}
                                                className={`text-left px-3 py-2 rounded-lg text-xs transition-all ${activeMetric === m.id ? 'bg-emerald-50 text-emerald-700 font-bold border border-emerald-100' : 'hover:bg-slate-50 text-slate-600 border border-transparent'}`}
                                            >
                                                {m.label}
                                            </button>
                                        ))}
                                        <div className="w-full h-px bg-slate-100 my-1"></div>
                                    </>
                                )}
                                <div className="text-[9px] font-black text-slate-400 uppercase tracking-widest pl-2 mb-1">Standard Metrics</div>
                                {METRICS.map((m) => (
                                    <button
                                        key={m.id}
                                        onClick={() => onMetricChange(m.id)}
                                        className={`text-left px-3 py-2 rounded-lg text-xs transition-all ${activeMetric === m.id ? 'bg-blue-50 text-blue-700 font-bold' : 'hover:bg-slate-50 text-slate-600'}`}
                                    >
                                        {m.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
