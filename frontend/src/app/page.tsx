"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Map as MapIcon,
  Table as TableIcon,
  Info,
  Database,
  ChevronRight,
  Sparkles,
  ArrowLeft,
  LayoutDashboard,
  BarChart3,
  MapPin,
  X,
  FileDown,
  CheckCircle,
  AlertCircle,
  Mic,
  MicOff
} from "lucide-react";
import AnalyticsDrawer from "@/components/AnalyticsDrawer";
import LayerControl from "@/components/Map/LayerControl";
import ExportModal from "@/components/ExportModal";
import DashboardTab from "@/components/DashboardTab";

// Dynamically import the Map component to avoid SSR issues with Leaflet
const GeoMap = dynamic(() => import("@/components/Map/GeoMap"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full bg-slate-50 flex flex-col items-center justify-center gap-4">
      <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      <p className="text-slate-400 font-bold uppercase tracking-widest text-xs">Initializing Spatial Engine...</p>
    </div>
  )
});

const suggestions = [
  {
    title: "🌍 Regional Analysis",
    queries: [
      { label: "Districts with highest road density", query: "Which districts have the highest road density?" },
      { label: "Blocks in RI BHOI district", query: "Show blocks in RI BHOI district" },
      { label: "Compare school density by district", query: "Compare school density across all districts" },
    ]
  },
  {
    title: "🏫 School Infrastructure",
    queries: [
      { label: "Schools without Electricity", query: "Show schools with no electricity connection" },
      { label: "Smart Classrooms and Computers", query: "Which schools have both computers and smart classrooms?" },
      { label: "Solar Energy Facilities", query: "Which schools are equipped with solar panels?" },
      { label: "Drinking Water in WEST GARO HILLS", query: "List schools in WEST GARO HILLS with no drinking water" },
      { label: "Library in RI BHOI", query: "Show schools in RI BHOI with a library facility" },
      { label: "Schools needing Ramps", query: "Show schools that need ramp facilities" },
    ]
  },
  {
    title: "📊 Advanced Analytics",
    queries: [
      { label: "Schools per SqKm (Block Density)", query: "Show blocks with highest school density" },
      { label: "Total Schools by District", query: "Show districts with the most schools" },
      { label: "Road Density vs Schools", query: "Compare road density across districts" },
    ]
  }
];

