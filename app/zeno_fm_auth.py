import requests
from urllib.parse import unquote
import re
import os
import json
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(base_dir), '.env'))
creds = json.load(open(base_dir+'/creds.json'))

zeno_username=os.getenv("zeno_username")
zeno_password=os.getenv("zeno_password")

REALM_BASE = "https://tools.zeno.fm/auth/realms/broadcasters"
AUTH_URL = f"{REALM_BASE}/protocol/openid-connect/auth"
TOKEN_URL = f"{REALM_BASE}/protocol/openid-connect/token"
REDIRECT_URI = "https://tools.zeno.fm/"
CLIENT_ID = "zeno-tools"

def zeno_fm_login(username: str, password: str) -> dict | None:
    # -- Step 1: Get login page + session cookies --
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_mode": "fragment",
        "response_type": "code",
        "scope": "openid",
    }

    resp = session.get(AUTH_URL, params=auth_params, allow_redirects=True)
    if resp.status_code != 200:
        return None

    login_action_url = re.findall('https://tools.zeno.fm/auth/realms/broadcasters/login-actions/authenticate\\?[^"\']+',resp.text)[0]

    # -- Step 2: Submit credentials --
    login_data = {
        "username": username,
        "password": password,
        "credentialId": "",
        "login": "Sign In",
    }

    resp = session.post(login_action_url, data=login_data, allow_redirects=False)

    # -- Step 3: Extract authorization code from redirect fragment --
    redirect_url = resp.headers.get("Location", "")
    if "#" not in redirect_url or "code=" not in redirect_url:
        return None

    fragment = redirect_url.split("#", 1)[1]
    fragment_params = {
        k: unquote(v)
        for k, v in (param.split("=", 1) for param in fragment.split("&") if "=" in param)
    }
    auth_code = fragment_params.get("code")
    if not auth_code:
        return None

    # -- Step 4: Exchange code for tokens --
    token_data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
    }

    resp = session.post(TOKEN_URL, data=token_data)
    if resp.status_code != 200:
        return None

    return resp.json()


def get_zeno_token():
    global creds
    token = creds['access_token']
    test_token = requests.get("https://stream-tools.zenomedia.com/users/me",headers={"Authorization": "Bearer "+token})
    # test_tokenn = requests.get("https://stream-tools.zenomedia.com/auth/profile",headers={"Authorization": "Bearer "+token})

    if "id" in test_token.json():
        print("Old access token works")
        return token

    rr = requests.post(TOKEN_URL,data={"grant_type":"refresh_token","refresh_token":creds['refresh_token'],"client_id":CLIENT_ID})
    print(rr.text)
    if not 'access_token' in rr.json():
        login_resp=zeno_fm_login(zeno_username,zeno_password)
        if not login_resp:
            print("Couldn't login")
            return None
        else:
            print("Logged in successfully")
            creds=login_resp
    else:
        print("Refreshed token successfully!")
        creds=rr.json()
    with open(base_dir+'/creds.json','w') as f:
        json.dump(creds,f)

    return creds['access_token']
