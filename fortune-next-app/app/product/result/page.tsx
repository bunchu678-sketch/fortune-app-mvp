"use client";

import Link from "next/link";
import { useState } from "react";
import GogyoFigure from "../gogyo-figure";
import { useProductState } from "../product-state";

type Row = Record<string, any>;
const rows = (value: unknown): Row[] => Array.isArray(value) ? value : [];
const value = (item: unknown) => item === null || item === undefined || item === "" || item === "未選択" ? "未入力" : String(item);
const sectionList = [
  ["basic", "基本情報"], ["meishiki", "命式表"], ["gogyo", "五行バランス"], ["special", "特殊な命式"],
  ["nikkan", "元命式から読み取れる性格"], ["tsuhensei", "通変星/蔵干通変星から読み取れる性格"],
  ["juuni", "十二運星から読み取れる性格"], ["thinking", "考え方の傾向"], ["daiun", "大運・接木運"],
  ["yearly", "今年の運勢の流れ"], ["overall", "今年一年の総合運勢"], ["memo", "鑑定者用メモ"],
] as const;
const stages = ["幼年期", "青年期", "成熟期", "老年期"];
const seasonByBranch: Record<string, string> = { 寅: "春", 卯: "春", 辰: "春", 巳: "夏", 午: "夏", 未: "夏", 申: "秋", 酉: "秋", 戌: "秋", 亥: "冬", 子: "冬", 丑: "冬" };
const formatTime = (dateTime: unknown) => dateTime ? String(dateTime).replace("T", " ").slice(0, 16) : "未取得";
const Paragraph = ({ children }: { children: unknown }) => children ? <p className="productParagraph">{String(children)}</p> : null;

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return <section id={id} className="productSection"><h2>{title}</h2>{children}</section>;
}
function SimpleTable({ data }: { data: Row[] }) {
  if (!data.length) return <p>表示できる項目がありません。</p>;
  const columns = Object.keys(data[0]);
  return <table className="productTable"><thead><tr>{columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{data.map((row, index) => <tr key={index}>{columns.map(column => <td key={column}>{value(row[column])}</td>)}</tr>)}</tbody></table>;
}
function Variant({ code, label, variant }: { code: string; label: string; variant: Row | undefined }) {
  return <article className="productVariant"><h3>{code}. {label}</h3>{variant?.status === "available" ? <><GogyoFigure id={`product-${code}`} gogyo={variant.gogyo} /><p className="productVariantScores">{Object.entries(variant.gogyo?.scores ?? {}).map(([element, score]) => `${element} ${score}点`).join("　")}</p>{code === "C" && variant.daiun ? <p>対象大運：{variant.daiun.name} {variant.daiun.kanshi}</p> : null}</> : variant?.status === "boundary_pending" ? <p role="status">節入り境界の前後確認が必要です。判定後に算出します。</p> : <p role="status">{variant?.status === "unavailable" ? "大運を取得できないため算出できません。" : "算出結果を取得できませんでした。"}</p>}</article>;
}
function Thinking({ thinking }: { thinking: Row }) {
  const [open, setOpen] = useState<string | null>(null);
  const groups = [["brain_type", "左脳／右脳"], ["merit_type", "メリット型／デメリット型"], ["goal_type", "目標への向かい方"], ["principle_type", "原理原則型／応用拡大型"], ["work_type", "仕事4分類"]];
  return <div className="productStack">{groups.map(([key, title]) => <article className="productEntry" key={key}><h3>{title}</h3>{Object.entries(thinking?.[key] ?? {}).map(([label, score]) => <div className="productScoreLine" key={label}><span>{label} <button className="productHelp" type="button" title="説明未設定" aria-label={`${label}の説明は未設定`} aria-expanded={open === `${key}-${label}`} onClick={() => setOpen(current => current === `${key}-${label}` ? null : `${key}-${label}`)}>?</button>{open === `${key}-${label}` ? <span className="productHelpText">説明未設定</span> : null}</span><strong>{String(score)}</strong></div>)}</article>)}</div>;
}

export default function ProductResult() {
  const { saved } = useProductState();
  if (!saved) return <main className="productPage"><h1>鑑定結果</h1><p>この画面で確認できる鑑定結果がありません。</p><Link href="/product">鑑定入力へ</Link></main>;
  const { result, form, manualChoices } = saved;
  const basicRows = rows(result.basic_info);
  const basic = (label: string) => basicRows.find(row => row["項目"] === label)?.["内容"];
  const specialRows = rows(result.special_meishiki?.rows);
  const variants = result.gogyo_variants ?? {};
  const life = rows(result.personality?.life_stage_tsuhensei);
  const juuni = rows(result.personality?.juuni_unsei?.rows);
  const daiun = rows(result.daiun?.rows);
  const yearly = rows(result.yearly_flow?.rows);
  const kubou = String(result.kubou ?? "");
  const visibleSections = sectionList.filter(([id]) => id !== "special" || specialRows.length);
  const basicItems: Array<[string, unknown]> = [["氏名", basic("氏名") ?? form.name], ["ふりがな", basic("ふりがな") ?? form.furigana], ["生年月日", basic("生年月日") ?? form.birthDate], ["出生時刻", form.birthTimeUnknown ? "出生時刻不明" : basic("出生時刻") ?? form.birthTime], ["性別", basic("性別") ?? form.gender], ["出生地", basic("出生地") ?? form.birthPlace], ["鑑定日", basic("鑑定日") ?? form.readingDate]];
  if (result.birth_adjustment?.time_adjustment_enabled) basicItems.push(["出生地補正後時刻", result.birth_adjustment.adjusted_birth_datetime]);
  for (const item of rows(saved.boundaryInfo)) {
    const chosen = manualChoices[item.kind];
    basicItems.push([`${item.kind === "birth" ? "出生日時" : "鑑定日"}・${item.term_name}の${chosen ? "手動判定" : "アプリ判定"}`, (chosen ?? item.choice) === "before" ? "節入り前" : "節入り後"]);
  }

  return <main className="productPage productResultPage"><aside className="productToc" aria-label="目次"><p>目次</p><nav>{visibleSections.map(([id, title]) => <a href={`#${id}`} key={id}>{title}</a>)}</nav></aside><div className="productContent"><header className="productResultHeader"><div><h1>鑑定結果</h1><p>商品版の画面確認用</p></div><button disabled title="Phase 5で実装予定">鑑定書を出力（未実装）</button></header>
    <Section id="basic" title="基本情報"><dl className="productBasic">{basicItems.map(([label, item]) => <div key={label}><dt>{label}</dt><dd>{value(item)}</dd></div>)}</dl></Section>
    <Section id="meishiki" title="命式表"><SimpleTable data={rows(result.meishiki_table)} /></Section>
    <Section id="gogyo" title="五行バランス"><div className="productVariantList"><Variant code="A" label="元命式のみ" variant={variants.A} /><Variant code="B" label="元命式＋鑑定年" variant={variants.B} /><Variant code="C" label="元命式＋鑑定年＋大運" variant={variants.C} /></div></Section>
    {specialRows.length ? <Section id="special" title="特殊な命式"><div className="productStack">{specialRows.map((row, index) => <article className="productEntry" key={index}><h3>{row["判定"]}</h3><Paragraph>{row["結果"]}</Paragraph></article>)}</div></Section> : null}
    <Section id="nikkan" title="元命式から読み取れる性格"><div className="productEntry"><h3>{value(result.personality?.nikkan?.tenkan)}の傾向</h3><Paragraph>{result.personality?.nikkan?.description}</Paragraph>{result.personality?.nikkan?.keywords ? <p>キーワード：{result.personality.nikkan.keywords}</p> : null}</div></Section>
    <Section id="tsuhensei" title="通変星/蔵干通変星から読み取れる性格"><div className="productStack">{life.map((row, index) => <article className="productEntry" key={index}><h3>{stages[index] ?? row.stage} <small>（{row.stage}）</small></h3><h4>社会に見せている自分：{value(row.outer)}</h4><Paragraph>{row.outer_comment}</Paragraph><h4>本来の自分：{value(row.inner)}</h4><Paragraph>{row.inner_comment}</Paragraph></article>)}{result.personality?.current_life_stage_pair?.public_comment ? <article className="productEntry"><h3>鑑定日時点の人生段階の組み合わせ</h3><p>{result.personality.current_life_stage_pair.stage}（{result.personality.current_life_stage_pair.age}歳）：{result.personality.current_life_stage_pair.outer} × {result.personality.current_life_stage_pair.inner}</p><Paragraph>{result.personality.current_life_stage_pair.public_comment}</Paragraph></article> : null}</div></Section>
    <Section id="juuni" title="十二運星から読み取れる性格"><div className="productStack">{juuni.map(row => <article className="productEntry" key={row.pillar_key}><h3>{row.pillar_label}：{row.personality_heading} <small>{row.personality_weight}</small></h3><h4>{value(row.juuni_unsei)}</h4><Paragraph>{row.public_comment}</Paragraph></article>)}</div></Section>
    <Section id="thinking" title="考え方の傾向"><Thinking thinking={result.personality?.juuni_unsei?.thinking ?? {}} /></Section>
    <Section id="daiun" title="大運・接木運">{daiun.length ? <><p className="productLegend">空亡の時期：該当する大運を「空亡」と表示</p><div className="productStack">{daiun.map((row, index) => <div key={index}><article className={`productEntry ${kubou.includes(row["地支"]) && row["地支"] ? "productKubou" : ""}`}><h3>{row["大運"]} {kubou.includes(row["地支"]) && row["地支"] ? <small>空亡</small> : null}</h3><p>{row["開始年齢"]}〜{row["終了年齢"]}／{row["目安開始年"]}年〜{row["目安終了年"]}年</p><p>{row["大運干支"]}｜{row["通変星"]}｜{row["十二運星"]}</p><Paragraph>{row["コメント"]}</Paragraph>{row["周期"] || row["キーワード"] ? <p>{row["周期"]}　{row["キーワード"]}</p> : null}</article>{row["次の大運との間が接木運"] ? <article className="productEntry productSetsuboku"><h3>接木運</h3><p>{row["接木運_表示年齢"]}／{row["地支"]} → {row["接木運_次地支"]}</p><p>{seasonByBranch[row["地支"]]} → {seasonByBranch[row["接木運_次地支"]]}</p></article> : null}</div>)}</div></> : <p>{result.daiun?.message || "大運を表示できません。"}</p>}</Section>
    <Section id="yearly" title="今年の運勢の流れ"><p className="productSubtle">{result.yearly_flow?.base_year}年2月〜{Number(result.yearly_flow?.base_year) + 1}年1月</p><p className="productLegend">空亡の時期：該当する月を「空亡」と表示</p><div className="productStack">{yearly.map((row, index) => <article className={`productEntry ${row["空亡"] ? "productKubou" : ""}`} key={index}><h3>{row["月"]} {row["空亡"] ? <small>空亡</small> : null}</h3><p>対象期間：{row["対象期間"] ? `${formatTime(row["対象期間"].start)}（${row["対象期間"].start_term}）〜 ${formatTime(row["対象期間"].end_exclusive)}（${row["対象期間"].end_term}）直前` : "取得できませんでした"}</p><p>{row["月干支"]}｜{row["通変星"]}</p>{row["キーワード"] ? <p>キーワード：{row["キーワード"]}</p> : null}<Paragraph>{row["コメント"] || row.error}</Paragraph></article>)}</div></Section>
    <Section id="overall" title="今年一年の総合運勢"><article className="productEntry"><h3>{result.yearly_overall?.year}年 {result.yearly_overall?.year_kanchi}｜{result.yearly_overall?.tsuhensei}</h3>{result.yearly_overall?.theme ? <p>テーマ：{result.yearly_overall.theme}</p> : null}<Paragraph>{result.yearly_overall?.comment || result.yearly_overall?.error}</Paragraph></article></Section>
    <Section id="memo" title="鑑定者用メモ"><h3>現行の点数表示</h3><SimpleTable data={rows(result.gogyo?.details)} /><div className="productUnset"><p>避けたい言葉・表現：未設定</p><p>伝わりやすい声かけ・伝え方：未設定</p></div><label className="productMemoLabel">自由記入メモ<textarea rows={7} aria-label="鑑定者用メモの自由記入欄" /></label><p className="productSubtle">この入力内容は保存されません。</p></Section>
    <footer className="productFooter"><button disabled title="Phase 4で実装予定">鑑定結果を保存（未実装）</button></footer>
  </div></main>;
}
