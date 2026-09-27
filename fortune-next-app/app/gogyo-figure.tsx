type Gogyo = { scores?: Record<string, number>; chart_order?: string[] };

const nodes = [
  { x: 220, y: 100, lx: 220, ly: 37, label: "自我の星" },
  { x: 358, y: 198, lx: 358, ly: 139, label: "表現の星" },
  { x: 305, y: 338, lx: 305, ly: 410, label: "魅力の星" },
  { x: 135, y: 338, lx: 135, ly: 410, label: "行動の星" },
  { x: 82, y: 198, lx: 82, ly: 139, label: "知性の星" },
];
const seisho = [0, 1, 2, 3, 4, 0];
const seikoku = [0, 2, 4, 1, 3, 0];

function ends(a: number, b: number, startOffset: number, endOffset: number) {
  const first = nodes[a], last = nodes[b];
  const distance = Math.hypot(last.x - first.x, last.y - first.y);
  const ux = (last.x - first.x) / distance, uy = (last.y - first.y) / distance;
  return [first.x + ux * startOffset, first.y + uy * startOffset,
    last.x - ux * endOffset, last.y - uy * endOffset];
}

export default function GogyoFigure({ gogyo, id }: { gogyo: Gogyo; id: string }) {
  const order = gogyo.chart_order ?? [];
  if (order.length !== 5) return <p className="empty">五行図の表示データがありません。</p>;
  const scores = gogyo.scores ?? {};
  const maximum = Math.max(1, ...order.map((element) => Number(scores[element] ?? 0)));
  return <svg className="gogyoFigure" viewBox="0 0 440 500" role="img" aria-label="五行バランス図">
    <defs>
      <marker id={`${id}-seisho`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#9eb9a8" /></marker>
      <marker id={`${id}-seikoku`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#d7a96b" /></marker>
    </defs>
    {seisho.slice(0, -1).map((a, i) => { const [x1, y1, x2, y2] = ends(a, seisho[i + 1], 38, 42); const radius = Math.max(Math.hypot(x2 - x1, y2 - y1) * 1.55, 68); return <path key={`s${i}`} d={`M ${x1} ${y1} A ${radius} ${radius} 0 0 1 ${x2} ${y2}`} fill="none" stroke="#9eb9a8" strokeWidth="2.8" markerEnd={`url(#${id}-seisho)`} />; })}
    {seikoku.slice(0, -1).map((a, i) => { const [x1, y1, x2, y2] = ends(a, seikoku[i + 1], 42, 42); return <line key={`k${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#d7a96b" strokeWidth="2.3" markerEnd={`url(#${id}-seikoku)`} />; })}
    {nodes.map((node, index) => {
      const strength = Math.max(0, Number(scores[order[index]] ?? 0)) / maximum;
      return <g key={node.label}>
        <text x={node.lx} y={node.ly} textAnchor="middle" className="gogyoRole">{node.label}</text>
        <circle cx={node.x} cy={node.y} r={22 + strength * 17} fill="rgba(158, 185, 168, 0.25)" />
        <circle cx={node.x} cy={node.y} r="31" fill="#232825" stroke="#f4efe6" strokeWidth="2" />
        <text x={node.x} y={node.y + 7} textAnchor="middle" className="gogyoElement">{order[index]}</text>
      </g>;
    })}
    <path d="M 100 472 Q 118 458 136 472" fill="none" stroke="#9eb9a8" strokeWidth="2.8" markerEnd={`url(#${id}-seisho)`} /><text x="150" y="477" className="gogyoLegend">相生</text>
    <line x1="235" y1="472" x2="269" y2="472" stroke="#d7a96b" strokeWidth="2.3" markerEnd={`url(#${id}-seikoku)`} /><text x="281" y="477" className="gogyoLegend">相剋</text>
  </svg>;
}
