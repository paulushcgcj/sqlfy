/**
 * Compute connected components (islands) from node list and edges.
 *
 * @param nodeData - array of objects with `id` property
 * @param edges - array of edges with `fromTable` and `toTable` string keys
 * @returns array of components, each component is an array of node ids
 */
export function getComponents(
  nodeData: Array<{ id: string }>,
  edges: Array<{ fromTable: string; toTable: string }>,
): string[][] {
  const adjList = new Map<string, Set<string>>();
  nodeData.forEach((n) => adjList.set(n.id, new Set()));
  edges.forEach((e) => {
    adjList.get(e.fromTable)?.add(e.toTable);
    adjList.get(e.toTable)?.add(e.fromTable);
  });

  const visited = new Set<string>();
  const comps: string[][] = [];

  for (const n of nodeData) {
    if (visited.has(n.id)) continue;
    const comp: string[] = [];
    const stack = [n.id];
    while (stack.length) {
      const cur = stack.pop()!;
      if (visited.has(cur)) continue;
      visited.add(cur);
      comp.push(cur);
      adjList.get(cur)?.forEach((nb) => {
        if (!visited.has(nb)) stack.push(nb);
      });
    }
    comps.push(comp);
  }

  return comps;
}
