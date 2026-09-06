from pathlib import Path

path = Path('.github/workflows/os-data-center-verification.yml')
text = path.read_text(encoding='utf-8')

old = '''          future_runtime = get_platform_runtime_capabilities('future-platform')
          assert future_runtime == {
              'platform': 'future-platform',
              'publish_supported': True,
              'analytics_supported': True,
              'metric_types': ['clicks', 'views'],
          }
'''
new = '''          future_runtime = get_platform_runtime_capabilities('future-platform')
          # Runtime capabilities intentionally grow as adapters/connectors are
          # added. Verify the stable Data Center contract without freezing the
          # entire response shape to an obsolete four-field snapshot.
          assert future_runtime['platform'] == 'future-platform'
          assert future_runtime['publish_supported'] is True
          assert future_runtime['analytics_supported'] is True
          assert future_runtime['metric_types'] == ['clicks', 'views']
          assert future_runtime['content_sync_registered'] is False
          assert future_runtime['analytics_sync_registered'] is False
          assert future_runtime['account_connector_registered'] is False
'''
if text.count(old) != 1:
    raise SystemExit(f'expected stale future_runtime assertion once, found {text.count(old)}')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
