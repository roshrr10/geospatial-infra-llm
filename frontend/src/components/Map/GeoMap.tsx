"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";
import { BarChart2, Filter, Layers, Map as MapIcon, Compass, Sparkles } from "lucide-react";

// Fix for default marker icons in Leaflet + Next.js
const fixIcon = () => {
    // @ts-ignore
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png",
    });
};

interface GeoMapProps {
    geojson?: any;
    basemap?: any;
    currentLevel: "district" | "block" | "school";
    onLevelChange: (level: "district" | "block" | "school") => void;
    onFeatureClick?: (level: string, name: string) => void;
    heatmapData?: [number, number, number][];
    activeMetric?: string;
    searchQuery?: string;
    initialFilterIntent?: 'all' | 'yes' | 'no' | 'issue';
    viewMode: "polygon" | "map" | "dashboard" | "heatmap";
    apiResult?: any;
}

export default function GeoMap({ geojson, basemap, currentLevel, onLevelChange, onFeatureClick, heatmapData, activeMetric, searchQuery, initialFilterIntent, viewMode, apiResult }: GeoMapProps) {
    const mapRef = useRef<L.Map | null>(null);
    const geojsonLayerRef = useRef<L.GeoJSON | null>(null);
    const basemapLayerRef = useRef<L.GeoJSON | null>(null);
    const heatLayerRef = useRef<any>(null);

    const [filterMode, setFilterMode] = useState<'all' | 'yes' | 'no' | 'issue'>('all');
    const [legendConfig, setLegendConfig] = useState<any>(null);
    
    // Refs for analytical context (solves stale closures in Leaflet events)
    const apiResultRef = useRef(apiResult);
    const gMetricRef = useRef<string | null>(null);
    const mMinRef = useRef(0);
    const mMaxRef = useRef(100);
    const activeMetricRef = useRef(activeMetric);
    const viewModeRef = useRef(viewMode);
    const regionCountsRef = useRef<Record<string, number>>({});
    
    // Core boolean logic for infrastructure status
    const isPos = (v: any, key?: string) => {
        const val = Number(v);
        // Special case for 'no_of_computer' count vs existence
        if (key?.toLowerCase().includes('computer') && !key?.toLowerCase().includes('available')) return val > 0;
        return (val === 1 || String(v).toLowerCase().trim() === 'yes') && val !== 2;
    };
    
    const isNeg = (v: any, key?: string) => {
        const val = Number(v);
        if (key?.toLowerCase().includes('computer') && !key?.toLowerCase().includes('available')) return val === 0 || v === null;
        return val === 0 || v === null || v === undefined || String(v).toLowerCase().trim() === 'no';
    };
    
    const isIssue = (v: any, key?: string) => {
        const val = Number(v);
        if (key?.toLowerCase().includes('computer') && !key?.toLowerCase().includes('available')) return false;
        return val === 2 || String(v).toLowerCase().includes('issue') || String(v).toLowerCase().includes('partial');
    };

    // Extracted filter logic so it can be used for aggregating region clusters dynamically
    const checkFeatureFilter = (feature: any, currentFilterMode: string, currentQueryMode: string, currentRelevantCols: string[], currActiveMetric?: string) => {
        if (!currentFilterMode || currentFilterMode === 'all') return true;
        const props = feature?.properties || {};
        
        if (currentQueryMode === 'multi_binary') {
            const score = currentRelevantCols.filter(k => isPos(props[k], k)).length;
            const issues = currentRelevantCols.filter(k => isIssue(props[k], k)).length;
            if (currentFilterMode === 'yes') return score === currentRelevantCols.length;
            if (currentFilterMode === 'no') return score === 0 && issues === 0;
            if (currentFilterMode === 'issue') return issues > 0 || (score > 0 && score < currentRelevantCols.length);
        } else {
            const col = currActiveMetric || currentRelevantCols[0];
            if (!col) return false; // Strict: Hide when filter active but no col found
            if (currentFilterMode === 'yes') return isPos(props[col], col);
            if (currentFilterMode === 'no') return isNeg(props[col], col);
            if (currentFilterMode === 'issue') return isIssue(props[col], col);
        }
        return false;
    };
    
    useEffect(() => { 
        apiResultRef.current = apiResult; 
        activeMetricRef.current = activeMetric;
        viewModeRef.current = viewMode;
    }, [apiResult, activeMetric, viewMode]);

    const normalizeName = (name: any) => {
        if (!name) return '';
        return name.toString()
            .toLowerCase()
            .replace(/\b(district|block|subdivision|hq|sub|the|development|state|union)\b/g, '')
            .replace(/[^a-z0-9]/g, '')
            .trim();
    };

    // --- DATA & INFRASTRUCTURE DETECTION ---
    const { 
        relevantInfraCols, 
        gradientMetric, 
        metricMin, 
        metricMax,
        queryMode
    } = useMemo(() => {
        const bKeys = ['electricity', 'water', 'library', 'computer', 'playground', 'ramp', 'internet', 'smart', 'classroom', 'toilet', 'solar', 'handwash', 'uniforms', 'text_books', 'extinguisher', 'provided', 'available'];
        const sKeys = new Set([
            'geometry', 'id', 'display_name', 'udise_code', 'udise_num', 'udisecode',
            'sl_no', 'schname', 'school_name', 'schoolName', 'schoolname',
            'block_name', 'district_name', 'cluster_name', 'village_name',
            'school_management', 'school_category', 'schlocation', 'schtype',
            'pincode', 'pinc', 'serial', 'index', 'code', 'longitude', 'latitude',
            'villageid', 'village_id', 'vcode', 'v_id', 'village_code',
            'blockid', 'block_id', 'districtid', 'district_id', 'stateid', 'state_id',
            'st_asgeojson', 'centroid', 'geom', '?column?'
        ]);

        let infraCols: string[] = [];
        let gMetric: string | null = null;
        let min = Infinity;
        let max = -Infinity;
        let finalMode: 'multi_binary' | 'single_binary' | 'metric' | 'default' = 'default';

        // Prioritize keys from the API query result over the background basemap properties
        const dataKeys = (apiResult?.table?.[0] ? Object.keys(apiResult.table[0]) : [])
            .concat(geojson?.features?.[0]?.properties ? Object.keys(geojson.features[0].properties) : []);
        const keys = Array.from(new Set(dataKeys));

        const isBinaryCol = (k: string) => bKeys.some(bk => k.toLowerCase().includes(bk)) && !sKeys.has(k.toLowerCase());
        infraCols = keys.filter(isBinaryCol);

        const countKeywords = ['total', 'count', 'density', 'num', 'per_sqkm', 'avg_'];
        const isCountCol = (k: string) => countKeywords.some(ck => k.toLowerCase().includes(ck)) && !sKeys.has(k.toLowerCase());
        
        // Metric Selection Logic
        if (activeMetric && !isBinaryCol(activeMetric) && !sKeys.has(activeMetric.toLowerCase())) {
            gMetric = activeMetric;
        } else if (!activeMetric) {
            for (const key of keys) {
                if (sKeys.has(key.toLowerCase())) continue;
                if (isCountCol(key)) { gMetric = key; break; }
            }
        }

        // Min/Max for Gradient
        const targetMetric = gMetric || activeMetric;
        // Scan query data first, then fall back to basemap features for min/max
        const dataSources = [
            (geojson?.features as any[]),
            apiResult?.table,
            (basemap?.features as any[])
        ];
        if (targetMetric) {
            for (const source of dataSources) {
                if (!source) continue;
                for (const item of source) {
                    const props = item.properties || item;
                    const val = parseFloat(props[targetMetric]);
                    if (!isNaN(val)) {
                        min = Math.min(min, val);
                        max = Math.max(max, val);
                    }
                }
            }
        }

        if (activeMetric && gMetric === activeMetric) finalMode = 'metric';
        else if (activeMetric && isBinaryCol(activeMetric)) finalMode = 'single_binary';
        else if (infraCols.length > 1) finalMode = 'multi_binary';
        else if (infraCols.length === 1) finalMode = 'single_binary';
        else if (gMetric) finalMode = 'metric';

        return { 
            relevantInfraCols: infraCols, 
            gradientMetric: gMetric,
            metricMin: min === Infinity ? 0 : min,
            metricMax: max === -Infinity ? 100 : max,
            queryMode: finalMode
        };
    }, [geojson, basemap, activeMetric, apiResult]);

    useEffect(() => {
        if (initialFilterIntent) setFilterMode(initialFilterIntent);
        else setFilterMode('all');
    }, [geojson, initialFilterIntent]);

    // Calculate dynamic region densities (for shading blocks/districts behind school points)
    const regionCounts = useMemo(() => {
        const counts: Record<string, number> = {};
        if (!geojson?.features) return counts;
        
        let maxCount = 0;
        geojson.features.forEach((feature: any) => {
            if (checkFeatureFilter(feature, filterMode, queryMode, relevantInfraCols, activeMetric)) {
                const props = feature.properties || {};
                const bName = normalizeName(props.block_name);
                const dName = normalizeName(props.district_name);
                if (bName) { counts[bName] = (counts[bName] || 0) + 1; maxCount = Math.max(maxCount, counts[bName]); }
                if (dName) { counts[dName] = (counts[dName] || 0) + 1; maxCount = Math.max(maxCount, counts[dName]); }
            }
        });
        counts['_max'] = maxCount === 0 ? 1 : maxCount; // prevent div by zero
        return counts;
    }, [geojson, filterMode, queryMode, relevantInfraCols, activeMetric]);

    useEffect(() => {
        regionCountsRef.current = regionCounts;
    }, [regionCounts]);

    useEffect(() => {
        fixIcon();
        if (!mapRef.current) {
            mapRef.current = L.map("map-container", {
                center: [25.5, 91.3],
                zoom: 8,
                zoomControl: false,
                preferCanvas: true,
                layers: [
                    L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png", {
                        attribution: '&copy; CARTO'
                    })
                ]
            });
            L.control.zoom({ position: 'bottomright' }).addTo(mapRef.current);

            // Create high-visibility panes for layering control
            const polygonsPane = mapRef.current.createPane('polygons');
            polygonsPane.style.zIndex = '450';
            polygonsPane.style.pointerEvents = 'auto';

            const schoolsPane = mapRef.current.createPane('schools');
            schoolsPane.style.zIndex = '500';
            schoolsPane.style.pointerEvents = 'auto'; // Interactive dots
        }

        const map = mapRef.current;

        // --- REFS SYNC FOR STYLE FACTORY ---
        gMetricRef.current = gradientMetric;
        mMinRef.current = metricMin;
        mMaxRef.current = metricMax;

        const getChoroplethStyle = (feature: any) => {
            // 1. Isolation: Hide EVERYTHING in Heatmap Mode
            if (viewMode === 'heatmap') {
                return { fillOpacity: 0, weight: 0, opacity: 0, color: 'transparent', interactive: false };
            }

            const defaultStyle = { color: "#3b82f6", weight: 1.5, fillOpacity: 0.1, fillColor: "#bae6fd", interactive: true };
            const nName = normalizeName(feature.properties?.block_name || feature.properties?.district_name || feature.properties?.NAME || feature.properties?.name);

            const rCount = regionCountsRef.current?.[nName];
            const maxRCount = regionCountsRef.current?.['_max'] || 1;
            const currentGMetric = gMetricRef.current;
            
            // DYNAMIC AGGREGATION CHOROPLETH: Shade block/district by density of matched schools over it 
            if (rCount !== undefined && rCount > 0 && (!currentGMetric && viewModeRef.current !== 'heatmap')) {
                const ratio = rCount / maxRCount;
                const r = Math.round(240 - ratio * 220); // 240 -> 20
                const g = Math.round(249 - ratio * 150); // 249 -> 99
                const b = Math.round(255 - ratio * 100); // 255 -> 155
                return { color: "white", weight: 2, fillOpacity: 0.85, fillColor: `rgb(${r},${g},${b})`, interactive: true };
            }

            const currentTable = apiResultRef.current?.table;
            const currentMin = mMinRef.current;
            const currentMax = mMaxRef.current;
            const targetMetric = currentGMetric || activeMetricRef.current;

            let val: number | undefined;

            if (currentTable && nName) {
                // Find matching record aggressively
                const record = currentTable.find((r: any) => {
                    return Object.values(r).some(v => {
                        const sVal = normalizeName(String(v));
                        return sVal === nName || sVal.includes(nName) || nName.includes(sVal);
                    });
                });

                if (record && targetMetric) {
                    val = parseFloat(record[targetMetric as string]);
                }
            }
            
            // If the record wasn't found in an active query table, look for the data native to the GeoJSON basemap!
            if (val === undefined || isNaN(val)) {
                if (targetMetric && feature.properties?.[targetMetric as string] !== undefined) {
                    val = parseFloat(feature.properties[targetMetric as string]);
                }
            }

            if (val !== undefined && !isNaN(val)) {
                const range = currentMax - currentMin;
                const ratio = range > 0 ? Math.min(1, Math.max(0, (val - currentMin) / range)) : (val > 0 ? 1 : 0);
                
                // Ultra-Vibrant High Contrast Palette
                const r = Math.round(180 - ratio * 160); // 180 -> 20
                const g = Math.round(200 - ratio * 150); // 200 -> 50
                const b = Math.round(255 - ratio * 100); // 255 -> 155
                return { color: "white", weight: 2, fillOpacity: 0.95, fillColor: `rgb(${r},${g},${b})`, interactive: true };
            }

            return defaultStyle;
        };

        // 1. Ensure map panes exist for layering control
        if (!map.getPane('polygons')) {
            map.createPane('polygons');
            const pane = map.getPane('polygons');
            if (pane) pane.style.zIndex = '450';
        }
        if (!map.getPane('schools')) {
            map.createPane('schools');
            const pane = map.getPane('schools');
            if (pane) pane.style.zIndex = '500';
        }

        // 2. BASMAP LAYER (Polygons)
        if (basemapLayerRef.current) {
            map.removeLayer(basemapLayerRef.current);
            basemapLayerRef.current = null;
        }

        if (basemap && viewMode !== 'heatmap') {
            basemapLayerRef.current = L.geoJSON(basemap, {
                pane: 'polygons',
                style: getChoroplethStyle,
                onEachFeature: (feature, layer) => {
                    const name = feature.properties?.block_name || feature.properties?.district_name || "Region";
                    layer.bindTooltip(`<div class="font-sans text-[10px] font-bold p-1">${name}</div>`, { sticky: true });
                    layer.on({
                        click: (e) => {
                            L.DomEvent.stopPropagation(e);
                            if (onFeatureClick) onFeatureClick(currentLevel, name);
                        },
                    mouseout: (e) => {
                        if (basemapLayerRef.current) {
                            basemapLayerRef.current.setStyle(getChoroplethStyle);
                        }
                    }
                });
            }
        }).addTo(map);

        // 3. GEOJSON LAYER (Dots) — ONLY show point markers in 'school' level
        if (geojsonLayerRef.current) {
            map.removeLayer(geojsonLayerRef.current);
            geojsonLayerRef.current = null;
        }

        const isHeatmapMode = String(viewMode) === 'heatmap';
        const showPoints = currentLevel === 'school';
        if (geojson && !isHeatmapMode && showPoints) {
            geojsonLayerRef.current = L.geoJSON(geojson, {
                pane: 'schools',
                    filter: (feature) => {
                        return checkFeatureFilter(feature, filterMode, queryMode, relevantInfraCols, activeMetric);
                    },
                    style: (feature) => {
                        const props = feature?.properties || {};
                        
                        // Apply Gradient for metrics (Density, Counts)
                        if (queryMode === 'metric' && gradientMetric && props[gradientMetric] !== undefined) {
                            const val = parseFloat(props[gradientMetric]);
                            if (!isNaN(val)) {
                                const range = metricMax - metricMin;
                                const ratio = range > 0 ? Math.min(1, Math.max(0, (val - metricMin) / range)) : (val > 0 ? 1 : 0);
                                const r = Math.round(240 - ratio * 225);
                                const g = Math.round(249 - ratio * 226);
                                const b = Math.round(255 - ratio * 175);
                                return { color: "white", weight: 1.5, opacity: 1, fillColor: `rgb(${r},${g},${b})`, fillOpacity: 0.85 };
                            }
                        }

                        if (queryMode === 'multi_binary') {
                            const score = relevantInfraCols.filter(k => isPos(props[k], k)).length;
                            const issues = relevantInfraCols.filter(k => isIssue(props[k], k)).length;
                            let fillColor = "#ef4444";
                            if (score === relevantInfraCols.length) fillColor = "#10b981";
                            else if (issues > 0 || score > 0) fillColor = "#f59e0b";
                            return { color: '#000', weight: 1.5, opacity: 1, fillColor, fillOpacity: 1, radius: 8 };
                        } else {
                            const col = activeMetric || relevantInfraCols[0];
                            let fillColor = "#3b82f6";
                            if (col && props[col] !== undefined) {
                                const val = props[col];
                                if (isPos(val, col)) fillColor = "#10b981";
                                else if (isIssue(val, col)) fillColor = "#f59e0b";
                                else fillColor = "#ef4444";
                            }
                            return { color: '#000', weight: 1.5, opacity: 1, fillColor, fillOpacity: 1, radius: 8 };
                        }
                    },
                    pointToLayer: (feature, latlng) => {
                        return L.circleMarker(latlng, { radius: 8, color: "#10172a", weight: 1.5, opacity: 1, fillOpacity: 0.9 });
                    },
                    onEachFeature: (feature, layer) => {
                        const props = feature.properties;
                        const name = props.display_name || props.schoolName || props.school_name || "Location";
                        layer.bindTooltip(`<div class="font-sans text-xs font-bold">${name}</div>`, { sticky: true });
                        
                        let popup = `<div class="p-2 min-w-[150px] font-sans text-xs">`;
                        popup += `<h3 class="font-bold border-b pb-1 mb-1">${name}</h3>`;
                        relevantInfraCols.forEach(k => {
                            let stat = '❌';
                            if (isPos(props[k], k)) stat = '✅';
                            else if (isIssue(props[k], k)) stat = '⚠️';
                            popup += `<div class="flex justify-between py-0.5"><span>${k.replace(/_/g, ' ')}</span><span>${stat}</span></div>`;
                        });
                        popup += `</div>`;
                        layer.bindPopup(popup);

                        layer.on("click", (e) => {
                            L.DomEvent.stopPropagation(e);
                            if (onFeatureClick) {
                                let clickLevel = "school";
                                let clickName = name;
                                if (feature.geometry?.type !== "Point") {
                                    if (props.block_name) { clickLevel = "block"; clickName = props.block_name; }
                                    else if (props.district_name) { clickLevel = "district"; clickName = props.district_name; }
                                    onFeatureClick(clickLevel, clickName);
                                } else {
                                    onFeatureClick("school", clickName);
                                }
                            }
                        });
                    }
                }).addTo(map);
            }
        }

        // --- HEATMAP LAYER ---
        if (viewMode === "heatmap" && heatmapData?.length) {
            if (heatLayerRef.current) map.removeLayer(heatLayerRef.current);
            // @ts-ignore
            heatLayerRef.current = (L as any).heatLayer(heatmapData, { radius: 25, blur: 15, max: 0.8 }).addTo(map);
        } else if (heatLayerRef.current) {
            map.removeLayer(heatLayerRef.current);
            heatLayerRef.current = null;
        }

        // --- LEGEND AND MODE FINALIZATION ---
        let newLegendConfig = null;
        const hasData = geojson || (apiResult?.table && apiResult.table.length > 0);

        if (hasData && queryMode === 'metric' && gradientMetric) {
            newLegendConfig = { type: 'gradient', metricLabel: gradientMetric.replace(/_/g, ' ').toUpperCase(), min: metricMin, max: metricMax };
        } else if (hasData && (queryMode === 'multi_binary' || queryMode === 'single_binary')) {
            const label = queryMode === 'multi_binary' 
                ? `Criteria: ${relevantInfraCols.map(k => k.replace(/_/g, ' ').replace(/\bno of\b/gi, '')).join(" & ").toUpperCase()}`
                : (activeMetric || relevantInfraCols[0] || "Infrastructure").replace(/_/g, ' ').toUpperCase();

            newLegendConfig = { 
                type: 'binary', 
                metricLabel: label, 
                items: [
                    { label: queryMode === 'multi_binary' ? 'All Criteria Met' : 'Met / Available', color: '#10b981' },
                    { label: queryMode === 'multi_binary' ? 'Partial / Issue' : 'Issue / Partial', color: '#f59e0b' },
                    { label: queryMode === 'multi_binary' ? 'None Met' : 'Missing / No', color: '#ef4444' }
                ]
            };
        }
        setLegendConfig(newLegendConfig);

    }, [geojson, basemap, currentLevel, onFeatureClick, heatmapData, filterMode, viewMode, activeMetric, gradientMetric, metricMin, metricMax, relevantInfraCols, queryMode]);

    return (
        <div className="relative h-full w-full">
            <div id="map-container" className="h-full w-full" />
            {(queryMode === 'multi_binary' || queryMode === 'single_binary') && (
                <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] glass p-1.5 rounded-2xl flex gap-1 bg-white/90 backdrop-blur-md border border-white/50 shadow-2xl">
                    {['all', 'yes', 'issue', 'no'].map(m => (
                        <button key={m} onClick={() => setFilterMode(m as any)} className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase transition-all ${filterMode === m ? 'bg-slate-800 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-100'}`}>
                            {m === 'all' ? 'All' : m === 'yes' ? 'Met' : m === 'issue' ? 'Partial' : 'None'}
                        </button>
                    ))}
                </div>
            )}
            {/* Choropleth Legend */}
            {gradientMetric && (
                <div className="absolute bottom-24 right-8 z-[1000] glass p-4 rounded-2xl shadow-2xl border border-white/20 min-w-[180px]">
                    <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-3 flex items-center justify-between">
                        <span>{gradientMetric.replace(/_/g, ' ').toUpperCase()}</span>
                        <BarChart2 size={12} className="text-blue-500" />
                    </div>
                    <div className="h-4 w-full rounded-full bg-gradient-to-r from-blue-50 to-blue-900 border border-blue-100 shadow-inner mb-2" />
                    <div className="flex justify-between text-[11px] font-bold text-slate-700">
                        <span>{metricMin.toLocaleString()}</span>
                        <span>{metricMax.toLocaleString()}</span>
                    </div>
                </div>
            )}

            {legendConfig && (
                <div className="absolute bottom-6 left-6 z-[1000] p-4 rounded-xl min-w-[200px] bg-white/95 backdrop-blur-md border border-white/20 shadow-2xl animate-in fade-in slide-in-from-bottom-2">
                    <div className="text-[10px] font-black text-slate-800 uppercase tracking-widest mb-1 border-b border-slate-200 pb-1">{legendConfig.metricLabel}</div>
                    {legendConfig.type === 'gradient' ? (
                        <>
                            <div className="h-3 w-full rounded-full" style={{ background: 'linear-gradient(to right, rgb(240, 249, 255), rgb(15, 23, 80))' }} />
                            <div className="flex justify-between text-[9px] font-bold text-slate-500 mt-1">
                                <span>Low ({legendConfig.min.toLocaleString()})</span>
                                <span>High ({legendConfig.max.toLocaleString()})</span>
                            </div>
                        </>
                    ) : (
                        <div className="flex flex-col gap-1.5 mt-2">
                            {legendConfig.items.map((it: any, i: number) => (
                                <div key={i} className="flex items-center gap-2">
                                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: it.color }} />
                                    <span className="text-[9px] font-bold text-slate-600 uppercase">{it.label}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
            <StateBorder map={mapRef.current} />
        </div>
    );
}

function StateBorder({ map }: { map: L.Map | null }) {
    useEffect(() => {
        if (!map) return;
        fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/basemap?level=state`, {
            headers: { "ngrok-skip-browser-warning": "true" }
        })
            .then(res => res.json())
            .then(data => L.geoJSON(data, { style: { color: "#1e293b", weight: 3, fillOpacity: 0, interactive: false } }).addTo(map))
            .catch(err => console.error("State border load error", err));
    }, [map]);
    return null;
}
