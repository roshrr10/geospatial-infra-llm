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
    selectedRegion?: string;
}

export default function GeoMap({ geojson, basemap, currentLevel, onLevelChange, onFeatureClick, heatmapData, activeMetric, searchQuery, initialFilterIntent, viewMode, apiResult, selectedRegion }: GeoMapProps) {
    const mapRef = useRef<L.Map | null>(null);
    const geojsonLayerRef = useRef<L.GeoJSON | null>(null);
    const basemapLayerRef = useRef<L.GeoJSON | null>(null);
    const heatLayerRef = useRef<any>(null);

    const [filterMode, setFilterMode] = useState<'all' | 'yes' | 'no' | 'issue' | 'only_x' | 'only_y'>('all');
    const [lastIntentProp, setLastIntentProp] = useState<'all' | 'yes' | 'no' | 'issue' | 'only_x' | 'only_y' | undefined>(initialFilterIntent as any);
    const [legendConfig, setLegendConfig] = useState<any>(null);
    
    // Refs for analytical context (solves stale closures in Leaflet events)
    const apiResultRef = useRef(apiResult);
    const gMetricRef = useRef<string | null>(null);
    const mMinRef = useRef(0);
    const mMaxRef = useRef(100);
    const activeMetricRef = useRef(activeMetric);
    const viewModeRef = useRef(viewMode);
    const regionCountsRef = useRef<Record<string, number>>({});
    const styleFuncRef = useRef<any>(null);
    
    // ── FIXED STATUS HELPERS (CZ3Y1UY8X Logic Restored) ──
    const isPos = (v: any, key?: string) => {
        const val = Number(v);
        if (key?.toLowerCase().includes('computer') && !key?.toLowerCase().includes('available')) return val > 0;
        return (val === 1 || String(v).toLowerCase().trim() === 'yes' || String(v).toLowerCase().trim() === 'available') && val !== 2;
    };
    
    const isNeg = (v: any, key?: string) => {
        const val = Number(v);
        if (key?.toLowerCase().includes('computer') && !key?.toLowerCase().includes('available')) return val === 0 || v === null;
        return val === 0 || v === null || v === undefined || String(v).toLowerCase().trim() === 'no' || String(v).toLowerCase().trim() === 'unavailable';
    };
    
    const isIssue = (v: any, key?: string) => {
        const val = Number(v);
        if (key?.toLowerCase().includes('computer') && !key?.toLowerCase().includes('available')) return false;
        return val === 2 || String(v).toLowerCase().includes('issue') || String(v).toLowerCase().includes('partial');
    };

    const checkFeatureFilter = (feature: any, currentFilterMode: string, currentQueryMode: string, currentRelevantCols: string[], currActiveMetric?: string) => {
        if (!currentFilterMode || currentFilterMode === 'all') return true;
        const props = feature?.properties || {};
        
        if (currentQueryMode === 'multi_binary') {
            const p1 = isPos(props[currentRelevantCols[0]], currentRelevantCols[0]);
            const p2 = isPos(props[currentRelevantCols[1]], currentRelevantCols[1]);
            
            if (currentFilterMode === 'yes') return p1 && p2;
            if (currentFilterMode === 'no') return !p1 && !p2;
            
            // Venn-logic exact filters
            if (currentFilterMode === 'only_x') return p1 && !p2;
            if (currentFilterMode === 'only_y') return !p1 && p2;
        } else {
            const col = currActiveMetric || currentRelevantCols[0];
            if (!col) return false; 
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

    const getCleanLabel = (k: string) => {
        if (!k) return '';
        return k.replace(/no_of_/gi, '')
            .replace(/smart_classroom_available_in_school_1_yes_2_no/gi, 'Smart Classroom')
            .replace(/_available/gi, '')
            .replace(/_provided/gi, '')
            .replace(/_/g, ' ')
            .trim()
            .split(' ')
            .map(w => w.charAt(0).toUpperCase() + w.slice(1))
            .join(' ');
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

        const isCombinedCol = (k: string) => k.toLowerCase().includes('_attainment') || k.toLowerCase().includes('_status') || k.toLowerCase() === 'status';
        const isBinaryCol = (k: string) => bKeys.some(bk => k.toLowerCase().includes(bk)) && !sKeys.has(k.toLowerCase()) && !isCombinedCol(k);
        
        infraCols = keys.filter(isBinaryCol);
        const combinedStatusDetected = keys.some(isCombinedCol);

        const countKeywords = ['total', 'count', 'density', 'num', 'per_sqkm', 'avg_'];
        const isCountCol = (k: string) => countKeywords.some(ck => k.toLowerCase().includes(ck)) && !sKeys.has(k.toLowerCase());
        
        // Metric Selection Logic
        if (activeMetric && !isBinaryCol(activeMetric) && !isCombinedCol(activeMetric) && !sKeys.has(activeMetric.toLowerCase())) {
            gMetric = activeMetric;
        } else if (!activeMetric) {
            for (const key of keys) {
                if (sKeys.has(key.toLowerCase()) || isCombinedCol(key)) continue;
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
        else if (combinedStatusDetected || infraCols.length > 1) finalMode = 'multi_binary'; 
        else if (activeMetric && isBinaryCol(activeMetric)) finalMode = 'single_binary';
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

    // Synchronously intercept new intents from API so there's no race condition
    if (initialFilterIntent !== lastIntentProp) {
        setLastIntentProp(initialFilterIntent);
        setFilterMode(initialFilterIntent || 'all');
    }

    // Cleanup Leaflet map on unmount so it remounts correctly when switching tabs
    useEffect(() => {
        return () => {
            if (mapRef.current) {
                mapRef.current.off();
                mapRef.current.remove();
                mapRef.current = null;
            }
        };
    }, []);

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

        styleFuncRef.current = getChoroplethStyle;

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
        let baseRenderHandle: any;
        let heatRenderHandle: any;

        if (basemapLayerRef.current) {
            map.removeLayer(basemapLayerRef.current);
            basemapLayerRef.current = null;
        }

        if (basemap && viewMode !== 'heatmap') {
            baseRenderHandle = setTimeout(() => {
                const getVal = (p: any, keywords: string[]) => {
                    const key = Object.keys(p).find(k => keywords.some(kw => k.toLowerCase().includes(kw)));
                    return key ? p[key] : null;
                };

                basemapLayerRef.current = L.geoJSON(basemap, {
                    pane: 'polygons',
                    style: getChoroplethStyle,
                    filter: (feature) => {
                        if (!selectedRegion) return true;
                        const props = feature.properties || {};
                        const target = normalizeName(selectedRegion);
                        
                        // Flexible detection of administrative properties
                        const dVal = getVal(props, ['district']);
                        const bVal = getVal(props, ['block']);
                        
                        const dName = normalizeName(dVal);
                        const bName = normalizeName(bVal);
                        
                        return dName === target || bName === target;
                    },
                onEachFeature: (feature, layer) => {
                    const props = feature.properties || {};
                    const name = getVal(props, ['block']) || getVal(props, ['district']) || "Region";
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
            }, 10);
        }

        // --- LEGEND AND MODE FINALIZATION ---
        let newLegendConfig = null;

        const hasData = geojson || (apiResult?.table && apiResult.table.length > 0);

        if (hasData && queryMode === 'metric' && gradientMetric) {
            newLegendConfig = { type: 'gradient', metricLabel: gradientMetric.replace(/_/g, ' ').toUpperCase(), min: metricMin, max: metricMax };
        } else if (hasData && queryMode === 'multi_binary' && relevantInfraCols.length >= 2) {
            const s1Name = getCleanLabel(relevantInfraCols[0]);
            const s2Name = getCleanLabel(relevantInfraCols[1]);
            
            newLegendConfig = { 
                type: 'binary', 
                metricLabel: `Comparative: ${s1Name} & ${s2Name}`, 
                items: [
                    { label: 'Both Equipped', color: '#10b981' },
                    { label: `Only ${s1Name}`, color: '#3b82f6' },
                    { label: `Only ${s2Name}`, color: '#f59e0b' },
                    { label: 'None (Neither)', color: '#ef4444' }
                ]
            };
        } else if (hasData && queryMode === 'single_binary') {
            newLegendConfig = { 
                type: 'binary', 
                metricLabel: (activeMetric || relevantInfraCols[0] || "Infrastructure").replace(/_/g, ' ').toUpperCase(), 
                items: [
                    { label: 'Met / Available', color: '#10b981' },
                    { label: 'Issue / Partial', color: '#f59e0b' },
                    { label: 'Missing / No', color: '#ef4444' }
                ]
            };
        }
        setLegendConfig(newLegendConfig);
        
        return () => {
            clearTimeout(baseRenderHandle);
            clearTimeout(heatRenderHandle);
        };

    }, [basemap, currentLevel, heatmapData, viewMode, activeMetric, gradientMetric, metricMin, metricMax, relevantInfraCols, queryMode, geojson, selectedRegion]);

    // Atomic Style Refresher to force polygon color recalibrations instantly 
    // when filter buttons or metrics change, without touching the literal shape geometries.
    useEffect(() => {
        if (basemapLayerRef.current && styleFuncRef.current) {
            basemapLayerRef.current.setStyle(styleFuncRef.current);
        }
    }, [regionCounts, activeMetric, gradientMetric, filterMode, viewMode]);

    // Isolated hook entirely dedicated to School Point Markers rendering
    useEffect(() => {
        if (!mapRef.current) return;
        const map = mapRef.current;

        if (geojsonLayerRef.current) {
            map.removeLayer(geojsonLayerRef.current);
            geojsonLayerRef.current = null;
        }

        const isHeatmapMode = String(viewMode) === 'heatmap';
        const showPoints = currentLevel === 'school';
        if (geojson && !isHeatmapMode && showPoints) {
            // Using a short setTimeout ensures the canvas renderer clears the previous removal completely
            // before calculating the path bounds for new additions. This defeats Leaflet's render batching race conditionals.
            const renderHandle = setTimeout(() => {
                geojsonLayerRef.current = L.geoJSON(geojson, {
                    pane: 'schools',
                    filter: (feature) => {
                        return checkFeatureFilter(feature, filterMode, queryMode, relevantInfraCols, activeMetric);
                    },
                    style: (feature) => {
                        const props = feature?.properties || {};
                        
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
                            const p1 = isPos(props[relevantInfraCols[0]], relevantInfraCols[0]);
                            const p2 = isPos(props[relevantInfraCols[1]], relevantInfraCols[1]);
                            
                            let fillColor = "#ef4444"; // Default: Neither
                            if (p1 && p2) fillColor = "#10b981"; // Both
                            else if (p1) fillColor = "#3b82f6";  // Only X
                            else if (p2) fillColor = "#f59e0b";  // Only Y
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
            }, 10);
            return () => clearTimeout(renderHandle);
        }
    }, [geojson, filterMode, queryMode, relevantInfraCols, activeMetric, viewMode, currentLevel, gradientMetric, metricMin, metricMax, onFeatureClick]);

    return (
        <div className="relative h-full w-full">
            <div id="map-container" className="h-full w-full" />
            {(queryMode === 'multi_binary' || queryMode === 'single_binary') && (
                <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] glass px-3 py-1.5 rounded-2xl flex flex-col gap-1 bg-white/90 backdrop-blur-md border border-white/50 shadow-2xl">
                    <div className="flex gap-1 items-center">
                        {(queryMode === 'multi_binary' ? ['all', 'yes', 'only_x', 'only_y', 'no'] : ['all', 'yes', 'issue', 'no']).map(m => {
                            let label = 'All';
                            if (m === 'yes') label = queryMode === 'multi_binary' ? 'Both' : 'Met';
                            else if (m === 'no') label = 'None';
                            else if (m === 'issue') label = 'Partial';
                            else if (m === 'only_x') label = getCleanLabel(relevantInfraCols[0]) || 'Metric 1';
                            else if (m === 'only_y') label = getCleanLabel(relevantInfraCols[1]) || 'Metric 2';
                            
                            return (
                                <button key={m} onClick={() => setFilterMode(m as any)} className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase transition-all ${filterMode === m ? 'bg-slate-800 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-100'}`}>
                                    {label}
                                </button>
                            );
                        })}
                    </div>
                    <div className="text-[7px] font-black text-slate-400 uppercase tracking-widest text-center opacity-50">
                        Map Filter: <span className="text-blue-600">{filterMode.toUpperCase()}</span> | Mode: {queryMode.toUpperCase()}
                    </div>
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
