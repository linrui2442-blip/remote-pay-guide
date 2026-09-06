from pathlib import Path

path = Path('os/frontend/src/App.jsx')
text = path.read_text(encoding='utf-8')

old_import = '  runProductionTask,\n'
new_import = '  runProductionTask,\n  refreshProductionTask,\n'
if text.count(old_import) != 1:
    raise SystemExit(f'expected runProductionTask import once, found {text.count(old_import)}')
text = text.replace(old_import, new_import, 1)

old_state = '  const [githubWorkflow, setGithubWorkflow] = useState("");\n'
new_state = old_state + '  const [refreshingProductionTaskId, setRefreshingProductionTaskId] = useState(null);\n'
if text.count(old_state) != 1:
    raise SystemExit(f'expected githubWorkflow state once, found {text.count(old_state)}')
text = text.replace(old_state, new_state, 1)

old_run = '''  const runTask = (task) => {
    const blocker = taskRunBlocker(task);
    if (blocker) return;
    runProductionTask(task.id).then(refreshProduction);
  };'''
new_run = '''  const runTask = (task) => {
    const blocker = taskRunBlocker(task);
    if (blocker) return;
    runProductionTask(task.id).then(() => {
      refreshProduction();
      apiGet("/assets").then(setAssets).catch(() => {});
    });
  };

  const taskCanRefresh = (task) =>
    ["scheduled", "running"].includes(String(task.status || "").toLowerCase());

  const refreshTask = async (task) => {
    if (!taskCanRefresh(task)) return;
    try {
      setRefreshingProductionTaskId(task.id);
      await refreshProductionTask(task.id);
      refreshProduction();
      apiGet("/assets").then(setAssets).catch(() => {});
    } finally {
      setRefreshingProductionTaskId(null);
    }
  };'''
if text.count(old_run) != 1:
    raise SystemExit(f'expected runTask block once, found {text.count(old_run)}')
text = text.replace(old_run, new_run, 1)

old_table = '''          <div className="table-wrap"><table><thead><tr><th>ID</th><th>类型</th><th>Provider</th><th>状态</th><th>执行</th><th></th></tr></thead><tbody>{productionTasks.map((task) => {
            const blocker = taskRunBlocker(task);
            return <tr key={task.id}><td>#{task.id}</td><td>{task.task_type || "—"}</td><td>{task.provider || "—"}</td><td><Badge tone={task.status === "completed" ? "success" : "neutral"}>{task.status || "created"}</Badge></td><td><Badge tone={blocker ? "neutral" : "success"}>{blocker ? "未就绪" : "可运行"}</Badge>{blocker ? <div className="muted" title={blocker}>{blocker}</div> : null}</td><td className="table-action"><button className="secondary-button" onClick={() => runTask(task)} disabled={Boolean(blocker)} title={blocker || "运行任务"}>运行</button></td></tr>;
          })}</tbody></table></div>'''
new_table = '''          <div className="table-wrap"><table><thead><tr><th>ID</th><th>类型</th><th>Provider</th><th>状态</th><th>执行</th><th></th></tr></thead><tbody>{productionTasks.map((task) => {
            const refreshable = taskCanRefresh(task);
            const terminal = ["completed", "failed"].includes(String(task.status || "").toLowerCase());
            const blocker = refreshable || terminal ? "" : taskRunBlocker(task);
            const refreshing = refreshingProductionTaskId === task.id;
            const executionLabel = terminal ? "已结束" : refreshable ? "等待远程结果" : blocker ? "未就绪" : "可运行";
            const actionTitle = refreshable ? "从 AI Gateway 查询远程任务最新状态" : blocker || "运行任务";
            return <tr key={task.id}><td>#{task.id}</td><td>{task.task_type || "—"}</td><td>{task.provider || "—"}</td><td><Badge tone={task.status === "completed" ? "success" : "neutral"}>{task.status || "created"}</Badge></td><td><Badge tone={!blocker && !terminal ? "success" : "neutral"}>{executionLabel}</Badge>{blocker ? <div className="muted" title={blocker}>{blocker}</div> : null}</td><td className="table-action">{terminal ? <span className="muted">—</span> : <button className="secondary-button" onClick={() => refreshable ? refreshTask(task) : runTask(task)} disabled={Boolean(blocker) || refreshing} title={actionTitle}>{refreshing ? "刷新中…" : refreshable ? "刷新状态" : "运行"}</button>}</td></tr>;
          })}</tbody></table></div>'''
if text.count(old_table) != 1:
    raise SystemExit(f'expected production table once, found {text.count(old_table)}')
text = text.replace(old_table, new_table, 1)

path.write_text(text, encoding='utf-8')
