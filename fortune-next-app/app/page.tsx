"use client";

import Image from "next/image";
import { CalendarDays, ChevronDown, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { formatJstDate } from "./jst-date";
import GogyoFigure from "./gogyo-figure";

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
  title,
  children,
  eyebrow,
}: {
  title: string;
  children: React.ReactNode;
  eyebrow?: string;
}) {
  return (
    <section className="section">
      <div className="sectionHeading">
        {eyebrow ? <span>{eyebrow}</span> : null}
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function ThinkingBars({ thinking }: { thinking: any }) {
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
                    <span>{label}</span>
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
              <span>{label}</span>
              <b>{Number(rawValue ?? 0)}</b>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ResultView({ result }: { result: FortuneResult }) {
  const starData = result.star_data ?? {};
  const yearlyRows = asRows(result.yearly_flow?.rows);
  const daiunRows = asRows(result.daiun?.rows);
  const specificRows = asRows(result.specific_datetime?.rows);
  const juuniRows = asRows(result.personality?.juuni_unsei?.rows);
  const lifeStageRows = asRows(result.personality?.life_stage_tsuhensei);
  const sekkiWarnings = result.calendar?.boundary_warnings ?? [];
  const variants = result.gogyo_variants ?? {};
  const stages = ["幼年期", "青年期", "成熟期", "老年期"];
  const variantLabels = { A: "元命式のみ", B: "元命式＋鑑定年", C: "元命式＋鑑定年＋大運" } as const;

  return (
    <div className="resultStack">
      <div className="resultSummary">
        <div>
          <span>日干</span>
          <b>{starData.day_tenkan || "未取得"}</b>
        </div>
        <div>
          <span>日支</span>
          <b>{starData.day_chishi || "未取得"}</b>
        </div>
        <div>
          <span>空亡</span>
          <b>{result.kubou || "未入力"}</b>
        </div>
        <div>
          <span>命式</span>
          <b>{result.source_label || "自動計算命式"}</b>
        </div>
      </div>

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

      <Section title="基本情報">
        <PlainTable rows={asRows(result.basic_info)} />
      </Section>

      <Section title="命式表">
        <PlainTable rows={asRows(result.meishiki_table)} />
      </Section>

      <Section title="五行のバランス">
        <div className="gogyoVariants">
          {(["A", "B", "C"] as const).map((code) => {
            const variant = variants[code];
            return <article className="gogyoVariant" key={code}>
              <h3>{code}. {variantLabels[code]}</h3>
              {variant?.status === "available" ? <GogyoFigure gogyo={variant.gogyo} id={`main-${code}`} /> :
                <p className="empty">{variant?.status === "boundary_pending" ? "節入りの確認後に算出します。" : "この条件では算出できません。"}</p>}
              {code === "C" && variant?.daiun ? <p className="empty">対象大運：{variant.daiun.name} {variant.daiun.kanshi}</p> : null}
            </article>;
          })}
        </div>
      </Section>

      <Section title="特殊な命式">
        {asRows(result.special_meishiki?.rows).length ? (
          <PlainTable rows={asRows(result.special_meishiki?.rows)} />
        ) : (
          <p className="empty">{result.special_meishiki?.empty_message}</p>
        )}
      </Section>

      <Section title="元命式から読み取れる性格">
        <div className="textBlock">
          <h3>{starData.day_tenkan || "日干"}の傾向</h3>
          <p>{result.personality?.nikkan?.description || "日干コメントが未登録です。"}</p>
          {result.personality?.nikkan?.keywords ? (
            <p className="keyword">キーワード：{result.personality.nikkan.keywords}</p>
          ) : null}
        </div>
      </Section>

      <Section title="通変星/蔵干通変星から読み取れる性格">
        <div className="cardGrid">
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
        {result.personality?.month_pair?.public_comment ? (
          <div className="textBlock">
            <h3>{result.personality.month_pair.center_star} × {result.personality.month_pair.tsuhensei}</h3>
            <p>{result.personality.month_pair.public_comment}</p>
          </div>
        ) : null}
      </Section>

      <Section title="十二運星から読み取れる性格">
        <div className="cardGrid">
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

      <Section title="考え方の傾向">
        <ThinkingBars thinking={result.personality?.juuni_unsei?.thinking} />
      </Section>

      <Section title="大運・接木運">
        {result.daiun?.message ? <p className="empty">{result.daiun.message}</p> : null}
        <div className="timeline">
          {daiunRows.map((row) => (
            <article className="timelineItem" key={row["大運"]}>
              <span>{row["大運"]} / {row["開始年齢"]}〜{row["終了年齢"]}</span>
              <h3>{row["大運干支"]}｜{row["通変星"]}</h3>
              <p>{row["コメント"]}</p>
              <small>{row["周期"]} / {row["キーワード"]}</small>
            </article>
          ))}
        </div>
      </Section>

      <Section title="今年の運勢の流れ">
        <div className="monthGrid">
          {yearlyRows.map((row) => (
            <article className={`monthCard ${row["空亡"] ? "marked" : ""}`} key={`${row["年"]}-${row["月番号"]}`}>
              <span>{row["月"]}</span>
              <h3>{row["月干支"]}｜{row["通変星"]}</h3>
              <p>{row["コメント"] || row.error}</p>
              {row["キーワード"] ? <small>{row["キーワード"]}</small> : null}
            </article>
          ))}
        </div>
      </Section>

      {specificRows.length ? (
        <Section title="特定日時での運勢">
          <div className="cardGrid">
            {specificRows.map((row) => (
              <article className="infoCard" key={row.label}>
                <span className="cardEyebrow">{row.label} / {row.display_datetime}</span>
                <h3>{row.day_kanchi}｜{row.tsuhensei}</h3>
                <p>{row.comment || row.error}</p>
                {asRows(row.parts).map((part: any) => (
                  <p className="keyword" key={part.display_name}>
                    {part.display_name}: {part.kanchi} / {part.keyword}
                  </p>
                ))}
              </article>
            ))}
          </div>
        </Section>
      ) : null}

      <Section title="今年一年の総合運勢">
        <div className="textBlock">
          <h3>{result.yearly_overall?.year}年 {result.yearly_overall?.year_kanchi}｜{result.yearly_overall?.tsuhensei}</h3>
          <p className="keyword">テーマ：{result.yearly_overall?.theme || "未登録"}</p>
          <p>{result.yearly_overall?.comment || result.yearly_overall?.error}</p>
        </div>
      </Section>

      <details className="memoPanel">
        <summary>
          <ChevronDown size={18} />
          鑑定者用メモ
        </summary>
        <div className="memoContent">
          <h3>現行点数</h3>
          <PlainTable rows={asRows(result.gogyo?.details)} />
          <PlainTable rows={asRows(result.special_meishiki?.rows)} />
          <h3>支援情報</h3>
          <p className="empty">避けたい言葉・表現：未設定</p>
          <p className="empty">伝わりやすい声かけ・伝え方：未設定</p>
          <label>自由記入メモ
            <textarea aria-label="鑑定者用メモの自由記入欄" />
          </label>
          <p className="empty">この入力内容は保存されません。</p>
        </div>
      </details>
    </div>
  );
}

export default function Home() {
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
    setIsLoading(true);
    setError("");
    setResult(null);
    try {
      const base = {
          ...form,
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
      if (manualBoundary && found.length && !boundaries.length) return;
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
      } else {
        setResult(automatic);
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

        <div className="workspace">
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
                <input required type="date" value={form.readingDate} onChange={(event) => updateForm("readingDate", event.target.value)} />
              </label>
            </div>

            <div className="timeLine">
              <label>
                出生時刻
                <input
                  type="time"
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

            <div className="boundaryPanel" role="group" aria-label="節入り・万年暦確認">
              <h3>節入り・万年暦確認</h3>
              {boundaries.length ? boundaries.map((item) => (
                <p className="boundaryJudgement" key={item.kind}>
                  {item.kind === "birth" ? "出生日時" : "鑑定日"}／{item.term_name}　現在のアプリ判定：節入り{item.choice === "before" ? "前" : "後"}
                </p>
              )) : <p>境界付近の場合、鑑定時に現在のアプリ判定を表示します。</p>}
              <label className="checkLine">
                <input type="checkbox" checked={manualBoundary} onChange={(event) => {
                  setManualBoundary(event.target.checked);
                  setBoundaryChoices({});
                  setResult(null);
                }} />
                万年暦の確認結果で判定を修正する
              </label>
            </div>

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
              <button type="submit" disabled={isLoading}>
                {isLoading ? <Loader2 className="spin" size={18} /> : <Sparkles size={18} />}
                {manualBoundary && boundaries.length ? "選択して鑑定を続ける" : "鑑定結果を表示する"}
              </button>
              <button type="button" className="ghostButton" onClick={resetForm}>
                <RotateCcw size={18} />
                <span className="visuallyHidden">リセット</span>
              </button>
            </div>
            {error ? <p className="formError">{error}</p> : null}
          </form>

          <div className="outputPanel">
            {result?.ok ? (
              <ResultView result={result} />
            ) : (
              <div className="emptyState">
                <Sparkles size={30} />
                <h2>鑑定結果</h2>
                <p>入力後、鑑定結果がここに表示されます。</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
