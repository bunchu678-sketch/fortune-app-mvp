"use client";
import { FormEvent, useEffect, useState } from "react";
import { Organization, productRequest, useProductData } from "../product-client";

type Invitation = { id:string; organization_id:string; alias:string; role:string; email:string;
  delivery_state:string; setup_state:string; expires_at:number|null; mailbox_delivery_confirmed:boolean };
const delivery:Record<string,string>={unsent:"未送信",queued:"送信待ち",sending:"送信処理中",provider_accepted:"送信受付済み（到達未確認）",failed:"送信失敗"};
const setup:Record<string,string>={pending:"初回設定待ち",completed:"初回設定完了",expired:"期限切れ・再発行が必要",cancelled:"招待取消し済み"};

export default function InvitationsPanel({organizations,organizationId=""}:{organizations:Organization[];organizationId?:string}) {
  const invitations=useProductData<Invitation[]>("/api/operations/invitations");
  const [org,setOrg]=useState(organizationId),[alias,setAlias]=useState(""),[role,setRole]=useState("teacher"),[email,setEmail]=useState("");
  const [confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(""),[failure,setFailure]=useState("");
  useEffect(()=>{const timer=window.setInterval(()=>void invitations.reload(),10000);return()=>window.clearInterval(timer);},[invitations.reload]);
  async function action(path:string,body:object) {
    setBusy(true);setMessage("");setFailure("");
    try {await productRequest(path,{method:"POST",body:JSON.stringify(body)});setMessage(path.endsWith("cancel")?"招待を取り消しました。以前のリンクは利用できません。":"送信待ちとして受け付けました。下の送信状態を確認してください。");await invitations.reload();}
    catch(error){setFailure(error instanceof Error?error.message:"招待を処理できませんでした。");}
    finally{setBusy(false);}
  }
  function submit(event:FormEvent) {
    event.preventDefault();const organization=organizations.find(item=>item.id===org);
    if(!window.confirm(`${organization?.display_name}\n${alias}（${role==="teacher"?"先生":"生徒"}）\n送信先：${email}\n\nこの宛先へ無料試用の初回招待を送信しますか？`))return;
    void action("/api/operations/invitations",{organization_id:org,alias,role,email,recipient_confirmed:true,free_trial_confirmed:confirmed});
  }
  // The parent renders this section only after an Operator API succeeds.
  if(invitations.error)return <section><h2>ユーザー招待</h2><p role="alert">{invitations.error}</p></section>;
  return <section aria-label="ユーザー招待"><h2>ユーザー招待</h2>
    <p>招待する本人のメールアドレスを確認して入力します。送信前にはアカウントや初回設定リンクを作りません。</p>
    <p>名前は管理用です。ログインIDはメールアドレスです。</p>
    <p>今回の無料試用は初期費用0円・月額0円です。入金記録・購入証明・自動請求は作成しません。将来の料金変更は別途確認します。</p>
    <form onSubmit={submit}>
      <label>招待対象の名前<input required maxLength={64} autoComplete="off" value={alias} onChange={event=>{setAlias(event.target.value);setEmail("");setConfirmed(false);}} /></label>
      <label>利用者の役割<select value={role} onChange={event=>setRole(event.target.value)}><option value="teacher">先生</option><option value="student">生徒</option></select></label>
      <label>所属する教室・講師名<select required value={org} onChange={event=>setOrg(event.target.value)}><option value="">所属先を選択</option>{organizations.map(item=><option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
      <label>メールアドレス<input type="email" required maxLength={254} autoComplete="off" value={email} onChange={event=>setEmail(event.target.value)} /></label>
      <label className="check"><input type="checkbox" required checked={confirmed} onChange={event=>setConfirmed(event.target.checked)} />この方の無料試用と、役割・所属・送信先を確認しました</label>
      <button disabled={busy||!confirmed}>招待メールを送信</button>
    </form>
    {message?<p role="status">{message}</p>:null}{failure?<p role="alert">{failure}</p>:null}
    <p>リンクは発行から30分・1回限りです。送信受付はメールボックスへの到達保証ではありません。</p>
    <button type="button" disabled={busy} onClick={()=>void invitations.reload()}>状態を更新</button>
    <ul>{invitations.data?.filter(item=>!organizationId||item.organization_id===organizationId).map(item=><li key={item.id}>
      <strong>{item.alias}（{item.role==="teacher"?"先生":"生徒"}）</strong>　{item.email}
      <p>メール：{delivery[item.delivery_state]||"確認が必要"}／設定：{setup[item.setup_state]||"確認が必要"}</p>
      <button type="button" disabled={busy||["completed","cancelled"].includes(item.setup_state)} onClick={()=>{if(window.confirm(`${item.alias}：${item.email}\n同じ所属・役割で再送しますか？旧リンクは失効します。`))void action(`/api/operations/invitations/${item.id}/resend`,{recipient_confirmed:true});}}>招待を再送信</button>
      <button type="button" disabled={busy||["completed","cancelled"].includes(item.setup_state)} onClick={()=>{if(window.confirm(`${item.alias}への招待を取り消しますか？未設定アカウントと発行済みリンクを無効にします。`))void action(`/api/operations/invitations/${item.id}/cancel`,{});}}>招待を取消し</button>
    </li>)}</ul>
  </section>;
}
