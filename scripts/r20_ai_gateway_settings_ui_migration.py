from pathlib import Path

path = Path('os/frontend/src/App.jsx')
text = path.read_text(encoding='utf-8')

# API imports.
old_import = '  getAnalyticsCollectorStatus,\n  getNetworkProxySettings,\n'
new_import = '  getAIGatewaySettings,\n  getAnalyticsCollectorStatus,\n  getNetworkProxySettings,\n'
if text.count(old_import) != 1:
    raise SystemExit(f'expected settings import anchor once, found {text.count(old_import)}')
text = text.replace(old_import, new_import, 1)

old_save_import = '  saveNetworkProxySettings,\n  syncAccountAll,\n'
new_save_import = '  saveAIGatewaySettings,\n  saveNetworkProxySettings,\n  syncAccountAll,\n'
if text.count(old_save_import) != 1:
    raise SystemExit(f'expected save import anchor once, found {text.count(old_save_import)}')
text = text.replace(old_save_import, new_save_import, 1)

# Runtime state.
state_anchor = '  const [savingProxy, setSavingProxy] = useState(false);\n'
state_insert = state_anchor + '''  const [aiGatewaySettings, setAIGatewaySettings] = useState({
    video_url: "",
    source: "none",
    configured: false,
    api_key_configured: false,
    local_inference: false,
  });
  const [aiGatewayUrl, setAIGatewayUrl] = useState("");
  const [aiGatewayMessage, setAIGatewayMessage] = useState("");
  const [savingAIGateway, setSavingAIGateway] = useState(false);
'''
if text.count(state_anchor) != 1:
    raise SystemExit(f'expected saving proxy state once, found {text.count(state_anchor)}')
text = text.replace(state_anchor, state_insert, 1)

# Refresh endpoint settings next to proxy settings.
refresh_anchor = '  useEffect(() => {\n'
refresh_block = '''  const refreshAIGateway = () => {
    getAIGatewaySettings()
      .then((settings) => {
        setAIGatewaySettings(settings);
        setAIGatewayUrl(settings.video_url || "");
      })
      .catch((error) => setAIGatewayMessage(error.message));
  };

'''
if text.count(refresh_anchor) != 1:
    raise SystemExit(f'expected useEffect anchor once, found {text.count(refresh_anchor)}')
text = text.replace(refresh_anchor, refresh_block + refresh_anchor, 1)

use_effect_anchor = '    refreshProduction();\n    refreshProxy();\n'
use_effect_new = '    refreshProduction();\n    refreshProxy();\n    refreshAIGateway();\n'
if text.count(use_effect_anchor) != 1:
    raise SystemExit(f'expected refresh calls once, found {text.count(use_effect_anchor)}')
text = text.replace(use_effect_anchor, use_effect_new, 1)

# Save action. The endpoint is non-secret; API key remains environment-only.
save_anchor = '  const collectTaskAnalytics = (task) => {\n'
save_block = '''  const saveAIGateway = async () => {
    try {
      setSavingAIGateway(true);
      setAIGatewayMessage("正在保存 AI Gateway 远程端点…");
      const result = await saveAIGatewaySettings({
        video_url: aiGatewayUrl.trim() || null,
      });
      setAIGatewaySettings(result);
      setAIGatewayUrl(result.video_url || "");
      setAIGatewayMessage(
        result.configured
          ? "AI Gateway 远程视频端点已保存，生产运行时已立即读取新配置。"
          : "AI Gateway 远程视频端点已清除；AI 视频任务会保持未就绪，不会回退到本地模型。"
      );
      refreshProduction();
    } catch (error) {
      setAIGatewayMessage(error.message);
    } finally {
      setSavingAIGateway(false);
    }
  };

'''
if text.count(save_anchor) != 1:
    raise SystemExit(f'expected collect analytics anchor once, found {text.count(save_anchor)}')
text = text.replace(save_anchor, save_block + save_anchor, 1)

# Expand System Settings without disturbing the existing proxy section.
settings_start = text.index('  const renderSettings = () => (')
settings_end = text.index('\n\n  const views =', settings_start)
settings = text[settings_start:settings_end]
settings = settings.replace(
    '<div><span className="eyebrow">SETTINGS</span><h1>系统设置</h1><p>配置 Remote Pay Guide OS 后端访问外部平台时使用的网络代理。</p></div>',
    '<div><span className="eyebrow">SETTINGS</span><h1>系统设置</h1><p>配置网络代理与 AI Remote Production 的远程网关。敏感 API Key 不在这里保存。</p></div>',
    1,
)

closing = '    </>\n  );'
closing_pos = settings.rfind(closing)
if closing_pos < 0:
    raise SystemExit('settings closing fragment not found')

ai_section = '''

      <section className="panel">
        <div className="panel-header">
          <div><span className="section-kicker">AI REMOTE PRODUCTION</span><h2>AI Gateway</h2></div>
          <Badge tone={aiGatewaySettings.configured ? "success" : "neutral"}>
            {aiGatewaySettings.configured ? "远程端点已配置" : "待配置"}
          </Badge>
        </div>

        <div className="settings-form">
          <label className="setting-field">
            <span>视频生成 Relay / Gateway URL</span>
            <input
              value={aiGatewayUrl}
              onChange={(event) => setAIGatewayUrl(event.target.value)}
              placeholder="https://your-relay.example/v1/video"
            />
            <small>只保存非敏感端点地址。生产请求路径：OS → AI Gateway / Relay → 外部 AI 视频服务。</small>
          </label>

          <div className="setting-field">
            <span>运行时安全状态</span>
            <div className="muted">
              配置来源：{aiGatewaySettings.source || "none"} · API Key：{aiGatewaySettings.api_key_configured ? "进程环境已配置" : "未配置"} · 本地推理：禁用
            </div>
            <small>API Key 只允许通过后端进程环境提供，不写入 SQLite、不回传前端。系统不会使用本地 GPU / 本地模型兜底。</small>
          </div>

          <button className="primary-button" onClick={saveAIGateway} disabled={savingAIGateway}>
            {savingAIGateway ? "保存中…" : "保存 AI Gateway"}
          </button>
        </div>

        {aiGatewayMessage ? <div className="notice">{aiGatewayMessage}</div> : null}
      </section>'''
settings = settings[:closing_pos] + ai_section + '\n' + settings[closing_pos:]
text = text[:settings_start] + settings + text[settings_end:]

path.write_text(text, encoding='utf-8')
