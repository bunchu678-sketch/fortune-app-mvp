type Gogyo = { scores?: Record<string, number>; chart_order?: string[] };
const nodes = [
  { x: 220, y: 100, lx: 220, ly: 38, label: "自我の星" },
  { x: 358, y: 198, lx: 358, ly: 140, label: "表現の星" },
  { x: 305, y: 338, lx: 305, ly: 410, label: "魅力の星" },
  { x: 135, y: 338, lx: 135, ly: 410, label: "行動の星" },
  { x: 82, y: 198, lx: 82, ly: 140, label: "知性の星" },
];
const seisho = [0, 1, 2, 3, 4, 0];
const seikoku = [0, 2, 4, 1, 3, 0];
function ends(a: number, b: number, startOffset: number, endOffset: number) {
  const first = nodes[a], last = nodes[b];
  const distance = Math.hypot(last.x - first.x, last.y - first.y);
  const ux = (last.x - first.x) / distance, uy = (last.y - first.y) / distance;
  return [first.x + ux * startOffset, first.y + uy * startOffset, last.x - ux * endOffset, last.y - uy * endOffset];
}
function score(value: unknown) { const number = Number(value ?? 0); return Number.isFinite(number) ? String(Number(number.toFixed(1))) : "0"; }

export default function GogyoFigure({ gogyo, id }: { gogyo: Gogyo; id: string }) {
  const order = gogyo.chart_order ?? [];
  const scores = gogyo.scores ?? {};
  if (order.length !== 5) return <p>五行図の表示データがありません。</p>;
  return <svg className="productGogyoFigure" viewBox="0 0 440 500" role="img" aria-label="五行バランス図">
    <defs>
      <marker id={`${id}-seisho`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#69737a" /></marker>
      <marker id={`${id}-seikoku`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#a65d1c" /></marker>
    </defs>
    {seisho.slice(0, -1).map((a, i) => { const [x1, y1, x2, y2] = ends(a, seisho[i + 1], 38, 42); const radius = Math.max(Math.hypot(x2 - x1, y2 - y1) * 1.55, 68); return <path key={`s${i}`} d={`M ${x1} ${y1} A ${radius} ${radius} 0 0 1 ${x2} ${y2}`} fill="none" stroke="#69737a" strokeWidth="2.8" markerEnd={`url(#${id}-seisho)`} />; })}
    {seikoku.slice(0, -1).map((a, i) => { const [x1, y1, x2, y2] = ends(a, seikoku[i + 1], 42, 42); return <line key={`k${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#a65d1c" strokeWidth="2.3" markerEnd={`url(#${id}-seikoku)`} />; })}
    {nodes.map((node, index) => <g key={node.label}><text x={node.lx} y={node.ly} textAnchor="middle" className="productGogyoRole">{node.label}</text><circle cx={node.x} cy={node.y} r="34" fill="var(--product-panel)" stroke="var(--product-ink)" strokeWidth="2" /><text x={node.x} y={node.y + 6} textAnchor="middle" className="productGogyoValue">{order[index]} {score(scores[order[index]])}</text></g>)}
    <path d="M 100 472 Q 118 458 136 472" fill="none" stroke="#69737a" strokeWidth="2.8" markerEnd={`url(#${id}-seisho)`} /><text x="150" y="477" className="productGogyoLegend">相生</text>
    <line x1="235" y1="472" x2="269" y2="472" stroke="#a65d1c" strokeWidth="2.3" markerEnd={`url(#${id}-seikoku)`} /><text x="281" y="477" className="productGogyoLegend">相剋</text>
  </svg>;
}
