from pathlib import Path
import sys
sys.path.insert(0,'os/backend')
text=Path('.github/workflows/recover-polish-artifact.yml').read_text()
assert 'workflow_dispatch:' in text
for key in ('source_run_id','artifact_name','content_id','hook','recovery_artifact_name'): assert key in text
assert 'HOOK_TEXT: ${{ inputs.hook }}' in text
for forbidden in ('cli.py','render_batch.py','PEXELS_API_KEY','--batch-file'): assert forbidden not in text
assert 'final-output.mp4' in text and 'actions/download-artifact@v4' in text
from production.providers.github_recovery import recover_failed_github_result
assert 'short13.mp4' not in Path('os/backend/production/providers/github_recovery.py').read_text()
print('Recovery workflow smoke passed')
