"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CalendarDays, ChevronDown, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { formatJstDate } from "./jst-date";
import GogyoFigure from "./gogyo-figure";
import { useFortuneState } from "./fortune-state";

type FortuneForm = {
  name: string;
  furigana: string;
  birthDate: string;
  birthTime: string;
  birthTimeUnknown: boolean;
  birthPlace: string;
  gender: string;
  consultation: string;
  readingDate: string;
  includeKanteiYearGogyoEffects: boolean;
  specificDatetimeEnabled: boolean;
  specificDatetimeCandidates: Array<{ date: string; time: string }>;
};

type SekkiBoundaryWarning = {
  code: string;
  level: string;
  message: string;
  term_name?: string;
  boundary_datetime?: string;
};

type FortuneResult = {
  ok?: boolean;
  errors?: string[];
  calendar?: {
    boundary_warnings?: SekkiBoundaryWarning[];
    auto_boundaries?: BoundaryJudgement[];
  };
  [key: string]: any;
};

type BoundaryChoice = "before" | "after";
type BoundaryJudgement = {
  kind: "birth" | "reading";
  term_name: string;
  boundary_datetime: string;
  choice: BoundaryChoice;
};

const API_BASE = (process.env.NEXT_PUBLIC_FORTUNE_API_URL ?? "").replace(/\/+$/, "");

const prefectures = [
  "未選択",
  "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
  "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
  "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
  "岐阜県", "静岡県", "愛知県", "三重県",
  "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
  "鳥取県", "島根県", "岡山県", "広島県", "山口県",
  "徳島県", "香川県", "愛媛県", "高知県",
  "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県",
  "沖縄県",
];

const todayIso = () => new Date().toISOString().slice(0, 10);

const defaultForm = (): FortuneForm => ({
  name: "",
  furigana: "",
  birthDate: "1950-01-01",
  birthTime: "00:00",
  birthTimeUnknown: false,
  birthPlace: "未選択",
  gender: "未選択",
  consultation: "",
  readingDate: formatJstDate(new Date()),
  includeKanteiYearGogyoEffects: true,
  specificDatetimeEnabled: false,
  specificDatetimeCandidates: [
    { date: todayIso(), time: "14:00" },
    { date: todayIso(), time: "10:00" },
    { date: todayIso(), time: "09:00" },
  ],
});

const sectionList = [
  ["basic", "基本情報"], ["meishiki", "命式表"], ["gogyo", "五行バランス"],
  ["special", "特殊な命式"], ["nikkan", "元命式から読み取れる性格"],
  ["tsuhensei", "通変星/蔵干通変星から読み取れる性格"],
  ["juuni", "十二運星から読み取れる性格"], ["thinking", "考え方の傾向"],
  ["daiun", "大運・接木運"], ["yearly", "今年の運勢の流れ"],
  ["overall", "今年一年の総合運勢"], ["memo", "鑑定者用メモ"],
] as const;
const seasonByBranch: Record<string, string> = {
  寅: "春", 卯: "春", 辰: "春", 巳: "夏", 午: "夏", 未: "夏",
  申: "秋", 酉: "秋", 戌: "秋", 亥: "冬", 子: "冬", 丑: "冬",
};
const formatTime = (value: unknown) => value ? String(value).replace("T", " ").slice(0, 16) : "未取得";

function percent(value: number, total: number) {
  if (!total) return 0;
  return Math.max(0, Math.min(100, Math.round((value / total) * 100)));
}

function asRows(value: any): any[] {
  return Array.isArray(value) ? value : [];
}

