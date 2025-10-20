import requests

def get_sbs_chill():
    r=requests.get("https://fos.sbs.com.au/web/audio/current-song/sbs-chill?delay=90").json()
    try: return r['songDisplayName']
    except: return "N/A"
   
