import io
import zipfile
import urllib.request
import urllib.parse
import json

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("test_repo/main.py", "def hello(): print('hello')\n")
buf.seek(0)
zip_data = buf.read()

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="file"; filename="test_repo.zip"\r\n'
    f'Content-Type: application/zip\r\n\r\n'
).encode('utf-8') + zip_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')

req = urllib.request.Request(
    'http://127.0.0.1:5000/api/upload_repo',
    data=body,
    headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    },
    method='POST'
)

try:
    with urllib.request.urlopen(req) as resp:
        print("Upload test status:", resp.status)
        print("Upload test response:", resp.read().decode('utf-8'))
except Exception as e:
    print("Upload test failed:", e)
