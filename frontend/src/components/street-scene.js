import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { edgeHeight, riskColor } from '@/utils/street-map'

// Imported only by the map route. The scene renders on demand, without particles.
export function createStreetScene(host, layout, callbacks) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75))
  renderer.setClearColor('#e9ede7', 1)
  renderer.domElement.setAttribute('aria-hidden', 'true')
  host.appendChild(renderer.domElement)
  const scene = new THREE.Scene(), camera = new THREE.OrthographicCamera(-120, 120, 120, -120, .1, 1500)
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = false
  controls.screenSpacePanning = false
  controls.minZoom = .6; controls.maxZoom = 3.5
  controls.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE }
  controls.touches = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_ROTATE }
  controls.minPolarAngle = .3; controls.maxPolarAngle = Math.PI / 2.6
  scene.add(new THREE.HemisphereLight('#ffffff', '#b0bba9', 1.1))
  const sun = new THREE.DirectionalLight('#ffffff', 1)
  sun.position.set(-100, 220, 80); scene.add(sun)
  const ground = new THREE.Group(), buildings = new THREE.Group(), links = new THREE.Group()
  scene.add(ground, buildings, links)
  const plane = (w, d, color, x, z, y = .03) => {
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshBasicMaterial({ color }))
    mesh.rotation.x = -Math.PI / 2; mesh.position.set(x, y, z); ground.add(mesh); return mesh
  }
  plane(2000, 2000, '#e9ede7', 0, 0, 0)
  for (const road of layout.roads) {
    plane(road.w + 1.1, road.d, '#dce3d7', road.x, road.z, .04)
    plane(road.w, road.d, '#f6f8f3', road.x, road.z, .06)
    if (Math.min(road.w,road.d) > 4) plane(road.w > road.d ? road.w : .15, road.w > road.d ? .15 : road.d, '#d8dfd3', road.x, road.z, .075)
  }
  // Small local access paths anchor region points to the schematic street grid.
  for (const n of layout.nodes) {
    const nearX=layout.roads.filter((r)=>r.w<r.d).reduce((closest,r)=>Math.abs(r.x-n.x)<Math.abs(closest-n.x)?r.x:closest,layout.roads[0].x)
    plane(Math.max(.4, Math.abs(nearX - n.x)), 1.7, '#fafbf7', (nearX + n.x) / 2, n.z, .08)
  }
  if (layout.buildings.length) {
    const boxes = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshLambertMaterial({ color: '#d1dacd',emissive:'#d1dacd',emissiveIntensity:.25,transparent:true,opacity:.55 }), layout.buildings.length)
    const feet = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({color:'#bdc8b7',transparent:true,opacity:.24,depthWrite:false}),layout.buildings.length)
    const dummy = new THREE.Object3D()
    layout.buildings.forEach((b, i) => {
      dummy.position.set(b.x, b.h / 2 + .1, b.z); dummy.scale.set(b.w, b.h, b.d); dummy.updateMatrix(); boxes.setMatrixAt(i, dummy.matrix)
      // A flat displaced footprint supplies depth without expensive shadow passes.
      dummy.rotation.x=-Math.PI/2;dummy.position.set(b.x+.7,.09,b.z+.8);dummy.scale.set(b.w+.6,b.d+.8,1);dummy.updateMatrix();feet.setMatrixAt(i,dummy.matrix);dummy.rotation.x=0
    })
    buildings.add(boxes,feet)
  }
  const heatCanvas = document.createElement('canvas'); heatCanvas.width = heatCanvas.height = 128
  const ctx = heatCanvas.getContext('2d')
  const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 64)
  gradient.addColorStop(0, '#ffffffc0'); gradient.addColorStop(.3, '#ffffff80'); gradient.addColorStop(1, '#ffffff00')
  ctx.fillStyle = gradient; ctx.fillRect(0, 0, 128, 128)
  const heatTexture = new THREE.CanvasTexture(heatCanvas)
  const nodeMeshes = [], edgeMeshes = [], hitTargets = []
  for (const n of layout.nodes) {
    const heat = new THREE.Mesh(new THREE.PlaneGeometry(22, 22), new THREE.MeshBasicMaterial({ map: heatTexture, transparent: true, depthWrite: false }))
    heat.rotation.x = -Math.PI / 2; heat.position.set(n.x, .15, n.z); scene.add(heat)
    const point = new THREE.Mesh(new THREE.CylinderGeometry(2.2, 2.4, .8, 24), new THREE.MeshBasicMaterial())
    point.position.set(n.x, .9, n.z); point.userData = { kind: 'node', id: n.area_id }; scene.add(point)
    const ring = new THREE.Mesh(new THREE.RingGeometry(2.7, 3.05, 40), new THREE.MeshBasicMaterial({ color: '#345fc5', side: THREE.DoubleSide }))
    ring.rotation.x = -Math.PI / 2; ring.position.set(n.x, .2, n.z); scene.add(ring)
    nodeMeshes.push({ node: n, point, ring, heat }); hitTargets.push(point)
  }
  const byId = new Map(layout.nodes.map((n) => [n.area_id, n]))
  for (const edge of layout.edges) {
    const a = byId.get(edge.a), b = byId.get(edge.b)
    const curve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(a.x, 1, a.z), new THREE.Vector3((a.x + b.x) / 2, edgeHeight(edge.distance) * 2, (a.z + b.z) / 2), new THREE.Vector3(b.x, 1, b.z))
    const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, 36, .27, 6, false), new THREE.MeshBasicMaterial({ color: '#71858f', transparent: true, opacity: .65 }))
    mesh.userData = { kind: 'edge', id: edge.id }; links.add(mesh); edgeMeshes.push({ edge, mesh }); hitTargets.push(mesh)
  }
  let width = 1, height = 1, frame = 0, disposed = false, selected = '', hovered = null, risk = {}, insets = {}, mode = 'inclined', visibleLinks = true
  const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2(), position = new THREE.Vector3()
  function render() {
    frame = 0
    if (disposed) return
    renderer.render(scene, camera)
    callbacks.onProject(nodeMeshes.map(({ node }) => {
      position.set(node.x, 1.5, node.z).project(camera)
      return { ...node, left: (position.x + 1) * width / 2, top: (1 - position.y) * height / 2, visible: position.z > -1 && position.z < 1 }
    }))
  }
  function invalidate() { if (!disposed && !frame) frame = requestAnimationFrame(render) }
  function fit() {
    camera.updateMatrixWorld()
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0), up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1)
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const x of [-89, 89]) for (const z of [-89, 89]) for (const y of [0, 30]) {
      const v = new THREE.Vector3(x, y, z), sx = v.dot(right), sy = v.dot(up)
      minX = Math.min(minX, sx); maxX = Math.max(maxX, sx); minY = Math.min(minY, sy); maxY = Math.max(maxY, sy)
    }
    const left = insets.left || 24, top = insets.top || 180, r = insets.right || 24, bottom = insets.bottom || 260
    const safeW = Math.max(180, width - left - r), safeH = Math.max(180, height - top - bottom)
    const fullH = Math.max((maxY - minY) * height / safeH, (maxX - minX) * height / safeW) * 1.12
    const hh = fullH / 2, hw = hh * width / height
    const shiftX = -(left - r) / width * hw, shiftY = (top - bottom) / height * hh
    camera.left = -hw + shiftX; camera.right = hw + shiftX; camera.top = hh + shiftY; camera.bottom = -hh + shiftY
    camera.updateProjectionMatrix(); invalidate()
  }
  function reset(nextMode = mode) {
    mode = nextMode; controls.target.set(0, 0, 0); camera.position.set(mode === 'top' ? 0 : 120, mode === 'top' ? 300 : 230, mode === 'top' ? .01 : 180); camera.zoom = 1
    controls.enableRotate = mode !== 'top'; controls.minPolarAngle = mode === 'top' ? 0 : .3
    camera.lookAt(controls.target); controls.update(); fit()
  }
  function updateStyle() {
    const hoveredEdge = hovered?.kind === 'edge' ? edgeMeshes.find((e) => e.edge.id === hovered.id)?.edge : null
    const focusId = hovered?.kind === 'node' ? hovered.id : selected
    for (const { node, point, ring, heat } of nodeMeshes) {
      const r = risk[node.area_id], focused = node.area_id === focusId || [hoveredEdge?.a, hoveredEdge?.b].includes(node.area_id)
      point.material.color.set(riskColor(r?.total_score)); point.scale.setScalar(focused ? 1.22 : 1)
      heat.material.color.set(riskColor(r?.total_score)); heat.material.opacity = r ? .85 : .12
      ring.visible = node.area_id === selected || focused
    }
    for (const { edge, mesh } of edgeMeshes) {
      const active = hoveredEdge ? edge.id === hoveredEdge.id : edge.a === focusId || edge.b === focusId
      mesh.material.color.set(active ? '#345fc5' : '#71858f'); mesh.material.opacity = active ? .95 : focusId ? .56 : .7
    }
    links.visible = visibleLinks; invalidate()
  }
  function setHover(hit, event) {
    if (hovered?.id !== hit?.id || hovered?.kind !== hit?.kind) { hovered = hit; updateStyle() }
    callbacks.onHover(hit, event)
    renderer.domElement.style.cursor = hit ? 'pointer' : 'grab'
  }
  function hitAt(event) {
    const rect = renderer.domElement.getBoundingClientRect()
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1)
    raycaster.setFromCamera(pointer, camera)
    return raycaster.intersectObjects(hitTargets.filter((m) => m.parent !== links || visibleLinks), false)[0]?.object.userData || null
  }
  let down = null, moving = false, multiTouch = false
  const activePointers = new Set()
  const onDown = (e) => { activePointers.add(e.pointerId); if(activePointers.size>1)multiTouch=true; down = { x: e.clientX, y: e.clientY }; moving = false; setHover(null, e) }
  const onMove = (e) => {
    if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) moving = true
    if (down) return
    setHover(hitAt(e), e)
  }
  const onUp = (e) => { if (down && !moving && !multiTouch && e.type!=='pointercancel' && Math.hypot(e.clientX - down.x, e.clientY - down.y) <= 5) { const hit = hitAt(e); if (hit?.kind === 'node') callbacks.onSelect(hit.id) } activePointers.delete(e.pointerId); if(!activePointers.size){down=null;multiTouch=false} }
  const onLeave = (e) => { setHover(null, e) }
  const onLost = (e) => { e.preventDefault(); callbacks.onFailure() }
  renderer.domElement.addEventListener('pointerdown', onDown)
  renderer.domElement.addEventListener('pointermove', onMove)
  renderer.domElement.addEventListener('pointerleave', onLeave)
  renderer.domElement.addEventListener('webglcontextlost', onLost)
  window.addEventListener('pointerup', onUp)
  window.addEventListener('pointercancel', onUp)
  controls.addEventListener('change', invalidate)
  controls.addEventListener('start', () => callbacks.onHover(null))
  const observer = new ResizeObserver(() => {
    width = Math.max(1, host.clientWidth); height = Math.max(1, host.clientHeight)
    renderer.setSize(width, height); fit()
  })
  observer.observe(host); reset()
  return {
    update(next) {
      risk = next.risk; selected = next.selected; insets = next.insets
      buildings.visible = next.buildings; visibleLinks = next.links
      if (mode !== next.mode) reset(next.mode)
      fit(); updateStyle()
    },
    reset: () => reset(),
    zoom(factor) { camera.zoom = THREE.MathUtils.clamp(camera.zoom * factor, .6, 3.5); camera.updateProjectionMatrix(); invalidate() },
    pan(x, z) { const offset = new THREE.Vector3(x, 0, z); camera.position.add(offset); controls.target.add(offset); controls.update(); invalidate() },
    focus(id) {
      const n = byId.get(id); if (!n) return
      const offset = new THREE.Vector3(n.x * .45, 0, n.z * .45).sub(controls.target)
      camera.position.add(offset); controls.target.add(offset); controls.update(); invalidate()
    },
    hover(id, event) { setHover(id ? { kind: 'node', id } : null, event) },
    dispose() {
      disposed = true; cancelAnimationFrame(frame); observer.disconnect(); controls.dispose()
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
      renderer.domElement.removeEventListener('pointerdown', onDown); renderer.domElement.removeEventListener('pointermove', onMove); renderer.domElement.removeEventListener('pointerleave', onLeave); renderer.domElement.removeEventListener('webglcontextlost', onLost)
      const geometries = new Set(), materials = new Set()
      scene.traverse((o) => { if(o.isInstancedMesh)o.dispose(); if (o.geometry) geometries.add(o.geometry); if (o.material) materials.add(o.material) })
      geometries.forEach((g) => g.dispose()); materials.forEach((m) => m.dispose()); heatTexture.dispose()
      renderer.dispose(); renderer.domElement.remove()
    },
  }
}
