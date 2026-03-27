"use client";

interface HeatmapLegendProps {
    min: number;
    max: number;
    metricLabel: string;
}

export default function HeatmapLegend({ min, max, metricLabel }: HeatmapLegendProps) {
    if (min === 0 && max === 0) return null;

    return (
        <div className="absolute bottom-6 right-6 z-[1000] glass p-4 rounded-xl flex flex-col gap-2 min-w-[200px] border border-white/20 shadow-2xl">
            <div className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">
                Intensity: {metricLabel.replace(/_/g, ' ')}
            </div>

            <div className="h-3 w-full rounded-full bg-gradient-to-r from-blue-500 via-cyan-400 via-lime-400 via-yellow-400 to-red-500 shadow-inner" />

            <div className="flex justify-between items-center text-[10px] font-black text-slate-600 uppercase mt-1">
                <span>Low Intensity</span>
                <span className="text-slate-900 font-bold">{max.toLocaleString()}</span>
                <span>High Intensity</span>
            </div>

            <p className="text-[9px] text-slate-400/80 leading-tight italic mt-1">
                * Visualizing density and distribution of {metricLabel.toLowerCase().replace(/_/g, ' ')} across the region.
            </p>
        </div>
    );
}
