import * as d3 from 'd3';

/**
 * Initialize zoom behaviour on the provided SVG element targeting the supplied root group.
 * Returns a cleanup function to remove listeners when the component unmounts.
 */
export function setupZoom<PE extends Element>(
  svgNode: SVGSVGElement | null,
  rootSel: d3.Selection<SVGGElement, unknown, PE, unknown> | null,
  zoomRef: { current: d3.ZoomBehavior<SVGSVGElement, unknown> | null },
) {
  if (!svgNode || !rootSel) return () => {};
  const svg = d3.select(svgNode);

  const zoom = d3
    .zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.2, 3])
    .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) =>
      rootSel.attr('transform', String(event.transform)),
    );

  // D3's call() overload resolution requires the cast here
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  svg.call(zoom as any);
  svg.on('dblclick.zoom', null);

  zoomRef.current = zoom;

  return () => {
    try {
      svg.on('.zoom', null);
    } catch {
      // ignore cleanup errors
    }
    zoomRef.current = null;
  };
}
