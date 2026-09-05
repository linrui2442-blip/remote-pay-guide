import React, {useEffect, useState} from "react";
import {apiGet} from "./api";

export default function App(){
 const [system,setSystem]=useState(null);
 const [assets,setAssets]=useState([]);
 const [tasks,setTasks]=useState([]);
 const [platforms,setPlatforms]=useState([]);
 const [metrics,setMetrics]=useState([]);
 useEffect(()=>{
  apiGet('/').then(setSystem).catch(()=>setSystem({status:'offline'}));
  apiGet('/assets').then(setAssets).catch(()=>{});
  apiGet('/publish/tasks').then(setTasks).catch(()=>{});
  apiGet('/publish/platforms').then(setPlatforms).catch(()=>{});
  apiGet('/analytics/metrics').then(setMetrics).catch(()=>{});
 },[]);
 return <main>
  <h1>Remote Pay Guide OS</h1>
  <h2>System Status</h2><pre>{JSON.stringify(system,null,2)}</pre>
  <h2>Video Assets</h2><pre>{JSON.stringify(assets,null,2)}</pre>
  <h2>Publish Tasks</h2><pre>{JSON.stringify(tasks,null,2)}</pre>
  <h2>Platforms</h2><pre>{JSON.stringify(platforms,null,2)}</pre>
  <h2>Analytics</h2><pre>{JSON.stringify(metrics,null,2)}</pre>
 </main>
}
