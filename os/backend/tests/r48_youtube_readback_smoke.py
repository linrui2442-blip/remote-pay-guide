"""Isolated contract for official YouTube videos.list read-back."""
import os, sys, tempfile
from pathlib import Path
os.environ["OS_TESTING"]="1"; os.environ.setdefault("OS_DATABASE_PATH",str(Path(tempfile.gettempdir()) / "r48-youtube-readback.db"))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from publish.adapters.youtube_api import YouTubeAPIClient
class Response:
    def raise_for_status(self): pass
    def json(self): return {"items":[{"id":"k_zYBNPifSs","snippet":{"title":"Which USDT Network Should Your Client Use? | USDT Payment Safety","channelId":"UC-test"},"status":{"privacyStatus":"public"},"processingDetails":{"processingStatus":"succeeded"}}]}
class Session:
    def get(self,url,params=None,timeout=None):
        assert url.endswith('/youtube/v3/videos'); assert params=={"part":"snippet,status,processingDetails","id":"k_zYBNPifSs"}; return Response()
c=YouTubeAPIClient(); c.session=Session(); r=c.get_video_status('k_zYBNPifSs')
assert r['video_id']=='k_zYBNPifSs' and r['privacy_status']=='public' and r['processing_status']=='succeeded' and r['title'].startswith('Which USDT')
print('YouTube official readback contract passed')
