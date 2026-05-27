import * as d3 from 'd3';

/**
 * Initialize zoom behaviour on the provided SVG element targeting the supplied root group.
 * Returns a cleanup function to remove listeners when the component unmounts.
 */
export function setupZoom(svgNode: SVGSVGElement | null, rootSel: any, zoomRef: { current: any }) {
  if (!svgNode || !rootSel) return () => {};
  const svg = d3.select(svgNode as unknown as SVGSVGElement);

  const zoom = d3
    .zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.2, 3])
    .on('zoom', (event: any) => rootSel.attr('transform', event.transform));

  svg.call(zoom as any);
  svg.on('dblclick.zoom', null);

  zoomRef.current = zoom;

  return () => {
    try {
      svg.on('.zoom', null as any);
    } catch (err) {
      // ignore cleanup errors
    }
    zoomRef.current = null;
  };
}
