import requests

def get_json(url):
    return requests.get(url).json()

def get_sbs_chill():
    r=get_json("https://fos.sbs.com.au/web/audio/current-song/sbs-chill?delay=90")
    print(r)
    return r['songDisplayName']
   
def get_box_chill():
    r=get_json("https://prod-api.radioapi.me/metadata/1ae42584-729c-4f36-9f8f-f0be92a95bff")
    return f"{r['song']} by {r['artist']}"
    
