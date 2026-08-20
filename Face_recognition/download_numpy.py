import urllib.request
import time

url = 'https://files.pythonhosted.org/packages/60/a2/33ebfcce60443fbce140e69af00eeb04cd3dc3a037bce477e3ffb0c79f32/numpy-1.26.4-cp310-cp310-win_amd64.whl'
file_name = 'numpy-1.26.4-cp310-cp310-win_amd64.whl'

for i in range(5):
    try:
        print(f'Attempt {i+1} to download numpy...')
        urllib.request.urlretrieve(url, file_name)
        print('Download successful!')
        break
    except Exception as e:
        print(f'Failed: {e}')
        time.sleep(2)
