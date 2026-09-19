import { useMemo, useRef, useState } from "react";

const PADDING = { top: 14, right: 12, bottom: 26, left: 38 };
const WIDTH = 900;
const HEIGHT = 260;

/** The comparison series' value at the same hour, or a dash where it has none. */
function compareAt(series, x, unit) {
  const found = series.find((point) => point.x === x);
  return Number.isFinite(found?.y) ? `${found.y.toFixed(1)} ${unit}` : "—";
}

/** Nice round step for an axis covering `span` in about `target` steps. */
function niceStep(span, target) {
  const rough = span / Math.max(target, 1);
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  return [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((step) => step >= rough) ?? rough;
}

function ticksBetween(low, high, target) {
  const step = niceStep(high - low, target);
  const first = Math.ceil(low / step) * step;
  const ticks = [];
  for (let value = first; value <= high + 1e-9; value += step) ticks.push(Number(value.toFixed(6)));
  return ticks;
}

/**
 * An hourly series as an SVG line, with an optional uncertainty band, a second line to
 * compare against, horizontal threshold lines, and a crosshair that follows the pointer.
 *
 * Points are {x: epoch ms, y: number|null, label: string}. Gaps (null y) break the line
 * rather than being joined across, because the station record really does have holes.
 */
export default function TimeSeries({
  points,
  band,
  compare,
  compareName,
  thresholds = [],
  unit = "°C",
  name,
  onHover,
  height = HEIGHT,
}) {
  const [hover, setHover] = useState(null);
  const svg = useRef(null);

  const scale = useMemo(() => {
    const values = [
      ...points.map((p) => p.y),
      ...(band ?? []).flatMap((p) => [p.low, p.high]),
      ...(compare ?? []).map((p) => p.y),
      ...thresholds.map((t) => t.value),
    ].filter((value) => value !== null && value !== undefined && Number.isFinite(value));
    if (!points.length || !values.length) return null;

    const xs = points.map((p) => p.x);
    const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
    const pad = (Math.max(...values) - Math.min(...values) || 2) * 0.12;
    const [y0, y1] = [Math.min(...values) - pad, Math.max(...values) + pad];
    const plotW = WIDTH - PADDING.left - PADDING.right;
    const plotH = height - PADDING.top - PADDING.bottom;
    return {
      x: (value) => PADDING.left + (x1 === x0 ? plotW / 2 : ((value - x0) / (x1 - x0)) * plotW),
      y: (value) => PADDING.top + plotH - ((value - y0) / (y1 - y0 || 1)) * plotH,
      x0,
      x1,
      y0,
      y1,
      plotH,
    };
  }, [points, band, compare, thresholds, height]);

  if (!scale) return <p className="lead">No hours to draw yet.</p>;

  const line = (series) => {
    let open = false;
    return series
      .map((p) => {
        if (p.y === null || p.y === undefined || !Number.isFinite(p.y)) {
          open = false;
          return "";
        }
        const command = open ? "L" : "M";
        open = true;
        return `${command}${scale.x(p.x).toFixed(1)} ${scale.y(p.y).toFixed(1)}`;
      })
      .join(" ")
      .trim();
  };

  const area = (series) => {
    const usable = series.filter((p) => Number.isFinite(p.low) && Number.isFinite(p.high));
    if (!usable.length) return "";
    const top = usable.map((p) => `${scale.x(p.x).toFixed(1)} ${scale.y(p.high).toFixed(1)}`);
    const bottom = usable
      .slice()
      .reverse()
      .map((p) => `${scale.x(p.x).toFixed(1)} ${scale.y(p.low).toFixed(1)}`);
    return `M${top.join(" L")} L${bottom.join(" L")} Z`;
  };

  const track = (event) => {
    const box = svg.current.getBoundingClientRect();
    const x = ((event.clientX - box.left) / box.width) * WIDTH;
    let nearest = null;
    let best = Infinity;
    for (const point of points) {
      const distance = Math.abs(scale.x(point.x) - x);
      if (distance < best) [best, nearest] = [distance, point];
    }
    setHover(nearest);
    onHover?.(nearest);
  };

  const leave = () => {
    setHover(null);
    onHover?.(null);
  };

  const xTicks = points.filter((_, index) => index % Math.ceil(points.length / 8) === 0);

  return (
    <div className="tseries">
      <svg
        ref={svg}
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="img"
        aria-label={`${name}: ${points.length} hours`}
        onMouseMove={track}
        onMouseLeave={leave}
        onTouchStart={(event) => track(event.touches[0])}
        onTouchMove={(event) => track(event.touches[0])}
      >
        {ticksBetween(scale.y0, scale.y1, 5).map((value) => (
          <g key={value}>
            <line
              className="grid"
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={scale.y(value)}
              y2={scale.y(value)}
            />
            <text className="tick" x={PADDING.left - 6} y={scale.y(value) + 4} textAnchor="end">
              {value}
            </text>
          </g>
        ))}

        {thresholds.map((threshold) => (
          <g key={threshold.label}>
            <line
              className={`threshold ${threshold.kind ?? ""}`}
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={scale.y(threshold.value)}
              y2={scale.y(threshold.value)}
            />
            <text className="threshold-label" x={WIDTH - PADDING.right} y={scale.y(threshold.value) - 4} textAnchor="end">
              {threshold.label}
            </text>
          </g>
        ))}

        {band ? <path className="band" d={area(band)} /> : null}
        {compare ? <path className="series compare" d={line(compare)} /> : null}
        <path className="series main" d={line(points)} />

        {xTicks.map((point) => (
          <text key={point.x} className="tick" x={scale.x(point.x)} y={height - 8} textAnchor="middle">
            {point.label}
          </text>
        ))}

        {hover && Number.isFinite(hover.y) ? (
          <g>
            <line
              className="crosshair"
              x1={scale.x(hover.x)}
              x2={scale.x(hover.x)}
              y1={PADDING.top}
              y2={PADDING.top + scale.plotH}
            />
            <circle className="marker" cx={scale.x(hover.x)} cy={scale.y(hover.y)} r="4" />
          </g>
        ) : null}
      </svg>

      <p className="tseries-read" aria-live="polite">
        {hover ? (
          <>
            <strong>{hover.full ?? hover.label}</strong>{" "}
            {Number.isFinite(hover.y) ? (
              <>
                {hover.y.toFixed(1)} {unit}
                {compare && compareName ? ` · ${compareName} ${compareAt(compare, hover.x, unit)}` : ""}
              </>
            ) : (
              <>no reading passed quality control for this hour</>
            )}
          </>
        ) : (
          <>Point at the chart to read an hour.</>
        )}
      </p>
    </div>
  );
}
