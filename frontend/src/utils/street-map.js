// Visual geometry only. No roads or links are business evidence.
export function riskColor(score) {
  if (score == null || !Number.isFinite(Number(score))) return '#dce1dd'
  const t = Math.max(0, Math.min(1, Number(score) / 9))
  return `rgb(${Math.round(244 - 76 * t)},${Math.round(228 - 164 * t)},${Math.round(222 - 165 * t)})`
}

export function streetLayout(areas) {
  const valid = areas.filter((a) => a.lng != null && a.lat != null && Number.isFinite(Number(a.lng)) && Number.isFinite(Number(a.lat)))
    .slice().sort((a, b) => a.area_id.localeCompare(b.area_id))
  if (!valid.length) return { nodes: [], edges: [], roads: [], buildings: [] }
  const lngs = valid.map((a) => Number(a.lng)), lats = valid.map((a) => Number(a.lat))
  const cx = (Math.min(...lngs) + Math.max(...lngs)) / 2, cz = (Math.min(...lats) + Math.max(...lats)) / 2
  const longitudeScale = Math.cos(cz * Math.PI / 180)
  const span = Math.max((Math.max(...lngs) - Math.min(...lngs)) * longitudeScale, Math.max(...lats) - Math.min(...lats), .01)
  const nodes = valid.map((a) => ({ ...a, x: (Number(a.lng) - cx) * longitudeScale / span * 164, z: -(Number(a.lat) - cz) / span * 164 }))
  const candidates = []
  for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
    const a = nodes[i], b = nodes[j]
    candidates.push({ id: `${a.area_id}:${b.area_id}`, a: a.area_id, b: b.area_id, distance: Math.hypot(a.x - b.x, a.z - b.z) })
  }
  candidates.sort((a, b) => a.distance - b.distance || a.id.localeCompare(b.id))
  const parents = new Map(nodes.map((a) => [a.area_id, a.area_id]))
  function root(id) { while (parents.get(id) !== id) id = parents.get(id); return id }
  const edges = []
  // Stable minimum spanning tree, then up to four short neighbouring links.
  for (const edge of candidates) if (root(edge.a) !== root(edge.b)) {
    parents.set(root(edge.a), root(edge.b)); edges.push(edge)
  }
  const backbone = new Set(edges.map((e) => e.id))
  edges.push(...candidates.filter((e) => !backbone.has(e.id)).slice(0, 4))
  const roads = []
  const xs=[-330,-278,-224,-174,-130,-94,-64,-36,-8,22,54,90,132,180,234,286,334]
  const zs=[-330,-270,-214,-166,-122,-84,-52,-22,12,46,80,120,164,214,270,334]
  for(const x of xs)roads.push({x,z:0,w:x===22?5.5:3,d:680})
  for(const z of zs)roads.push({x:0,z,w:680,d:z===12?5.5:3})
  const buildings = []
  for(let i=0;i<xs.length-1;i++)for(let j=0;j<zs.length-1;j++){
    const width=xs[i+1]-xs[i]-9,depth=zs[j+1]-zs[j]-9,cols=width>35?3:2,rows=depth>32?2:1
    const cellW=width/cols,cellD=depth/rows
    for(let c=0;c<cols;c++)for(let r=0;r<rows;r++){
      const seed=(i*73+j*37+c*11+r*17)%101
      if(seed%6===0)continue
      const x=xs[i]+4.5+(c+.5)*cellW,z=zs[j]+4.5+(r+.5)*cellD
      const w=cellW-3-seed%3,d=cellD-3-seed%4
      if(nodes.some((n)=>Math.abs(n.x-x)<w/2+8&&Math.abs(n.z-z)<d/2+8))continue
      buildings.push({x,z,w,d,h:1.2+seed%6*.45})
    }
  }
  return { nodes, edges, roads, buildings }
}

export function edgeHeight(distance) { return Math.min(27, 8 + distance * .22) }
