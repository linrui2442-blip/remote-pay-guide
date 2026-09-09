import os, sys, tempfile
from pathlib import Path
os.environ["OS_TESTING"]="1"
os.environ["OS_DATABASE_PATH"]=str(Path(tempfile.mkdtemp(prefix="remote-pay-meta-test-"))/"os.db")
BACKEND=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BACKEND))
from oauth.meta_runtime_config import meta_config_status
from oauth.providers.meta import MetaOAuthProvider, MetaOAuthConfigurationError
from oauth.meta_bindings import save_binding, get_binding
from oauth.registry import list_account_connectors
from oauth.manager import create_oauth_state, consume_oauth_state_by_state

def main():
    for key in ("META_OAUTH_APP_ID","META_OAUTH_APP_SECRET","META_OAUTH_REDIRECT_URI","META_GRAPH_API_VERSION"): os.environ.pop(key, None)
    assert meta_config_status()["configured"] is False
    assert {item["platform"] for item in list_account_connectors()} >= {"youtube","facebook","instagram"}
    fb=MetaOAuthProvider("facebook", app_id="app", app_secret="secret", redirect_uri="http://localhost/callback", graph_api_version="v-test")
    ig=MetaOAuthProvider("instagram", app_id="app", app_secret="secret", redirect_uri="http://localhost/callback", graph_api_version="v-test")
    assert set(fb.scopes)=={"pages_show_list","pages_read_engagement","pages_manage_posts"}; assert "instagram_content_publish" in ig.scopes
    from unittest.mock import patch
    with patch("oauth.providers.meta.create_oauth_state") as state:
        auth=fb.authorization_url(1); assert auth["state"] and auth["state"] != fb.authorization_url(1)["state"] and state.call_count==2
    try: MetaOAuthProvider("facebook").authorization_url(1)
    except MetaOAuthConfigurationError: pass
    else: raise AssertionError("missing config must fail closed")
    with patch.object(fb,"_get",return_value={"data":[{"id":"p1","name":"Page One","tasks":["CREATE_CONTENT"],"instagram_business_account":{"id":"ig1"}},{"id":"p2","name":"Page Two","tasks":[]}]}) as get:
        resources=fb.discover_resources("TOKEN"); assert len(resources)==2 and "TOKEN" not in str(resources); get.assert_called_once()
    with patch.object(ig,"_get",return_value={"data":[{"id":"p1","name":"Page One","instagram_business_account":{"id":"ig1"}},{"id":"p2","name":"Page Two"}]}) as get:
        resources=ig.discover_resources("TOKEN"); assert len(resources)==1 and resources[0]["instagram_user_id"]=="ig1"
    binding=save_binding(1,"instagram","p1","ig1",external_display_name="Page One"); assert get_binding(1)["page_id"]=="p1" and "token" not in str(binding).lower()
    create_oauth_state(1, "facebook-state", provider="meta", connector_platform="facebook", scope_profile="meta_full")
    assert consume_oauth_state_by_state("facebook-state", provider="meta", expected_connector_platform="instagram", expected_scope_profile=["instagram_publish", "meta_full"]) is None
    assert consume_oauth_state_by_state("facebook-state", provider="meta", expected_connector_platform="facebook", expected_scope_profile=["facebook_publish", "meta_full"])
    assert consume_oauth_state_by_state("facebook-state", provider="meta", expected_connector_platform="facebook") is None
    print("Meta OAuth foundation smoke test passed")
if __name__ == "__main__": main()
