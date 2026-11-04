import { aggregateGroups, groupNames, type GroupConfig } from "./thinking-groups";

export default function ThinkingGroups({ rows, config }: { rows: any[]; config: GroupConfig }) {
  const { scores, total, missing } = aggregateGroups(rows, config);
  return <div className="threeGroups">
    <h3>十二運星の3グループ割合</h3>
    <div className="threeGroupBar" role="img" aria-label={groupNames.map(name => `${name} ${scores[name]}%`).join("、") + (missing ? `、未算入 ${missing}%` : "")}>
      {groupNames.map((name, index) => <span key={name} data-group={index} style={{ width: `${scores[name]}%` }} />)}
      {missing > 0 ? <span className="groupMissing" style={{ width: `${missing}%` }} /> : null}
    </div>
    <div className="threeGroupLegend">{groupNames.map((name, index) => <span key={name}><i data-group={index} aria-hidden="true" />{name} <b>{scores[name]}%</b></span>)}</div>
    {missing > 0 ? <p className="empty">算入済み {total}%／未算入 {missing}%（十二運星が未入力・未登録の柱は加算せず、100%への換算は行いません）</p> : null}
  </div>;
}
