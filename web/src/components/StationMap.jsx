import L from "leaflet";
import { useEffect, useRef } from "react";

export default function StationMap({ station }) {
  const container = useRef(null);

  useEffect(() => {
    const map = L.map(container.current, { scrollWheelZoom: false }).setView(
      [station.latitude, station.longitude],
      14,
    );
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "© OpenStreetMap contributors",
    }).addTo(map);
    // A circle marker avoids Leaflet's bundled icon images, which bundlers mangle.
    const accent =
      getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#0f6d63";
    L.circleMarker([station.latitude, station.longitude], {
      radius: 9,
      color: accent,
      fillColor: accent,
      fillOpacity: 0.7,
    })
      .addTo(map)
      .bindPopup(`${station.name}<br>${station.latitude}, ${station.longitude}`);
    return () => map.remove();
  }, [station]);

  return (
    <section className="card">
      <h2>Where it stands</h2>
      <p className="lead">
        {station.site}, Juja, Kiambu. {station.latitude}, {station.longitude}, at{" "}
        {station.elevation_m} m.
      </p>
      <div id="map" ref={container} />
    </section>
  );
}
