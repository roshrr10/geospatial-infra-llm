"use client";

import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";

interface HeatmapLayerProps {
    points: [number, number, number][]; // [lat, lng, intensity]
    radius?: number;
    blur?: number;
    max?: number;
}

export default function HeatmapLayer({
    points,
    radius = 25,
    blur = 15,
    max = 1.0
}: HeatmapLayerProps) {
    const map = useMap();

    useEffect(() => {
        if (!map || !points || points.length === 0) return;

        // @ts-ignore - leaflet.heat is not typed
        const heatLayer = L.heatLayer(points, {
            radius,
            blur,
            max,
            gradient: {
                0.0: 'blue',
                0.2: 'cyan',
                0.4: 'lime',
                0.6: 'yellow',
                1.0: 'red'
            }
        });

        heatLayer.addTo(map);

        return () => {
            map.removeLayer(heatLayer);
        };
    }, [map, points, radius, blur, max]);

    return null;
}
