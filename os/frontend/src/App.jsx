import React, {useEffect, useState} from "react";
import {apiGet, getProductionTasks, getProductionStatus, getProductionProviders, createProductionTask, runProductionTask} from "./api";

export default function App(){
 const [system,setSystem]=useState(null);
 const [assets,setAssets]=useState([]);
 const [tasks,setTasks]=useState([]);
 const [platforms,setPlatforms]=useState([]);
 const [metrics,setMetrics]=useState([]);
 const [productionStatus,setProductionStatus]=useState(null);
 const [productionTasks,setProductionTasks]=useState([]);
 const [providers,setProviders]=useState([]);
 const [provider,setProvider]=useState("github");

 const refreshProduction=()=>{
  getProductionStatus().then(setProductionStatus).catch(()=>{});
  getProductionTasks().then(setProductionTasks).catch(()=>{});
  getProductionProviders().then(setProviders).catch(()=>{});
 };

 useEffect(()=>{
  apiGet('/').then(setSystem).catch(()=>setSystem({status:'offline'}));
  apiGet('/assets').then(setAssets).catch(()=>{});
  apiGet('/publish/tasks').then(setTasks).catch(()=>{});
  apiGet('/publish/platforms').then(setPlatforms).catch(()=>{});
  apiGet('/analytics/metrics').then(setMetrics).catch(()=>{});
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

 return <main>
  <h1>Remote Pay Guide OS</h1>
  <h2>System Status</h2><pre>{JSON.stringify(system,null,2)}</pre>
  <h2>Video Assets</h2><pre>{JSON.stringify(assets,null,2)}</pre>
  <h2>Publish Tasks</h2><pre>{JSON.stringify(tasks,null,2)}</pre>
  <h2>Platforms</h2><pre>{JSON.stringify(platforms,null,2)}</pre>
  <h2>Analytics</h2><pre>{JSON.stringify(metrics,null,2)}</pre>
  <h2>Production Center</h2>
  <pre>{JSON.stringify(productionStatus,null,2)}</pre>
  <h3>Production Provider</h3>
  <select value={provider} onChange={e=>setProvider(e.target.value)}>
   <option value="github">GitHub Actions</option>
   <option value="ai_gateway">Local AI</option>
  </select>
  <button onClick={createTask}>Create Production Task</button>
  <pre>{JSON.stringify(providers,null,2)}</pre>
  <h3>Production Tasks</h3>
  <pre>{JSON.stringify(productionTasks,null,2)}</pre>
  {productionTasks.map(task=><button key={task.id} onClick={()=>runTask(task.id)}>Run Task {task.id}</button>)}
 </main>
}
