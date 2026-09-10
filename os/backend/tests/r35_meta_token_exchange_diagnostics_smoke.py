import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch
os.environ["OS_TESTING"]="1"; os.environ["OS_DATABASE_PATH"]=str(Path(tempfile.mkdtemp())/"os.db")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from oauth.providers.meta import MetaOAuthProvider, MetaOAuthRequestError

class Response:
    def __init__(self, status=200, payload=None): self.status_code=status; self.payload=payload or {}; self.ok=status < 400
    def json(self): return self.payload

def main():
    provider=MetaOAuthProvider("facebook",app_id="app",app_secret="SECRET_APP",redirect_uri="http://localhost/callback",graph_api_version="v-test",facebook_login_config_id="config")
    calls=[]
    def fake_get(url,params=None,**kwargs):
        calls.append((url,params,kwargs))
        return Response(payload={"access_token":"LONG_TOKEN","expires_in":5184000})
    with patch("oauth.providers.meta.requests.get",side_effect=fake_get):
        provider._token_exchange({"code":"SECRET_CODE"}); provider._token_exchange({"fb_exchange_token":"SECRET_SHORT"})
    assert len(calls)==2 and all(call[1] is not None for call in calls)
    error_payload={"error":{"type":"OAuthException","code":100,"error_subcode":123,"message":"Invalid OAuth request","fbtrace_id":"trace-safe"}}
    with patch("oauth.providers.meta.requests.get",return_value=Response(400,error_payload)):
        try: provider._token_exchange({"code":"SECRET_CODE","client_secret":"SECRET_APP"})
        except MetaOAuthRequestError as exc:
            text=str(exc); assert all(item in text for item in ("HTTP 400","OAuthException","code=100","subcode=123","trace-safe")); assert "SECRET_CODE" not in text and "SECRET_APP" not in text
        else: raise AssertionError("expected safe Meta error")
    print("Meta token exchange diagnostics smoke test passed")
if __name__=="__main__": main()
