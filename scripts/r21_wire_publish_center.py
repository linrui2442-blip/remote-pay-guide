from pathlib import Path


path = Path("os/frontend/src/App.jsx")
text = path.read_text(encoding="utf-8")

old_import = 'import DataCenter from "./pages/DataCenter.jsx";\n'
new_import = old_import + 'import PublishCenter from "./pages/PublishCenter.jsx";\n'
if text.count(old_import) != 1:
    raise SystemExit(f"expected DataCenter import once, found {text.count(old_import)}")
text = text.replace(old_import, new_import, 1)

old_render = '''  const renderPublishing = () => (
    <>
      <div className="page-heading compact"><div><span className="eyebrow">PUBLISHING</span><h1>发布中心</h1><p>查看各平台发布状态，并从已发布视频直接采集数据。</p></div></div>
      {analyticsMessage && <div className="notice">{analyticsMessage}</div>}
      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">TASKS</span><h2>发布任务</h2></div><span className="muted">{tasks.length} 条</span></div>
        {tasks.length === 0 ? <EmptyState title="暂无本地发布任务" description="现有 legacy/Postiz 发布记录尚未导入 OS Publish Center。" /> : (
          <div className="table-wrap"><table><thead><tr><th>ID</th><th>平台</th><th>视频</th><th>状态</th><th></th></tr></thead><tbody>{tasks.map((task) => <tr key={task.id}><td>#{task.id}</td><td>{platformLabel(task.platform)}</td><td>{task.platform_video_id || task.video_id || "—"}</td><td><Badge tone={task.status === "published" ? "success" : task.status === "failed" ? "danger" : "neutral"}>{task.status}</Badge></td><td className="table-action">{canCollectTask(task) && <button className="secondary-button" onClick={() => collectTaskAnalytics(task)} disabled={accountReadiness[task.account_id]?.ready !== true}>采集 Analytics</button>}</td></tr>)}</tbody></table></div>
        )}
      </section>
    </>
  );
'''

new_render = '''  const renderPublishing = () => (
    <PublishCenter
      assets={assets}
      tasks={tasks}
      accounts={accounts}
      platforms={platforms}
      accountReadiness={accountReadiness}
      onRefreshTasks={refreshPublishTasks}
      onRefreshAnalytics={refreshAnalytics}
    />
  );
'''

if text.count(old_render) != 1:
    raise SystemExit(
        f"expected legacy renderPublishing once, found {text.count(old_render)}"
    )
text = text.replace(old_render, new_render, 1)
path.write_text(text, encoding="utf-8")
print("PublishCenter wired into App.jsx")
