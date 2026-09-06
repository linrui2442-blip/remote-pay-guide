import React, {useEffect, useState} from "react";
import {
 apiGet,
 beginYouTubeOAuth,
 createAccount,
 createProductionTask,
 getAccounts,
 getAnalyticsCollectorStatus,
 getProductionProviders,
 getProductionStatus,
 getProductionTasks,
 getYouTubeOAuthStatus,
 runProductionTask,
} from "./api";
import YouTubeOAuthCallback from "./pages/YouTubeOAuthCallback.jsx";

export default function App(){
 if (window.location.pathname === "/oauth/youtube/callback") {
  return <YouTubeOAuthCallback />;
 }

 const [system,setSystem]=useState(null);
 const [assets,setAssets]=useState([]);
 const [tasks,setTasks]=useState([]);
 const [platforms,setPlatforms]=useState([]);
 const [metrics,setMetrics]=useState([]);
 const [accounts,setAccounts]=useState([]);
 const [accountReadiness,setAccountReadiness]=useState({});
 const [youtubeOAuthStatus,setYouTubeOAuthStatus]=useState(null);
 const [newYouTubeAccount,setNewYouTubeAccount]=useState("");
 const [oauthMessage,setOAuthMessage]=useState("");
 const [productionStatus,setProductionStatus]=useState(null);
 const [productionTasks,setProductionTasks]=useState([]);
 const [providers,setProviders]=useState([]);
 const [provider,setProvider]=useState("github");

 const refreshProduction=()=>{
  getProductionStatus().then(setProductionStatus).catch(()=>{});
  getProductionTasks().then(setProductionTasks).catch(()=>{});
  getProductionProviders().then(setProviders).catch(()=>{});
 };

 const refreshAccounts=()=>{
  getAccounts()
   .then(async records=>{
    setAccounts(records);
    const youtubeAccounts=records.filter(
     account=>String(account.platform || "").toLowerCase() === "youtube"
    );
    const statuses=await Promise.all(
     youtubeAccounts.map(async account=>{
      try {
       const status=await getAnalyticsCollectorStatus("youtube", account.id);
       return [account.id,status];
      } catch (error) {
       return [account.id,{ready:false,reason:error.message}];
      }
     })
    );
    setAccountReadiness(Object.fromEntries(statuses));
   })
   .catch(error=>setOAuthMessage(error.message));
 };

 useEffect(()=>{
  apiGet('/').then(setSystem).catch(()=>setSystem({status:'offline'}));
  apiGet('/assets').then(setAssets).catch(()=>{});
  apiGet('/publish/tasks').then(setTasks).catch(()=>{});
  apiGet('/publish/platforms').then(setPlatforms).catch(()=>{});
  apiGet('/analytics/metrics/current').then(setMetrics).catch(()=>{});
  getYouTubeOAuthStatus().then(setYouTubeOAuthStatus).catch(error=>{
   setYouTubeOAuthStatus({configured:false,reason:error.message});
  });
  refreshAccounts();
  refreshProduction();
 },[]);

 const createTask=()=>{
  createProductionTask({
   task_type: provider === "ai_gateway" ? "video_generation" : "video_render",
   provider,
   workflow:"render.yml",
   branch:"main"
  }).then(refreshProduction);
 };

 const runTask=(id)=>runProductionTask(id).then(refreshProduction);

 const addYouTubeAccount=()=>{
  const accountName=newYouTubeAccount.trim();
  if (!accountName) {
   setOAuthMessage("Enter a YouTube account name first.");
   return;
  }
  createAccount({platform:"youtube",account_name:accountName,status:"inactive"})
   .then(()=>{
    setNewYouTubeAccount("");
    setOAuthMessage("YouTube account added. Connect it to authorize publishing and analytics.");
    refreshAccounts();
   })
   .catch(error=>setOAuthMessage(error.message));
 };

 const connectYouTube=(accountId)=>{
  if (youtubeOAuthStatus && youtubeOAuthStatus.configured === false) {
   const missing=(youtubeOAuthStatus.missing_configuration || []).join(", ");
   setOAuthMessage(
    missing
     ? `YouTube OAuth configuration is incomplete: ${missing}`
     : "YouTube OAuth configuration is incomplete."
   );
   return;
  }

  setOAuthMessage("Opening Google authorization...");
  beginYouTubeOAuth(accountId,"full")
   .then(result=>{
    if (!result?.authorization_url) {
     throw new Error("YouTube authorization URL was not returned");
    }
    window.location.assign(result.authorization_url);
   })
   .catch(error=>setOAuthMessage(error.message));
 };

 return <main>
  <h1>Remote Pay Guide OS</h1>
  <h2>System Status</h2><pre>{JSON.stringify(system,null,2)}</pre>

  <h2>Platform Accounts</h2>
  <h3>YouTube OAuth Readiness</h3>
  <pre>{JSON.stringify(youtubeOAuthStatus || {status:"checking"},null,2)}</pre>
  <div>
   <input
    value={newYouTubeAccount}
    onChange={event=>setNewYouTubeAccount(event.target.value)}
    placeholder="YouTube account name"
   />
   <button onClick={addYouTubeAccount}>Add YouTube Account</button>
  </div>
  {oauthMessage && <p>{oauthMessage}</p>}
  {accounts.map(account=><section key={account.id}>
   <strong>{account.platform}: {account.account_name}</strong>
   <span> — {account.status}</span>
   {String(account.platform || "").toLowerCase() === "youtube" && <>
    <button
     onClick={()=>connectYouTube(account.id)}
     disabled={youtubeOAuthStatus?.configured === false}
    >
     Connect YouTube (Publish + Analytics)
    </button>
    <pre>{JSON.stringify(accountReadiness[account.id] || {status:"checking"},null,2)}</pre>
   </>}
  </section>)}

  <h2>Video Assets</h2><pre>{JSON.stringify(assets,null,2)}</pre>
  <h2>Publish Tasks</h2><pre>{JSON.stringify(tasks,null,2)}</pre>
  <h2>Platforms</h2><pre>{JSON.stringify(platforms,null,2)}</pre>
  <h2>Current Analytics</h2><pre>{JSON.stringify(metrics,null,2)}</pre>
  <h2>Production Center</h2>
  <pre>{JSON.stringify(productionStatus,null,2)}</pre>
  <h3>Production Provider</h3>
  <select value={provider} onChange={e=>setProvider(e.target.value)}>
   <option value="github">GitHub Actions</option>
   <option value="ai_gateway">AI Gateway (Remote)</option>
  </select>
  <button onClick={createTask}>Create Production Task</button>
  <pre>{JSON.stringify(providers,null,2)}</pre>
  <h3>Production Tasks</h3>
  <pre>{JSON.stringify(productionTasks,null,2)}</pre>
  {productionTasks.map(task=><button key={task.id} onClick={()=>runTask(task.id)}>Run Task {task.id}</button>)}
 </main>
}
