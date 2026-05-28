import * as d3 from 'd3';

const ALPHA = 0.3;

type DragDatum = d3.SimulationNodeDatum;
type SimRef = { current: { alphaTarget(n: number): { restart(): unknown } } | null };

/**
 * Attach D3 drag behaviour to the node selection and wire it to the provided simulation ref.
 * Returns a cleanup function that attempts to remove the drag listeners.
 */
export function setupDrag<D extends DragDatum, PE extends Element>(
  nodeSel: d3.Selection<SVGGElement, D, PE, unknown> | null,
  simRef: SimRef,
) {
  if (!nodeSel) return () => {};

  const drag = d3
    .drag<SVGGElement, D>()
    .on('start', (ev, d) => {
      if (!ev.active) simRef.current?.alphaTarget(ALPHA).restart();
      d.fx = d.x;
      d.fy = d.y;
    })
    .on('drag', (ev, d) => {
      d.fx = ev.x;
      d.fy = ev.y;
    })
    .on('end', (ev) => {
      if (!ev.active) simRef.current?.alphaTarget(0);
    });

  nodeSel.call(drag);

  return () => {
    try {
      // best-effort removal; environments may not support namespaced listeners
      nodeSel.on?.('.drag', null);
    } catch {
      // ignore
    }
  };
}
