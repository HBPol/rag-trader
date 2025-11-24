"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useInfluenceGraphQuery } from "@/lib/queries/analytics";
import type { InfluenceGraphEdge } from "@/lib/schemas/influenceGraph";
import { renderFreshness } from "./freshness";
import ExplainabilityChip from "./ExplainabilityChip";
import "./influence-graph.css";

type LayoutNode = {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
};

type Point = { x: number; y: number };

type InfluenceGraphProps = {
  source: string;
  target: string;
  windowSize: string;
};

function normalizeSymbol(value: string): string {
  return value.trim().toUpperCase();
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

const PULSE_DELTA_THRESHOLD = 0.05;
const PULSE_INTENSITY_DELTA_RANGE = 0.25;
const PULSE_RECENCY_MINUTES = 240;

function getEdgeKey(
  edge: Pick<InfluenceGraphEdge, "source" | "target" | "window">,
) {
  return `${edge.source}-${edge.target}-${edge.window}`;
}

function minutesSince(
  timestamp: string | null | undefined,
  now: number,
): number {
  if (!timestamp) return Number.NaN;
  const parsed = Date.parse(timestamp);
  if (Number.isNaN(parsed)) return Number.NaN;
  return (now - parsed) / 60000;
}

function derivePulseStrength(edge: InfluenceGraphEdge, now: number): number {
  const currentWeight = edge.weight;
  const previousWeight = edge.previous_weight;
  if (
    currentWeight === null ||
    currentWeight === undefined ||
    previousWeight === null ||
    previousWeight === undefined
  ) {
    return 0;
  }

  const delta = currentWeight - previousWeight;
  if (!Number.isFinite(delta) || delta < PULSE_DELTA_THRESHOLD) return 0;

  const ageMinutes = minutesSince(edge.computed_ts, now);
  if (Number.isFinite(ageMinutes) && ageMinutes > PULSE_RECENCY_MINUTES) {
    return 0;
  }

  const normalized = delta / PULSE_INTENSITY_DELTA_RANGE;
  return clamp(normalized, 0.35, 1);
}

function weightToStroke(
  weight: number | null | undefined,
  maxAbsWeight: number,
): number {
  if (!maxAbsWeight || !Number.isFinite(maxAbsWeight)) return 1.5;
  if (weight === null || weight === undefined || !Number.isFinite(weight)) {
    return 1.5;
  }
  const normalized = Math.abs(weight) / maxAbsWeight;
  return 1.5 + normalized * 5;
}

function runForceLayout(
  nodeIds: string[],
  edges: InfluenceGraphEdge[],
  width: number,
  height: number,
): Map<string, Point> {
  if (!width || !height) {
    return new Map();
  }

  const nodes: LayoutNode[] = nodeIds.map((id, index) => {
    const angle = (index / Math.max(nodeIds.length, 1)) * Math.PI * 2;
    const radius = Math.min(width, height) / 3;
    return {
      id,
      x: width / 2 + radius * Math.cos(angle),
      y: height / 2 + radius * Math.sin(angle),
      vx: 0,
      vy: 0,
    };
  });

  const nodeIndex = new Map(nodes.map((node, index) => [node.id, index]));
  const maxAbsWeight = Math.max(
    0.0001,
    ...edges
      .map((edge) => (edge.weight == null ? 0 : Math.abs(edge.weight)))
      .filter((value) => Number.isFinite(value)),
  );

  const iterations = 200;
  const repulsion = 2200;
  const damping = 0.85;
  const targetLengthBase = Math.min(width, height) / 2.5;

  for (let step = 0; step < iterations; step += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const nodeA = nodes[i];
        const nodeB = nodes[j];
        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        const distSq = dx * dx + dy * dy + 0.01;
        const force = repulsion / distSq;
        const distance = Math.sqrt(distSq);
        const fx = (force * dx) / distance;
        const fy = (force * dy) / distance;
        nodeA.vx -= fx;
        nodeA.vy -= fy;
        nodeB.vx += fx;
        nodeB.vy += fy;
      }
    }

    edges.forEach((edge) => {
      const sourceIndex = nodeIndex.get(edge.source);
      const targetIndex = nodeIndex.get(edge.target);
      if (sourceIndex === undefined || targetIndex === undefined) return;

      const sourceNode = nodes[sourceIndex];
      const targetNode = nodes[targetIndex];
      const dx = targetNode.x - sourceNode.x;
      const dy = targetNode.y - sourceNode.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      const absWeight = Math.abs(edge.weight ?? 0);
      const targetLength =
        targetLengthBase * (1 - 0.35 * (absWeight / maxAbsWeight));
      const spring = 0.1;
      const force = (distance - targetLength) * spring;
      const fx = (force * dx) / distance;
      const fy = (force * dy) / distance;
      sourceNode.vx += fx;
      sourceNode.vy += fy;
      targetNode.vx -= fx;
      targetNode.vy -= fy;
    });

    nodes.forEach((node) => {
      node.vx *= damping;
      node.vy *= damping;
      node.x = clamp(node.x + node.vx, 40, width - 40);
      node.y = clamp(node.y + node.vy, 40, height - 40);
    });
  }

  return new Map(nodes.map((node) => [node.id, { x: node.x, y: node.y }]));
}