function PlainTable({ rows }: { rows: any[] }) {
  if (!rows.length) return <p className="empty">表示できる項目がありません。</p>;
  const columns = Object.keys(rows[0]);
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Section({
  id,
  title,
  children,
  eyebrow,
}: {
  id?: string;
  title: string;
  children: React.ReactNode;
  eyebrow?: string;
}) {
  return (
    <section className="section" id={id}>
      <div className="sectionHeading">
        {eyebrow ? <span>{eyebrow}</span> : null}
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function ThinkingBars({ thinking }: { thinking: any }) {
  const [openHelp, setOpenHelp] = useState<string | null>(null);
  const help = (key: string, label: string) => <>
    <button type="button" className="thinkingHelp" title="説明未設定"
      aria-label={`${label}の説明は未設定`} aria-expanded={openHelp === key}
      onClick={() => setOpenHelp((current) => current === key ? null : key)}>?</button>
    {openHelp === key ? <span className="thinkingHelpText">説明未設定</span> : null}
  </>;
  const groups = [
    ["brain_type", "左脳／右脳"],
    ["merit_type", "メリット型／デメリット型"],
    ["goal_type", "目標への向かい方"],
    ["principle_type", "原理原則型／応用拡大型"],
  ];
  return (
    <div className="thinkingGrid">
      {groups.map(([key, title]) => {
        const scores = thinking?.[key] ?? {};
        const total = Object.values(scores).reduce((sum: number, value) => sum + Number(value ?? 0), 0);
        return (
          <div className="miniPanel" key={key}>
            <h3>{title}</h3>
            {Object.entries(scores).map(([label, rawValue]) => {
              const value = Number(rawValue ?? 0);
              return (
                <div className="scoreLine" key={label}>
                  <div className="scoreMeta">
                    <span>{label} {help(`${key}-${label}`, label)}</span>
                    <b>{value}</b>
                  </div>
                  <div className="scoreTrack">
                    <div style={{ width: `${percent(value, total)}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
      <div className="miniPanel wide">
        <h3>仕事4分類</h3>
        <div className="workGrid">
          {Object.entries(thinking?.work_type ?? {}).map(([label, rawValue]) => (
            <div className="workTile" key={label}>
              <span>{label} {help(`work-${label}`, label)}</span>
              <b>{Number(rawValue ?? 0)}</b>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ResultView({ result, form, manualChoices }: {
  result: FortuneResult;
  form: FortuneForm;
  manualChoices: Partial<Record<BoundaryJudgement["kind"], BoundaryChoice>>;
}) {
  const starData = result.star_data ?? {};
  const yearlyRows = asRows(result.yearly_flow?.rows);
  const daiunRows = asRows(result.daiun?.rows);
  const specificRows = asRows(result.specific_datetime?.rows);
  const specialRows = asRows(result.special_meishiki?.rows);
  const juuniRows = asRows(result.personality?.juuni_unsei?.rows);
  const lifeStageRows = asRows(result.personality?.life_stage_tsuhensei);
  const sekkiWarnings = result.calendar?.boundary_warnings ?? [];
  const variants = result.gogyo_variants ?? {};
  const stages = ["幼年期", "青年期", "成熟期", "老年期"];
  const variantLabels = { A: "元命式のみ", B: "元命式＋鑑定年", C: "元命式＋鑑定年＋大運" } as const;
  const basicValue = (label: string) => asRows(result.basic_info).find((row) => row["項目"] === label)?.["内容"];
  const filled = (value: unknown) => value && value !== "未選択" ? String(value) : "未入力";
  const basicRows = [
    ["氏名", basicValue("氏名") ?? form.name],
    ["ふりがな", basicValue("ふりがな") ?? form.furigana],
    ["生年月日", basicValue("生年月日") ?? form.birthDate],
    ["出生時刻", basicValue("出生時刻")],
    ["性別", basicValue("性別") ?? form.gender],
    ["出生地", basicValue("出生地") ?? form.birthPlace],
    ["鑑定日", basicValue("鑑定日") ?? form.readingDate],
  ].map(([label, value]) => ({ "項目": label, "内容": filled(value) }));
  if (result.birth_adjustment?.time_adjustment_enabled) {
    basicRows.push({ "項目": "出生地補正後時刻", "内容": formatTime(result.birth_adjustment.adjusted_birth_datetime) });
  }
  for (const [kind, choice] of Object.entries(manualChoices)) {
    if (choice) basicRows.push({ "項目": `${kind === "birth" ? "出生日時" : "鑑定日"}の節入り判定`,
      "内容": `万年暦確認により節入り${choice === "before" ? "前" : "後"}を採用` });
  }
  const kubou = String(result.kubou ?? "");
  const currentStage = result.personality?.current_life_stage_pair;
  const currentStageName = typeof currentStage?.age === "number"
    ? stages[currentStage.age < 5 ? 0 : currentStage.age < 30 ? 1 : currentStage.age < 65 ? 2 : 3] : "";

  return (
    <div className="resultStack">
      <Section id="basic" title="基本情報">
        <PlainTable rows={basicRows} />
      </Section>

      {sekkiWarnings.length ? (
        <div className="sekkiWarningList" aria-live="polite">
          {sekkiWarnings.map((warning, index) => (
            <p className="sekkiWarning" key={`${warning.code}-${warning.term_name ?? index}`}>
              {warning.message}
              {warning.term_name ? ` 対象節気: ${warning.term_name}` : ""}
            </p>
          ))}
        </div>
      ) : null}

      <Section id="meishiki" title="命式表">
        <PlainTable rows={asRows(result.meishiki_table)} />
      </Section>

      <Section id="gogyo" title="五行バランス">
        <div className="gogyoVariants">
          {(["A", "B", "C"] as const).map((code) => {
            const variant = variants[code];
            return <article className="gogyoVariant" key={code}>
              <h3>{code}. {variantLabels[code]}</h3>
              {variant?.status === "available" ? <GogyoFigure gogyo={variant.gogyo} id={`main-${code}`} /> :
                <p className="empty" role="status">{variant?.status === "boundary_pending" ? "節入りの確認後に算出します。" : variant?.status === "unavailable" ? "大運を取得できないため算出できません。" : "算出結果を取得できませんでした。"}</p>}
              {code === "C" && variant?.daiun ? <p className="empty">対象大運：{variant.daiun.name} {variant.daiun.kanshi}</p> : null}
            </article>;
          })}
        </div>
      </Section>

      {specialRows.length ? <Section id="special" title="特殊な命式">
        <div className="specialList">{specialRows.map((row, index) => <article className="infoCard" key={index}>
          <h3>{row["判定"]}</h3><p>{row["結果"]}</p>
        </article>)}</div>
      </Section> : null}

      <Section id="nikkan" title="元命式から読み取れる性格">
        <div className="textBlock">
          <h3>{starData.day_tenkan || "日干"}の傾向</h3>
          <p>{result.personality?.nikkan?.description || "日干コメントが未登録です。"}</p>
          {result.personality?.nikkan?.keywords ? (
            <p className="keyword">キーワード：{result.personality.nikkan.keywords}</p>
          ) : null}
        </div>
      </Section>

      <Section id="tsuhensei" title="通変星/蔵干通変星から読み取れる性格">
        <div className="stageList">
          {lifeStageRows.map((row, index) => (
            <article className="infoCard" key={row.stage}>
              <span className="cardEyebrow">{stages[index] ?? ""}</span>
              <h3>社会に見せている自分：{row.outer || "－"}</h3>
              {row.outer_comment ? <p>{row.outer_comment}</p> : null}
              <h3 className="stageInner">本来の自分：{row.inner || "－"}</h3>
              {row.inner_comment ? <p>{row.inner_comment}</p> : null}
            </article>
          ))}
        </div>
        {currentStage?.public_comment ? <div className="textBlock">
          <h3>鑑定日時点の人生段階の組み合わせ</h3>
          <p>{currentStageName}：{currentStage.outer} × {currentStage.inner}</p>
          <p>{currentStage.public_comment}</p>
        </div> : null}
        {result.personality?.month_pair?.public_comment ? (
          <div className="textBlock">
            <h3>{result.personality.month_pair.center_star} × {result.personality.month_pair.tsuhensei}</h3>
            <p>{result.personality.month_pair.public_comment}</p>
          </div>
        ) : null}
      </Section>

      <Section id="juuni" title="十二運星から読み取れる性格">
        <div className="juuniList">
          {juuniRows.map((row) => (
            <article className="infoCard" key={row.pillar_key}>
              <span className="cardEyebrow">{row.pillar_label} / {row.personality_weight}</span>
              <h3>{row.personality_heading}：{row.juuni_unsei}</h3>
              <p>{row.public_comment || "コメント未登録"}</p>
              <p className="keyword">{row.keywords}</p>
            </article>
          ))}
        </div>
      </Section>

      <Section id="thinking" title="考え方の傾向">
        <ThinkingBars thinking={result.personality?.juuni_unsei?.thinking} />
      </Section>

      <Section id="daiun" title="大運・接木運">
        {result.daiun?.message ? <p className="empty">{result.daiun.message}</p> : null}
        {daiunRows.length ? <p className="empty">空亡の時期：該当する大運を「空亡」と表示</p> : null}
        <div className="timeline">
          {daiunRows.map((row) => <div className="timelineGroup" key={row["大運"]}>
            <article className={`timelineItem ${row["地支"] && kubou.includes(row["地支"]) ? "marked" : ""}`}>
              <span>{row["大運"]} {row["地支"] && kubou.includes(row["地支"]) ? "空亡" : ""}</span>
              <h3>{row["大運干支"]}｜{row["通変星"]}｜{row["十二運星"]}</h3>
              <p>{row["開始年齢"]}〜{row["終了年齢"]}／{row["目安開始年"]}年〜{row["目安終了年"]}年</p>
              <p>{row["コメント"]}</p>
              <small>{row["周期"]} / {row["キーワード"]}</small>
            </article>
            {row["次の大運との間が接木運"] ? <article className="timelineItem setsubokuItem">
              <h3>接木運</h3>
              <p>{row["接木運_表示年齢"]}／{row["地支"]} → {row["接木運_次地支"]}</p>
              <p>{seasonByBranch[row["地支"]]} → {seasonByBranch[row["接木運_次地支"]]}</p>
            </article> : null}
          </div>)}
        </div>
      </Section>

      <Section id="yearly" title="今年の運勢の流れ">
        <p className="empty">{result.yearly_flow?.base_year}年2月〜{Number(result.yearly_flow?.base_year) + 1}年1月</p>
        <p className="empty">空亡の時期：該当する月を「空亡」と表示</p>
        <div className="monthGrid">
          {yearlyRows.map((row) => (
            <article className={`monthCard ${row["空亡"] ? "marked" : ""}`} key={`${row["年"]}-${row["月番号"]}`}>
              <span>{row["月"]} {row["空亡"] ? "空亡" : ""}</span>
              <p>対象期間：{row["対象期間"] ? `${formatTime(row["対象期間"].start)}（${row["対象期間"].start_term}）〜 ${formatTime(row["対象期間"].end_exclusive)}（${row["対象期間"].end_term}）直前` : "取得できませんでした"}</p>
              <h3>{row["月干支"]}｜{row["通変星"]}</h3>
              <p>{row["コメント"] || row.error}</p>
              {row["キーワード"] ? <small>{row["キーワード"]}</small> : null}
            </article>
          ))}
        </div>
      </Section>

      <Section id="overall" title="今年一年の総合運勢">
        <div className="textBlock">
          <h3>{result.yearly_overall?.year}年 {result.yearly_overall?.year_kanchi}｜{result.yearly_overall?.tsuhensei}</h3>
          <p className="keyword">テーマ：{result.yearly_overall?.theme || "未登録"}</p>
          <p>{result.yearly_overall?.comment || result.yearly_overall?.error}</p>
        </div>
      </Section>

      {specificRows.length ? <Section id="specific" title="特定日時での運勢">
        <div className="cardGrid">{specificRows.map((row) => <article className="infoCard" key={row.label}>
          <span className="cardEyebrow">{row.label} / {row.display_datetime}</span>
          <h3>{row.day_kanchi}｜{row.tsuhensei}</h3>
          <p>{row.comment || row.error}</p>
          {asRows(row.parts).map((part: any) => <p className="keyword" key={part.display_name}>
            {part.display_name}: {part.kanchi} / {part.keyword}
          </p>)}
        </article>)}</div>
      </Section> : null}

      <details id="memo" className="memoPanel">
        <summary>
          <ChevronDown size={18} />
          鑑定者用メモ
        </summary>
        <div className="memoContent">
          <h3>支援情報</h3>
          <p className="empty">避けたい言葉・表現：未設定</p>
          <p className="empty">伝わりやすい声かけ・伝え方：未設定</p>
          <h3>現行点数</h3>
          <PlainTable rows={asRows(result.gogyo?.details)} />
          <label>自由記入メモ
            <textarea aria-label="鑑定者用メモの自由記入欄" />
          </label>
          <p className="empty">この入力内容は保存されません。</p>
        </div>
      </details>
    </div>
  );
}

export default function MainFortune({ mode }: { mode: "input" | "result" }) {
  const router = useRouter();
  const { saved, setSaved } = useFortuneState();
  const [form, setForm] = useState<FortuneForm>(() => defaultForm());
  const [result, setResult] = useState<FortuneResult | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [candidateCount, setCandidateCount] = useState(1);
  const [manualBoundary, setManualBoundary] = useState(false);
  const [boundaries, setBoundaries] = useState<BoundaryJudgement[]>([]);
  const [boundaryChoices, setBoundaryChoices] = useState<Partial<Record<BoundaryJudgement["kind"], BoundaryChoice>>>({});

  const visibleCandidates = useMemo(
    () => form.specificDatetimeCandidates.slice(0, candidateCount),
    [candidateCount, form.specificDatetimeCandidates],
  );

  function updateForm<K extends keyof FortuneForm>(key: K, value: FortuneForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setBoundaries([]);
    setBoundaryChoices({});
    setResult(null);
  }

  function updateCandidate(index: number, field: "date" | "time", value: string) {
    setForm((current) => {
      const nextCandidates = [...current.specificDatetimeCandidates];
      nextCandidates[index] = { ...nextCandidates[index], [field]: value };
      return { ...current, specificDatetimeCandidates: nextCandidates };
    });
    setBoundaries([]);
    setBoundaryChoices({});
    setResult(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.birthDate || (!form.birthTimeUnknown && !form.birthTime)) {
      setError("生年月日と出生時刻、または「出生時刻不明」を入力してください。");
      return;
    }
    setIsLoading(true);
    setError("");
    setResult(null);
    try {
      const base = {
          ...form,
          readingDate: form.readingDate || formatJstDate(new Date()),
          productAutoBoundary: true,
          includeGogyoVariants: true,
          specificDatetimeCandidates: form.specificDatetimeEnabled ? visibleCandidates : [],
      };
      async function request(payload: Record<string, unknown>): Promise<FortuneResult> {
        const response = await fetch(`${API_BASE}/api/fortune`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        return response.json();
      }
      const automatic = await request(base);
      if (!automatic.ok) {
        setError(asRows(automatic.errors).join(" / ") || "鑑定結果を取得できませんでした。");
        return;
      }
      const found = automatic.calendar?.auto_boundaries ?? [];
      setBoundaries(found);
      if (found.length && !boundaries.length) return;
      if (manualBoundary && found.some((item) => !boundaryChoices[item.kind])) {
        setError("修正する境界の前後を選択してください。");
        return;
      }
      if (manualBoundary && found.length) {
        const selected = await request({
          ...base,
          boundarySelections: Object.fromEntries(found.map((item) => [
            item.kind, { boundary_datetime: item.boundary_datetime, choice: boundaryChoices[item.kind] },
          ])),
        });
        if (!selected.ok) {
          setError(asRows(selected.errors).join(" / ") || "鑑定結果を取得できませんでした。");
          return;
        }
        setResult(selected);
        setSaved({ result: selected, form, manualChoices: Object.fromEntries(
          found.map((item) => [item.kind, boundaryChoices[item.kind]]),
        ) as Record<string, BoundaryChoice> });
        router.push("/result");
      } else {
        setResult(automatic);
        setSaved({ result: automatic, form, manualChoices: {} });
        router.push("/result");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "APIに接続できませんでした。");
    } finally {
      setIsLoading(false);
    }
  }

  function resetForm() {
    setForm(defaultForm());
    setResult(null);
    setError("");
    setCandidateCount(1);
    setManualBoundary(false);
    setBoundaries([]);
    setBoundaryChoices({});
  }

  if (mode === "result") {
    if (!saved) return <main className="appShell resultMissing">
      <h1>鑑定結果</h1><p>この画面で確認できる鑑定結果がありません。</p>
      <Link href="/">基本情報入力へ戻る</Link>
    </main>;
    const specialRows = asRows(saved.result.special_meishiki?.rows);
    const visibleSections: Array<readonly [string, string]> = sectionList.filter(([id]) => id !== "special" || specialRows.length);
    if (asRows(saved.result.specific_datetime?.rows).length) {
      visibleSections.splice(visibleSections.findIndex(([id]) => id === "memo"), 0, ["specific", "特定日時での運勢"]);
    }
    return <main className="appShell resultPage">
      <div className="resultLayout">
        <aside className="resultToc" aria-label="目次"><h2>目次</h2><nav>
          {visibleSections.map(([id, title]) => <a key={id} href={`#${id}`}>{title}</a>)}
        </nav></aside>
        <div className="resultContent">
          <header className="resultPageHeader"><div><p>四柱推命 鑑定補助</p><h1>鑑定結果</h1></div>
            <button type="button" disabled title="Phase 5で実装予定">鑑定書を出力（未実装）</button>
          </header>
          <ResultView result={saved.result} form={saved.form as FortuneForm}
            manualChoices={saved.manualChoices} />
          <footer className="resultFooter"><button type="button" disabled title="Phase 4で実装予定">鑑定結果を保存（未実装）</button></footer>
        </div>
      </div>
    </main>;
  }

  return (
    <main>
      <div className="appShell">
        <header className="topBar">
          <div className="brandMark">
            <Image src="/logo_white.png" alt="四柱推命ロゴ" width={76} height={76} priority />
          </div>
          <div>
            <p>四柱推命 鑑定補助</p>
            <h1>鑑定結果を、見せる画面へ。</h1>
          </div>
        </header>

        <div className="workspace inputWorkspace">
          <form className="inputPanel" onSubmit={submit}>
            <div className="panelTitle">
              <CalendarDays size={20} />
              <h2>基本情報</h2>
            </div>

            <label>
              氏名
              <input value={form.name} onChange={(event) => updateForm("name", event.target.value)} />
            </label>
            <label>
              ふりがな
              <input value={form.furigana} onChange={(event) => updateForm("furigana", event.target.value)} />
            </label>
            <div className="fieldPair">
              <label>
                生年月日
                <input required type="date" value={form.birthDate} onChange={(event) => updateForm("birthDate", event.target.value)} />
              </label>
              <label>
                鑑定日
                <input type="date" value={form.readingDate} onChange={(event) => updateForm("readingDate", event.target.value)} />
              </label>
            </div>

            <div className="timeLine">
              <label>
                出生時刻
                <input
                  type="time"
                  required={!form.birthTimeUnknown}
                  value={form.birthTime}
                  disabled={form.birthTimeUnknown}
                  onChange={(event) => updateForm("birthTime", event.target.value)}
                />
              </label>
              <label className="checkLine">
                <input
                  type="checkbox"
                  checked={form.birthTimeUnknown}
                  onChange={(event) => updateForm("birthTimeUnknown", event.target.checked)}
                />
                出生時刻不明
              </label>
            </div>

            <div className="fieldPair">
              <label>
                出生地
                <select value={form.birthPlace} onChange={(event) => updateForm("birthPlace", event.target.value)}>
                  {prefectures.map((prefecture) => <option key={prefecture}>{prefecture}</option>)}
                </select>
              </label>
              <label>
                性別
                <select value={form.gender} onChange={(event) => updateForm("gender", event.target.value)}>
                  <option>未選択</option>
                  <option>男性</option>
                  <option>女性</option>
                  <option>その他・回答しない</option>
                </select>
              </label>
            </div>

            <label>
              相談内容
              <textarea value={form.consultation} onChange={(event) => updateForm("consultation", event.target.value)} />
            </label>

            <label className="checkLine prominent">
              <input
                type="checkbox"
                checked={form.specificDatetimeEnabled}
                onChange={(event) => updateForm("specificDatetimeEnabled", event.target.checked)}
              />
              特定の日時について占う
            </label>

            {form.specificDatetimeEnabled ? (
              <div className="candidateBox">
                <label>
                  候補数
                  <select value={candidateCount} onChange={(event) => setCandidateCount(Number(event.target.value))}>
                    <option value={1}>1</option>
                    <option value={2}>2</option>
                    <option value={3}>3</option>
                  </select>
                </label>
                {visibleCandidates.map((candidate, index) => (
                  <div className="fieldPair" key={index}>
                    <label>
                      候補{index + 1} 日付
                      <input type="date" value={candidate.date} onChange={(event) => updateCandidate(index, "date", event.target.value)} />
                    </label>
                    <label>
                      候補{index + 1} 時刻
                      <input type="time" value={candidate.time} onChange={(event) => updateCandidate(index, "time", event.target.value)} />
                    </label>
                  </div>
                ))}
              </div>
            ) : null}

            {boundaries.length ? <div className="boundaryPanel" role="group" aria-label="節入り・万年暦確認">
              <h3>節入り・万年暦確認</h3>
              {boundaries.map((item) => (
                <p className="boundaryJudgement" key={item.kind}>
                  {item.kind === "birth" ? "出生日時" : "鑑定日"}／{item.term_name}　現在のアプリ判定：節入り{item.choice === "before" ? "前" : "後"}
                </p>
              ))}
              <label className="checkLine">
                <input type="checkbox" checked={manualBoundary} onChange={(event) => {
                  setManualBoundary(event.target.checked);
                  setBoundaryChoices({});
                  setResult(null);
                }} />
                万年暦の確認結果で判定を修正する
              </label>
            </div> : null}

            {manualBoundary && boundaries.length ? (
              <div className="boundaryPanel" role="group" aria-label="節入り境界の確認">
                <h3>万年暦の確認結果</h3>
                {boundaries.map((item) => {
                  const beforeLabel = item.kind === "reading" ? "立春前として鑑定" : "節入り前として鑑定";
                  const afterLabel = item.kind === "reading" ? "立春後として鑑定" : "節入り後として鑑定";
                  return (
                    <fieldset className="boundaryChoice" key={item.kind}>
                      <legend>{item.kind === "birth" ? "出生時刻" : "鑑定日"}</legend>
                      <p>計算上の{item.term_name}時刻は {item.boundary_datetime.replace("T", " ").slice(0, 16)} 頃です。</p>
                      <div className="boundaryOptions">
                        {(["before", "after"] as const).map((choice) => (
                          <label className="checkLine" key={choice}>
                            <input
                              type="radio"
                              name={`boundary-${item.kind}`}
                              checked={boundaryChoices[item.kind] === choice}
                              onChange={() => {
                                setBoundaryChoices((current) => ({ ...current, [item.kind]: choice }));
                                setResult(null);
                              }}
                            />
                            {choice === "before" ? beforeLabel : afterLabel}
                          </label>
                        ))}
                      </div>
                    </fieldset>
                  );
                })}
              </div>
            ) : null}

            <div className="buttonRow">
              <button type="submit" disabled={isLoading || !form.birthDate || (!form.birthTimeUnknown && !form.birthTime)}>
                {isLoading ? <Loader2 className="spin" size={18} /> : <Sparkles size={18} />}
                {manualBoundary && boundaries.length ? "選択して鑑定を続ける" : boundaries.length ? "アプリ判定で鑑定結果へ" : "鑑定結果を表示する"}
              </button>
              <button type="button" className="ghostButton" onClick={resetForm}>
                <RotateCcw size={18} />
                <span className="visuallyHidden">リセット</span>
              </button>
            </div>
            {error ? <p className="formError">{error}</p> : null}
          </form>

        </div>
      </div>
    </main>
  );
}
