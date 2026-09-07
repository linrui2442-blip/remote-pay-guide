from pathlib import Path


path = Path("os/frontend/src/App.jsx")
text = path.read_text(encoding="utf-8")

old = '''            <div className="platform-card-header"><div className="platform-logo">{platformMark(name)}</div><div><strong>{platformLabel(name)}</strong><span>{item.adapter}</span></div><Badge tone="success">ready</Badge></div>
            <div className="capability-row"><span>发布</span><Badge tone={capability.publish_supported ? "success" : "neutral"}>{capability.publish_supported ? "支持" : "未启用"}</Badge></div>
'''
new = '''            <div className="platform-card-header"><div className="platform-logo">{platformMark(name)}</div><div><strong>{platformLabel(name)}</strong><span>{item.adapter}</span></div><Badge tone={item.publish_ready ? "success" : "neutral"}>{item.publish_ready ? "live" : "placeholder"}</Badge></div>
            <div className="capability-row"><span>发布 Adapter</span><Badge tone={capability.publish_supported ? "success" : "neutral"}>{capability.publish_supported ? "已注册" : "未注册"}</Badge></div>
            <div className="capability-row"><span>实时发布</span><Badge tone={item.publish_ready ? "success" : "neutral"}>{item.publish_ready ? item.execution_mode || "已启用" : "未启用"}</Badge></div>
'''
if text.count(old) != 1:
    raise SystemExit(f"expected platform readiness block once, found {text.count(old)}")
text = text.replace(old, new, 1)

text = text.replace(
    '"Adapter Ready"',
    '"Adapter 已注册"',
)

path.write_text(text, encoding="utf-8")
print("Platform publish readiness UI made truthful")
