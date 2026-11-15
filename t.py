import base64, pyotp
import time
import requests
from datetime import datetime

SP_DC="AQB4TkmIeiqEVsjGv1-gShPYpQUF8m_H4A2RRf-eiiOnnQZiHVAsdHh1lHOLEPlZ3qT4jzVkt1eHomj71nJGvgDGZMGhgavhA6WAXXuIlb0KT59dFDpi_tTWcLPBgOMIplKVX-Th-r-NHOzgNwRCJrzqhh4lD18u1CqT_9TgB9thpQ2CoVDb-Dy2utSUKSJOmTHhbFyZoV5hT3hziA"
FRIEND_PREFIX = "friend:"
_web_token = {"value": None, "exp": 0}

TOTP_VER = 61
TOTP_SECRET_BYTES = [44, 55, 47, 42, 70, 40, 34, 114, 76, 74, 50, 111, 120, 97, 75, 76, 94, 102, 43, 69, 49, 120, 118, 80, 64, 78]
friend_uids = set()

FRIEND_STALE_WINDOW = 20 * 60
track_cache = {}
user_cache = {}

def _api_get(path, token):
    r = requests.get(f"https://api.spotify.com/v1/{path}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=8)
    r.raise_for_status()
    return r.json()

def get_track_meta(tid, token):
    if tid not in track_cache:
        j = _api_get(f"tracks/{tid}", token)
        imgs = j.get("album", {}).get("images", [])
        track_cache[tid] = {
            "title": j.get("name", "Unknown"),
            "artist": ", ".join(a.get("name", "") for a in j.get("artists", [])),
            "cover": imgs[0]["url"] if imgs else "",
        }
    return track_cache[tid]

def get_user_meta(raw_id, token):
    if raw_id not in user_cache:
        try:
            j = _api_get(f"users/{raw_id}", token)
            imgs = j.get("images", [])
            user_cache[raw_id] = {"name": j.get("display_name") or raw_id,
                                  "image": imgs[0]["url"] if imgs else ""}
        except Exception:
            user_cache[raw_id] = {"name": raw_id, "image": ""}
    return user_cache[raw_id]

def _make_totp(server_time):
    # transform used by the web player; verify it against your capture (see below)
    transformed = [b ^ ((i % 33) + 9) for i, b in enumerate(TOTP_SECRET_BYTES)]
    secret = base64.b32encode("".join(map(str, transformed)).encode()).decode().rstrip("=")
    return pyotp.TOTP(secret).at(server_time)

def get_web_token():
    now = time.time()
    if _web_token["value"] and now < _web_token["expirationDate"] - 60:
        return _web_token["value"]

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:156.0) Gecko/20100101 Firefox/156.0",
        "Accept": "*/*",
        "Referer": "https://open.spotify.com/",
        "Cookie": f"sp_dc={SP_DC}",
    }
    # server time (the browser uses this too; check the exact URL in your Network tab)
    st = requests.get("https://open.spotify.com/api/server-time", headers=headers, timeout=8).json()["serverTime"]
    code = _make_totp(st)

    r = requests.get(
        "https://open.spotify.com/api/token",
        params={"reason": "init", "productType": "web-player",
                "totp": code, "totpServer": code, "totpVer": TOTP_VER},
        headers=headers, timeout=8,
    )
    r.raise_for_status()
    j = r.json()
    print({k: v for k, v in j.items() if k != "accessToken"})
    _web_token["value"] = j["accessToken"]
    _web_token["exp"] = j["accessTokenExpirationTimestampMs"] / 1000.0
    return _web_token["value"]


def poll_friends():
    if not SP_DC:
        return
    now = time.time()
    try:
        token = get_web_token()

        r = requests.post(
            "https://spclient.wg.spotify.com/listening-activity/v1/feed",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json;charset=UTF-8",
                "app-platform": "WebPlayer",
                "Origin": "https://open.spotify.com",
                "Referer": "https://open.spotify.com/",
            },
            json={"unused": True, "resultLimit": 100},
            timeout=8,
        )

        print(r.text)

        if r.status_code == 401:
            _web_token["exp"] = 0
            return
        r.raise_for_status()
        entities = r.json().get("entities", [])

    except Exception as e:
        print(f"Friend feed error: {e}")
        return

    live_now = set()

    for ent in entities:
        try:
            fe = ent.get("followEntity")
            if not fe:
                continue
            act = fe.get("activity", {})
            if not act.get("isPlaying"):
                continue
            if not fe["uri"].startswith("spotify:user:"):
                continue
            if not act.get("entityUri", "").startswith("spotify:track:"):
                continue

            raw_id = fe["uri"].split(":")[-1]
            #if raw_id in spotify_users:
            #    continue  # already polled via their own authorization

            ts = datetime.fromisoformat(act["timestamp"].replace("Z", "+00:00")).timestamp()
            if now - ts > FRIEND_STALE_WINDOW:
                continue

            uid = FRIEND_PREFIX + raw_id
            tid = act["entityUri"].split(":")[-1]
            tm = get_track_meta(tid, token)
            um = get_user_meta(raw_id, token)

            set_user_activity(
                uid=uid, track=tid, user=um["name"], profile=um["image"],
                title=tm["title"], artist=tm["artist"], cover=tm["cover"], start=ts,
            )
            live_now.add(uid)

            if raw_id != EXCLUDED_NOTIFY_UID and not notified_flags.get(uid):
                notified_flags[uid] = True
                if now - last_notified_at.get(uid, 0) >= NOTIFY_COOLDOWN:
                    last_notified_at[uid] = now
                    notify_discord_listen_along(uid)
        except Exception as e:
            print(f"Friend parse error: {e}")


    # remove friends who are no longer live
    for uid in list(friend_uids - live_now):
        notified_flags.pop(uid, None)
        remove_user_activity(uid)
    friend_uids.clear()
    friend_uids.update(live_now)

poll_friends()
