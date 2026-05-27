import * as d3 from 'd3';

const ALPHA = 0.3;

/**
 * Attach D3 drag behaviour to the node selection and wire it to the provided simulation ref.
 * Returns a cleanup function that attempts to remove the drag listeners.
 */
export function setupDrag(nodeSel: any, simRef: { current: any }) {
  if (!nodeSel) return () => {};

  const drag = d3
    .drag<SVGGElement, any>()
    .on('start', (ev: any, d: any) => {
      if (!ev.active) simRef.current?.alphaTarget(ALPHA)?.restart();
      d.fx = d.x;
      d.fy = d.y;
    })
    .on('drag', (ev: any, d: any) => {
      d.fx = ev.x;
      d.fy = ev.y;
    })
    .on('end', (ev: any) => {
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
