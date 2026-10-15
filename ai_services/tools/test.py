import urllib.request
import json
import base64
import glob

imgs = glob.glob('employees/*/*.jpg')
if not imgs:
    print("No images found in employees folder!")
else:
    img = imgs[0]
    print('Using image:', img)
    with open(img, "rb") as f:
        img_data = f.read()
    b64 = base64.b64encode(img_data).decode("utf-8")

    req = urllib.request.Request(
        'http://127.0.0.1:5000/recognize',
        data=json.dumps({'image': f'data:image/jpeg;base64,{b64}'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        res = urllib.request.urlopen(req)
        print("Success:", res.read())
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code)
        print(e.read())
    except Exception as e:
        print("General Error:", str(e))