export default function InfluenceGraph({
  source,
  target,
  windowSize,
}: InfluenceGraphProps) {
  const graphContainerRef = useRef<HTMLDivElement | null>(null);
  const [dimensions, setDimensions] = useState<{
    width: number;
    height: number;
  }>({ width: 760, height: 480 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 });
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [pulsingEdges, setPulsingEdges] = useState<Map<string, number>>(
    () => new Map(),
  );
  const isPanning = useRef(false);
  const lastPointer = useRef<Point | null>(null);

  const influenceGraphQuery = useInfluenceGraphQuery(
    source,
    target,
    windowSize,
  );
  const nodes = useMemo(
    () => influenceGraphQuery.data?.payload.graph.nodes ?? [],
    [influenceGraphQuery.data?.payload.graph?.nodes],
  );
  const edges = useMemo(
    () => influenceGraphQuery.data?.payload.graph.edges ?? [],
    [influenceGraphQuery.data?.payload.graph?.edges],
  );
  const maxAbsWeight = useMemo(
    () =>
      Math.max(
        0.0001,
        ...edges
          .map((edge) => (edge.weight == null ? 0 : Math.abs(edge.weight)))
          .filter((value) => Number.isFinite(value)),
      ),
    [edges],
  );

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mediaQuery.matches);

    const handleChange = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches);
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleChange);
    } else {
      mediaQuery.addListener?.(handleChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleChange);
      } else {
        mediaQuery.removeListener?.(handleChange);
      }
    };
  }, []);

  const pulseStrengthByEdge = useMemo(() => {
    const now = Date.now();
    return edges.reduce((map, edge) => {
      const strength = derivePulseStrength(edge, now);
      if (strength > 0) {
        map.set(getEdgeKey(edge), strength);
      }
      return map;
    }, new Map<string, number>());
  }, [edges]);

  useEffect(() => {
    const frameId = globalThis.window?.requestAnimationFrame(() => {
      setPulsingEdges(pulseStrengthByEdge);
    });

    return () => {
      if (frameId !== undefined) {
        globalThis.window?.cancelAnimationFrame(frameId);
      }
    };
  }, [pulseStrengthByEdge]);

  useEffect(() => {
    const element = graphContainerRef.current;
    if (!element) return;

    const updateSize = () => {
      const { width, height } = element.getBoundingClientRect();
      if (width && height) {
        setDimensions({ width, height });
      }
    };

    updateSize();
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(updateSize);
      observer.observe(element);
      return () => observer.disconnect();
    }

    const intervalId = globalThis.window?.setInterval(updateSize, 500);
    return () => {
      if (intervalId !== undefined) {
        globalThis.window?.clearInterval(intervalId);
      }
    };
  }, []);

  const layout = useMemo(
    () => runForceLayout(nodes, edges, dimensions.width, dimensions.height),
    [nodes, edges, dimensions.height, dimensions.width],
  );

  useEffect(() => {
    setPan({ x: 0, y: 0 });
    setZoom(1);
  }, [source, target, windowSize]);

  const handleWheel: React.WheelEventHandler<SVGSVGElement> = (event) => {
    event.preventDefault();
    const delta = event.deltaY > 0 ? -0.1 : 0.1;
    setZoom((current) => clamp(current + delta, 0.6, 2.2));
  };

  const handlePointerDown: React.PointerEventHandler<SVGSVGElement> = (
    event,
  ) => {
    isPanning.current = true;
    lastPointer.current = { x: event.clientX, y: event.clientY };
  };

  const handlePointerMove: React.PointerEventHandler<SVGSVGElement> = (
    event,
  ) => {
    if (!isPanning.current || !lastPointer.current) return;
    const dx = event.clientX - lastPointer.current.x;
    const dy = event.clientY - lastPointer.current.y;
    setPan((current) => ({ x: current.x + dx, y: current.y + dy }));
    lastPointer.current = { x: event.clientX, y: event.clientY };
  };

  const handlePointerUp: React.PointerEventHandler<SVGSVGElement> = () => {
    isPanning.current = false;
    lastPointer.current = null;
  };

  const isEmpty = !nodes.length;
  const freshnessMinutes =
    influenceGraphQuery.data?.payload.freshness.age_minutes;

  return (
    <Card className="border shadow-sm" data-testid="influence-graph">
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle>Influence Graph</CardTitle>
            <p className="text-sm text-muted-foreground">
              Force-directed view of cross-asset influence weighted by lead/lag
              and granger evidence.
            </p>
            <p className="text-xs text-muted-foreground" aria-live="polite">
              Freshness: {renderFreshness(freshnessMinutes)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-foreground">
            <Button
              size="sm"
              variant="outline"
              aria-label="Zoom in"
              onClick={() => setZoom((value) => clamp(value + 0.2, 0.6, 2.2))}
            >
              +
            </Button>
            <Button
              size="sm"
              variant="outline"
              aria-label="Zoom out"
              onClick={() => setZoom((value) => clamp(value - 0.2, 0.6, 2.2))}
            >
              –
            </Button>
            <Button
              size="sm"
              variant="outline"
              aria-label="Reset view"
              onClick={() => {
                setZoom(1);
                setPan({ x: 0, y: 0 });
              }}
            >
              Reset
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span className="rounded-full bg-muted px-3 py-1">
            Nodes: {nodes.length}
          </span>
          <span className="rounded-full bg-muted px-3 py-1">
            Edges: {edges.length}
          </span>
          <span className="rounded-full bg-muted px-3 py-1">
            Pair: {normalizeSymbol(source)} → {normalizeSymbol(target)} (
            {windowSize})
          </span>
          {influenceGraphQuery.data?.matchingEdge ? (
            <span className="rounded-full bg-primary/10 px-3 py-1 text-primary">
              Selected weight:{" "}
              {influenceGraphQuery.data.matchingEdge.weight?.toFixed(3) ??
                "n/a"}
            </span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {influenceGraphQuery.isLoading ? (
          <div
            className="h-[420px] w-full animate-pulse rounded-md bg-muted"
            aria-label="Loading influence graph"
          />
        ) : influenceGraphQuery.error ? (
          <p className="text-sm text-destructive" role="status">
            Failed to load influence graph. Please retry.
          </p>
        ) : isEmpty ? (
          <p className="text-sm text-muted-foreground">
            No influence graph data available.
          </p>
        ) : (
          <div className="space-y-3">
            <div
              ref={graphContainerRef}
              className="relative h-[420px] w-full overflow-hidden rounded-lg border bg-background"
            >
              <svg
                role="img"
                aria-label="Influence graph"
                className="h-full w-full cursor-grab"
                viewBox={`0 0 ${Math.max(dimensions.width, 100)} ${Math.max(dimensions.height, 100)}`}
                onWheel={handleWheel}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                data-testid="influence-graph-canvas"
              >
                <rect width="100%" height="100%" fill="transparent" />
                <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                  {edges.map((edge) => {
                    const from = layout.get(edge.source);
                    const to = layout.get(edge.target);
                    if (!from || !to) return null;
                    const strokeWidth = weightToStroke(
                      edge.weight,
                      maxAbsWeight,
                    );
                    const edgeKey = getEdgeKey(edge);
                    const pulseStrength = pulsingEdges.get(edgeKey) ?? 0;
                    const shouldPulse =
                      pulseStrength > 0 && !prefersReducedMotion;
                    const pulseStyle: CSSProperties | undefined = shouldPulse
                      ? {
                          ["--edge-pulse-strength" as string]: pulseStrength,
                          ["--edge-pulse-opacity" as string]: 0.8,
                        }
                      : undefined;
                    const isSelected =
                      normalizeSymbol(edge.source) ===
                        normalizeSymbol(source) &&
                      normalizeSymbol(edge.target) ===
                        normalizeSymbol(target) &&
                      edge.window === windowSize;

                    return (
                      <g key={`${edge.source}-${edge.target}-${edge.window}`}>
                        <line
                          data-testid={`influence-edge-${edge.source}-${edge.target}`}
                          x1={from.x}
                          y1={from.y}
                          x2={to.x}
                          y2={to.y}
                          className={
                            shouldPulse ? "influence-edge--pulse" : undefined
                          }
                          style={pulseStyle}
                          stroke={
                            isSelected
                              ? "hsl(var(--primary))"
                              : "hsl(var(--muted-foreground))"
                          }
                          strokeWidth={strokeWidth}
                          strokeOpacity={0.8}
                          markerEnd="url(#arrowhead)"
                        />
                        <text
                          x={(from.x + to.x) / 2}
                          y={(from.y + to.y) / 2 - 8}
                          className="fill-foreground text-[10px]"
                        >
                          {(edge.weight ?? 0).toFixed(2)}
                        </text>
                      </g>
                    );
                  })}
                  {nodes.map((node) => {
                    const point = layout.get(node);
                    if (!point) return null;
                    return (
                      <g key={node} data-testid={`influence-node-${node}`}>
                        <circle
                          cx={point.x}
                          cy={point.y}
                          r={18}
                          className="fill-background stroke-primary"
                          strokeWidth={2.5}
                        />
                        <text
                          x={point.x}
                          y={point.y + 4}
                          textAnchor="middle"
                          className="fill-foreground text-sm font-semibold"
                        >
                          {node}
                        </text>
                      </g>
                    );
                  })}
                  <defs>
                    <marker
                      id="arrowhead"
                      markerWidth="10"
                      markerHeight="10"
                      refX="6"
                      refY="3"
                      orient="auto"
                    >
                      <path
                        d="M0,0 L0,6 L9,3 z"
                        fill="hsl(var(--foreground))"
                      />
                    </marker>
                  </defs>
                </g>
              </svg>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                {[0.2, 0.5, 0.8].map((value) => (
                  <div key={value} className="flex items-center gap-1">
                    <span
                      className="inline-block rounded-sm bg-muted"
                      style={{ width: 40, height: weightToStroke(value, 1) }}
                    />
                    <span className="text-[11px]">
                      {value.toFixed(1)} weight
                    </span>
                  </div>
                ))}
              </div>
              <ExplainabilityChip
                metricId={`influence-legend:${source}:${target}:${windowSize}`}
                label="Influence"
                className="shrink-0"
              />
              <span>
                Zoom with scroll or buttons. Drag to pan. Edge width scales with
                absolute weight.
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
