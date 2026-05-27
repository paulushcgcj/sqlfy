import * as d3 from 'd3';
import { useCallback } from 'react';
import type { RefObject } from 'react';

export function useSimulationControls(params: {
  svgRef: RefObject<SVGSVGElement | null>;
  zoomRef: { current: any };
  simRef: { current: any };
  height: number;
}) {
  const { svgRef, zoomRef, simRef, height } = params;

  const fitView = useCallback(() => {
    const svgNode = svgRef?.current;
    if (!svgNode) return;
    const svg = d3.select(svgNode);
    const root = svg.select<SVGGElement>('.root');
    const rootNode = root.node() as SVGGElement | null;
    if (!rootNode) return;
    const bbox = rootNode.getBBox();
    if (!bbox.width || !bbox.height) return;
    const W = svgNode.clientWidth || 800;
    const scale = 0.85 * Math.min(W / bbox.width, height / bbox.height);
    const tx = W / 2 - scale * (bbox.x + bbox.width / 2);
    const ty = height / 2 - scale * (bbox.y + bbox.height / 2);
    try {
      zoomRef.current?.transform(
        d3.select(svgNode).transition().duration(500),
        d3.zoomIdentity.translate(tx, ty).scale(scale),
      );
    } catch {
      // In test environments the transition may not exist — fallback to no-transition
      try {
        zoomRef.current?.transform?.(d3.zoomIdentity.translate(tx, ty).scale(scale));
      } catch {
        // swallow
      }
    }
  }, [svgRef, zoomRef, height]);

  const reheat = useCallback(() => {
    simRef.current?.alpha(0.4).restart();
  }, [simRef]);

  return { fitView, reheat };
}