export default function Dashboard() {
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [apiResult, setApiResult] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [lastSearch, setLastSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mapLevel, setMapLevel] = useState<"district" | "block" | "school">("district");
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [basemapData, setBasemapData] = useState<any>(null);

  // Phase 3 States
  const [activeMetric, setActiveMetric] = useState("priority_score");
  const [viewMode, setViewMode] = useState<"polygon" | "heatmap">("polygon");
  const [heatmapData, setHeatmapData] = useState<[number, number, number][] | undefined>(undefined);
  const [isSidebarVisible, setIsSidebarVisible] = useState(true);
  const [showAllResults, setShowAllResults] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [viewTab, setViewTab] = useState<"map"|"dashboard">("map");
  const [dynamicMetrics, setDynamicMetrics] = useState<{id: string, label: string}[]>([]);
  const [mapFilterIntent, setMapFilterIntent] = useState<'all' | 'yes' | 'no' | 'issue'>('all');

  // Voice Input States
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    // Load basemap on mount (default: district)
    if (mapLevel !== 'school') {
      loadBasemap(mapLevel);
    } else {
      setBasemapData(null);
    }
  }, [mapLevel]);

  const loadBasemap = useCallback((level: string) => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/basemap?level=${level}`, {
      headers: { "ngrok-skip-browser-warning": "true" }
    })
      .then(res => res.json())
      .then(data => setBasemapData(data))
      .catch(err => console.error("Basemap fetch failed", err));
  }, []);

  const fetchHeatmap = useCallback(async (metric: string, level: string) => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/heatmap?metric=${metric}&level=${level}`, {
        headers: { "ngrok-skip-browser-warning": "true" }
      });
      const data = await response.json();
      if (data.features) {
        const points = data.features.map((f: any) => [
          f.geometry.coordinates[1],
          f.geometry.coordinates[0],
          f.properties.intensity
        ]) as [number, number, number][];
        setHeatmapData(points);
      }
    } catch (err) {
      console.error("Heatmap fetch failed", err);
    }
  }, []);

  const fetchHeatmapSummary = useCallback(async (metric: string, level: string) => {
    try {
      setApiResult((prev: any) => ({
        ...prev,
        summary: "Generating AI spatial insights...",
        table: prev?.table || []
      }));

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/heatmap/summary?metric=${metric}&level=${level}`, {
        headers: { "ngrok-skip-browser-warning": "true" }
      });
      const data = await response.json();
      if (data.summary) {
        setApiResult((prev: any) => ({
          ...prev,
          summary: data.summary,
          table: prev?.table || []
        }));
      }
    } catch (err) {
      console.error("Heatmap summary fetch failed", err);
      setApiResult((prev: any) => ({
        ...prev,
        summary: "Spatial insights currently unavailable."
      }));
    }
  }, []);

  useEffect(() => {
    if (viewMode === "heatmap") {
      const level = mapLevel === "school" ? "block" : mapLevel;
      fetchHeatmap(activeMetric, level);
      fetchHeatmapSummary(activeMetric, level);
    } else {
      setHeatmapData(undefined);
    }
  }, [activeMetric, viewMode, mapLevel, fetchHeatmap, fetchHeatmapSummary]);

  const processSearch = useCallback(async (q: string) => {
    setIsSearching(true);
    setApiResult(null);
    setError(null);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/query`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true"
        },
        body: JSON.stringify({ question: q }),
      });
      if (!response.ok) throw new Error("Failed to fetch from backend");
      const data = await response.json();
      
      if (data.type === 'chat') {
          setApiResult({
              ...data,
              geojson: { type: "FeatureCollection", features: [] },
              table: []
          });
          setIsSearching(false);
          return;
      }

      setLastSearch(q);
      
      const features = data.geojson?.features || [];
      // Detect user intent to guide the map's filterMode without throwing away table stats
      const queryLower = q.toLowerCase();
      let detectedIntent: 'all' | 'yes' | 'no' | 'issue' = 'all';
      if (/\b(without|no|lack|missing|need|don't have|dont have|needs|lacking)\b/.test(queryLower)) {
          detectedIntent = 'no';
      } else if (/\b(issue|problem|broken|functional issue|repair|partial)\b/.test(queryLower)) {
          detectedIntent = 'issue';
      } else if (/\b(both|all|have|with|equipped)\b/.test(queryLower)) {
          detectedIntent = 'yes';
      }
      setMapFilterIntent(detectedIntent);
      
      if (data.table && data.table.length > 0) {
        // Collect ALL keys from the first 500 rows to ensure sparse data (like computers) is detected
        const allKeysSet = new Set<string>();
        data.table.slice(0, 500).forEach((row: any) => Object.keys(row).forEach(k => allKeysSet.add(k)));
        const keys = Array.from(allKeysSet);
        
        const skipKeywords = ['id', 'code', 'udise', 'pinc', 'rank', 'geometry', 'mobi', 'phone', 'latitude', 'longitude', 'accuracy', 'altitude', 'serial', 'index', 'class', 'grade', 'year', 'month', 'village', 'cluster', 'vil', 'adm'];
        
        // Count/density keywords that should be treated as gradient metrics, not binary
        const countKeywords = ['total_schools', 'schools_per_sqkm', 'road_density', 'avg_', 'count', 'density', 'total_road'];
        const isCountMetric = (k: string) => countKeywords.some(ck => k.toLowerCase().includes(ck));
        
        const numericCols = keys.filter(k => {
          const lk = k.toLowerCase();
          // Skip admin name columns but NOT count/total columns
          if (lk === 'block_name' || lk === 'district_name' || lk === 'state_name') return false;
          if (skipKeywords.some(skip => lk.includes(skip))) return false;
          // Include count metrics
          if (isCountMetric(k)) return true;
          const infraKeywords = ['solar', 'panel', 'electricity', 'water', 'toilet', 'computer', 'facility', 'internet', 'smart', 'ramp', 'playground', 'available', 'connection', 'provided'];
          if (infraKeywords.some(ik => lk.includes(ik))) return true;
          // Heuristic for other numeric metrics
          return data.table.slice(0, 500).some((row: any) => typeof row[k] === 'number' || (!isNaN(Number(row[k])) && String(row[k]).trim() !== ''));
        });

        // Add Composite Metric if Multiple detected
        let initialActive = "";
        let finalDynamicMetrics: {id: string, label: string}[] = [];
        
        // Find the best metric to set as active based on user's query
        const queryWords = queryLower.split(/\W+/);
        const mentionedCol = numericCols.find(col => {
            const lCol = col.toLowerCase();
            return queryWords.some(word => word.length > 3 && lCol.includes(word));
        });

        if (numericCols.length > 1) {
            const compositeKey = "All Selected Facilities";
            data.table = data.table.map((row: any) => {
                const results = numericCols.map(k => {
                    const v = row[k];
                    const val = Number(v);
                    if (val === 1 || String(v).toLowerCase().trim() === 'yes' || String(v).toLowerCase().trim() === 'available') return 'pos';
                    if (val === 0 || val === 2 || String(v).toLowerCase().trim() === 'no' || String(v).toLowerCase().trim() === 'unavailable') return 'neg';
                    return 'iss';
                });
                
                let compositeVal = 0;
                if (results.every(r => r === 'pos')) compositeVal = 1;
                else if (results.some(r => r === 'pos' || r === 'iss')) compositeVal = 2; // Partial
                
                return { ...row, [compositeKey]: compositeVal };
            });
            finalDynamicMetrics = [
                {id: compositeKey, label: compositeKey},
                ...numericCols.map(k => ({ id: k, label: k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) }))
            ];
            // If user mentioned a specific column, prefer it over the composite summary
            initialActive = mentionedCol || compositeKey;
        } else {
            finalDynamicMetrics = numericCols.map(k => ({ id: k, label: k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) }));
            initialActive = numericCols[0] || "";
        }
        
        setDynamicMetrics(finalDynamicMetrics);
        if (initialActive) setActiveMetric(initialActive);
      }

      setApiResult(data);
      if (data.level) setMapLevel(data.level);

      setIsDrawerOpen(true);

      fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/query/summary`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true"
        },
        body: JSON.stringify({ question: q, data: data.table }),
      }).then(res => res.json()).then(summaryData => {
        setApiResult((prev: any) => prev ? { ...prev, summary: summaryData.summary } : null);
      }).catch(() => {
        setApiResult((prev: any) => prev ? { ...prev, summary: "Analysis summary unavailable." } : null);
      });
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setIsSearching(false);
    }
  }, []);

  const handleQuickQuery = (q: string) => {
    setQuery(q);
    processSearch(q);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    processSearch(query);
  };

  useEffect(() => {
    // Initialize speech recognition
    if (typeof window !== "undefined" && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = true;
      
      recognitionRef.current.onresult = (event: any) => {
        let interimTranscript = '';
        let finalTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }
        
        if (finalTranscript) {
          setQuery(finalTranscript);
          processSearch(finalTranscript);
        } else if (interimTranscript) {
           setQuery(interimTranscript);
        }
      };

      recognitionRef.current.onstart = () => setIsListening(true);
      recognitionRef.current.onend = () => setIsListening(false);
      recognitionRef.current.onerror = (e: any) => {
        console.error("Speech recognition error:", e.error);
        setIsListening(false);
      };
    }
  }, [processSearch]);

  const toggleVoice = () => {
    if (isListening) {
      recognitionRef.current?.stop();
    } else {
      setQuery("");
      recognitionRef.current?.start();
    }
  };

  const handleFeatureClick = useCallback(async (level: string, name: string) => {
    if (level === "school") return;
    setIsSearching(true);
    try {
      const nextLevel = level === "district" ? "block" : "school";
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/drilldown/${level}/${name}`, {
        headers: { "ngrok-skip-browser-warning": "true" }
      });
      const geojson = await response.json();
      
      if (apiResult) setHistory((h: any) => [...h, apiResult]);
      
      setApiResult({
        ...apiResult,
        geojson: geojson,
        table: geojson.features.map((f: any) => f.properties),
        summary: `Exploring ${nextLevel}s in ${name}`,
        level: nextLevel
      });
      setMapLevel(nextLevel as any);
      setIsDrawerOpen(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSearching(false);
    }
  }, [apiResult]);

  const handleGoBack = () => {
    if (history.length > 0) {
      const prev = history[history.length - 1];
      setApiResult(prev);
      setHistory(history.slice(0, -1));
      
      if (prev.table && prev.table.length > 0) {
          const keys = Object.keys(prev.table[0]);
          if (keys.includes("All Selected Facilities")) {
              setActiveMetric("All Selected Facilities");
          } else {
              const first = prev.table[0];
              if (first.schoolName) setMapLevel("school");
              else if (first.block_name) setMapLevel("block");
              else setMapLevel("district");
          }
      }
    } else {
      setApiResult(null);
      setMapLevel("district");
    }
  };

  const handleExportPDF = async () => {
    if (!apiResult?.table) return;
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/report`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true"
        },
        body: JSON.stringify({
          metric: activeMetric,
          level: mapLevel,
          data: apiResult.table,
          summary: apiResult.summary
        }),
      });
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Report_${activeMetric}.pdf`;
      a.click();
    } catch (err) {
      console.error("PDF Export failed", err);
      throw err;
    }
  };

  const handleSendEmail = async (email: string) => {
    if (!apiResult?.table) return;
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/send-email`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true"
        },
        body: JSON.stringify({
          email,
          report_data: {
            metric: activeMetric,
            level: mapLevel,
            data: apiResult.table,
            summary: apiResult.summary
          }
        }),
      });
      if (!response.ok) throw new Error("Email delivery failed");
      return await response.json();
    } catch (err) {
      console.error("Email Sending failed", err);
      throw err;
    }
  };

  return (
    <div className="flex flex-col h-screen bg-slate-50 text-slate-900 overflow-hidden font-sans">
      <header className="h-16 bg-white border-b flex items-center px-8 justify-between z-30 shrink-0">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-xl shadow-lg">
            <Database className="text-white w-5 h-5" />
          </div>
          <h1 className="text-lg font-black leading-none">MEGHALAYA <span className="text-blue-600">GEO-AI</span></h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex bg-slate-100 p-1 rounded-xl">
            <button onClick={() => setViewTab("map")} className={`px-4 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${viewTab === "map" ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-600"}`}>Map View</button>
            <button onClick={() => setViewTab("dashboard")} className={`px-4 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${viewTab === "dashboard" ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-600"}`}>Dashboard</button>
          </div>
          <button onClick={() => setIsExportOpen(true)} className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all">
            <FileDown size={14} /> Export Report
          </button>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-full text-[10px] font-black uppercase tracking-widest">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
            System Active
          </div>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden relative">
        <button
          onClick={() => setIsSidebarVisible(!isSidebarVisible)}
          className={`absolute bottom-8 left-8 z-[1001] w-12 h-12 glass flex items-center justify-center rounded-2xl shadow-2xl transition-all ${!isSidebarVisible ? 'bg-blue-600 text-white' : 'text-slate-600'}`}
        >
          <LayoutDashboard size={20} />
        </button>

        <AnimatePresence>
          {isSidebarVisible && (
            <motion.aside
              initial={{ x: -420 }} animate={{ x: 0 }} exit={{ x: -420 }}
              className="w-[420px] bg-white border-r flex flex-col shrink-0 z-20 shadow-xl overflow-hidden relative"
            >
              <div className="p-8 pb-4 space-y-4">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Search & Intelligence</label>
                <form onSubmit={handleSearch} className="relative group flex items-center gap-2">
                  <div className="relative flex-1">
                    <input
                      type="text"
                       placeholder="Ask GeoAI Assistant... (e.g. 'Hi' or 'Schools in block X')"
                  className="w-full pl-6 pr-14 py-4 bg-slate-50 border-2 border-slate-100 rounded-2xl focus:border-blue-500 outline-none text-sm font-medium"
                      value={query} onChange={(e) => setQuery(e.target.value)}
                    />
                    
                    <button type="submit" disabled={isSearching} className="absolute right-2 top-2 bottom-2 w-10 bg-blue-600 text-white rounded-xl flex items-center justify-center hover:bg-blue-700 transition">
                      <Search size={18} />
                    </button>
                  </div>
                  <button 
                    type="button" 
                    onClick={toggleVoice} 
                    className={`w-[56px] h-[56px] rounded-2xl flex items-center justify-center transition-all shrink-0 ${isListening ? 'bg-rose-500 text-white shadow-lg animate-pulse' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}
                    title="Voice Search"
                  >
                    {isListening ? <MicOff size={24} /> : <Mic size={24} />}
                  </button>
                </form>

                {/* Assistant Chat Bubble (Moved to Sidebar Content) */}
                <AnimatePresence>
                  {apiResult?.type === 'chat' && apiResult?.message && (
                    <motion.div 
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="bg-blue-50/50 p-5 rounded-3xl border border-blue-100/50 mb-4 overflow-hidden"
                    >
                        <div className="flex gap-4">
                            <div className="w-10 h-10 bg-blue-600 rounded-2xl flex items-center justify-center shrink-0 shadow-lg shadow-blue-500/30">
                                <Sparkles size={20} className="text-white" />
                            </div>
                            <div className="space-y-1">
                                <h4 className="text-[9px] font-black text-blue-600 uppercase tracking-widest italic">GeoAI Assistant</h4>
                                <p className="text-slate-700 text-xs leading-relaxed font-medium">
                                    {apiResult.message}
                                </p>
                                <button 
                                    onClick={() => setApiResult(null)}
                                    className="text-[8px] font-black text-slate-400 uppercase hover:text-blue-600 transition-colors pt-2 block"
                                >
                                    Dismiss
                                </button>
                            </div>
                        </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <div className="flex-1 overflow-y-auto px-8 pb-8 space-y-6">
                <AnimatePresence mode="wait">
                  {isSearching ? (
                    <div className="p-6 bg-blue-50 border border-blue-100 rounded-3xl space-y-4">
                      <div className="flex items-center gap-3 animate-pulse">
                        <Sparkles size={16} className="text-blue-600" />
                        <p className="text-xs font-bold text-blue-800 uppercase tracking-widest">Architecting Spatial Intelligence...</p>
                      </div>
                    </div>
                  ) : error ? (
                    <div className="p-6 bg-rose-50 border border-rose-100 rounded-3xl space-y-4">
                      <div className="flex items-center gap-3 text-rose-600">
                        <AlertCircle size={20} />
                        <h3 className="text-sm font-bold uppercase tracking-widest">Search Failed</h3>
                      </div>
                      <p className="text-xs text-rose-500 font-medium">{error}</p>
                      <button onClick={() => processSearch(query)} className="w-full py-3 bg-rose-600 text-white rounded-2xl text-[10px] font-black uppercase">Try Again</button>
                    </div>
                  ) : apiResult ? (
                    <div className="space-y-6 pt-2">
                      <div className="flex items-center justify-between">
                        <button onClick={handleGoBack} className="flex items-center gap-2 text-[10px] font-black uppercase text-slate-400 hover:text-blue-600">
                          <ArrowLeft size={12} /> Go Back
                        </button>
                        <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-[9px] font-black uppercase">{mapLevel.toUpperCase()} VIEW</span>
                      </div>

                      <div className="bg-slate-50 border border-slate-100 p-6 rounded-3xl space-y-3">
                        <h3 className="text-[10px] font-black text-blue-600 uppercase tracking-widest flex items-center gap-2">
                          <Info size={14} /> AI Analysis
                        </h3>
                        <p className="text-sm font-medium text-slate-700 leading-relaxed whitespace-pre-wrap">{apiResult.summary}</p>
                        <button onClick={() => setIsDrawerOpen(true)} className="w-full py-3 bg-slate-900 text-white rounded-2xl text-[10px] font-black uppercase mt-4">View Analytics Table</button>
                      </div>

                      {(() => {
                        const bKeys = [
                          'electricity', 'drinking_water', 'water', 'library', 'computers', 'computer', 'playground', 
                          'ramp', 'internet', 'smart_classroom', 'ict_lab', 'boy_toilets', 'toilet',
                          'girl_toilets', 'solar_panel', 'solar', 'handwash', 'uniforms', 'text_books',
                          'extinguisher', 'building_status', 'facility', 'available', 'provided'
                        ];
                        
                        let presentInfra: string[] = [];
                        if (apiResult.table && apiResult.table.length > 0) {
                          // Scan for infrastructure keywords in column names
                          const allKeysSet = new Set<string>();
                          apiResult.table.slice(0, 500).forEach((row: any) => Object.keys(row).forEach(k => allKeysSet.add(k)));
                          const bKeys = ["solar", "electricity", "water", "toilet", "computer", "internet", "smart", "ramp", "playground"];
                          presentInfra = Array.from(allKeysSet).filter(k => {
                            const lower = k.toLowerCase();
                            const skip = ['id', 'geometry', 'name', 'code', 'longitude', 'latitude'];
                            if (skip.some(s => lower.includes(s))) return false;
                            return bKeys.some(keyword => lower.includes(keyword));
                          });
                        }
                        
                        return (
                          <div className="space-y-4">
                            <div className="p-4 bg-blue-50 border border-blue-100 rounded-2xl">
                              <label className="text-[9px] font-black text-blue-600 uppercase tracking-widest block mb-2">Manual Metric Selection</label>
                              <select 
                                value={activeMetric}
                                onChange={(e) => setActiveMetric(e.target.value)}
                                className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-bold text-slate-700 outline-none focus:ring-2 focus:ring-blue-500"
                              >
                                <option value="priority_score">Default Priority Score</option>
                                {presentInfra.map(f => (
                                  <option key={f} value={f}>{f.replace(/_/g, ' ').toUpperCase()}</option>
                                ))}
                              </select>
                            </div>

                            {presentInfra.length > 0 && (
                              <div className="grid grid-cols-2 gap-4">
                                {(() => {
                                  const total = apiResult.table.length;
                                  const positive = apiResult.table.filter((row: any) => {
                                    const positives = ['1', '1.0', 'yes', 'true', 'functional', 'satisfactory', 'available', 'provided'];
                                    const v = row[activeMetric] || row[presentInfra[0]];
                                    if (v === 1 || v === 1.0) return true;
                                    const vStr = String(v).toLowerCase().trim();
                                    return positives.includes(vStr);
                                  }).length;
                                  return (
                                    <>
                                      <div className="p-5 bg-emerald-600 rounded-3xl text-white shadow-md">
                                        <p className="text-[9px] font-black uppercase opacity-70">Filtered Results: Positive</p>
                                        <h4 className="text-3xl font-black mt-1">{positive}</h4>
                                      </div>
                                      <div className="p-5 bg-slate-800 rounded-3xl text-white shadow-md">
                                        <p className="text-[9px] font-black uppercase opacity-70">Filtered Results: Total Output</p>
                                        <h4 className="text-3xl font-black mt-1">{total}</h4>
                                      </div>
                                    </>
                                  );
                                })()}
                              </div>
                            )}
                          </div>
                        );
                      })()}

                      <div className="space-y-3">
                        <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Top Samples</h3>
                        {apiResult.table.slice(0, 5).map((row: any, i: number) => (
                          <div key={i} className="p-4 bg-white border border-slate-100 rounded-2xl shadow-sm">
                            <h4 className="text-xs font-bold text-slate-900 uppercase">{row.display_name || row.schoolName || row.block_name || row.district_name || "Location"}</h4>
                            <p className="text-[9px] font-bold text-blue-600 mt-1 uppercase tracking-widest">{row.udiseCode || row.block_id || "Live Record"}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-8">
                      {suggestions.map((cat, idx) => (
                        <div key={idx} className="space-y-4">
                          <h3 className="text-[10px] font-black text-slate-300 uppercase tracking-widest px-1">{cat.title}</h3>
                          <div className="space-y-2">
                            {cat.queries.map((item, id) => (
                              <button key={id} onClick={() => handleQuickQuery(item.query)} className="w-full text-left p-4 bg-slate-50 border-2 border-transparent hover:border-blue-100 rounded-2xl transition-all flex items-center justify-between group">
                                <span className="text-xs font-bold text-slate-600 group-hover:text-slate-900">{item.label}</span>
                                <ChevronRight size={14} className="text-slate-300" />
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </AnimatePresence>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        <section className="flex-1 relative flex flex-col h-full bg-slate-50">
          {viewTab === "map" ? (
            <>
              <LayerControl 
                activeMetric={activeMetric} 
                onMetricChange={setActiveMetric} 
                viewMode={viewMode} 
                onModeChange={setViewMode} 
                adminLevel={mapLevel as any} 
                onLevelChange={(level) => {
                  setMapLevel(level);
                }} 
                dynamicOptions={dynamicMetrics} 
              />
              <GeoMap 
                geojson={apiResult?.geojson} 
                basemap={basemapData} 
                currentLevel={mapLevel} 
                onLevelChange={setMapLevel} 
                onFeatureClick={handleFeatureClick} 
                heatmapData={heatmapData} 
                activeMetric={activeMetric} 
                searchQuery={lastSearch} 
                initialFilterIntent={mapFilterIntent} 
                viewMode={viewMode} 
                apiResult={apiResult} 
              />
              <div className="absolute bottom-8 right-8 z-[1000] glass p-4 rounded-2xl w-64 space-y-2 shadow-2xl border border-white/20">
                <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">System Sync</h4>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div className={`h-full bg-blue-600 transition-all ${apiResult ? 'w-full' : 'w-1/3 animate-pulse'}`}></div>
                  </div>
                  <span className="text-[10px] font-black text-blue-600 uppercase">{apiResult ? "Locked" : "Syncing"}</span>
                </div>
              </div>
            </>
          ) : (
            <DashboardTab data={apiResult?.table || []} activeMetric={activeMetric} level={mapLevel} summary={apiResult?.summary} />
          )}
        </section>

        <AnalyticsDrawer data={apiResult?.table || []} isOpen={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} title="Analysis Results" summary={apiResult?.summary} />
        <ExportModal 
          isOpen={isExportOpen}
          onClose={() => setIsExportOpen(false)}
          onDownloadReady={handleExportPDF}
          onEmailSend={handleSendEmail}
        />
      </main>
    </div>
  );
}
