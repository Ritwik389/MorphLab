"""Fetch the MobileFaceSwap authors' public checkpoint archive using verified HTTPS."""
import hashlib
import html.parser
import json
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
directory = ROOT / 'models/mobilefaceswap'
directory.mkdir(parents=True, exist_ok=True)
archive = directory / 'checkpoints.tar'
EXPECTED = '8e45272de4cc55d64294d282bb7605343a406696a05209203065aa1b51aed58e'
url = 'https://drive.google.com/uc?export=download&id=1ZIzGLDB15GRAZAbkfNR0hNWdgQpxeA_r'


class Form(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}
    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'form':
            self.action = data.get('action')
        if tag == 'input' and data.get('name'):
            self.fields[data['name']] = data.get('value', '')


if not archive.exists():
    with urllib.request.urlopen(url, timeout=40) as response:
        page = response.read(16000).decode()
    form = Form()
    form.feed(page)
    if form.action != 'https://drive.usercontent.google.com/download':
        raise RuntimeError('The authors’ download is unavailable or changed. No HTML will be saved as weights.')
    url = form.action + '?' + urllib.parse.urlencode(form.fields)
    temporary = archive.with_suffix('.partial')
    try:
        with urllib.request.urlopen(url, timeout=90) as response, temporary.open('wb') as output:
            if 'html' in response.headers.get('Content-Type', ''):
                raise RuntimeError('Download returned a confirmation page instead of model weights.')
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > 800 * 1024 * 1024:
                    raise RuntimeError('Unexpected checkpoint archive size.')
                output.write(chunk)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
with archive.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
if digest != EXPECTED:
    raise RuntimeError('MobileFaceSwap archive checksum mismatch; refusing to extract.')
with tarfile.open(archive) as tar:
    for member in tar.getmembers():
        if member.isfile() and Path(member.name).name in {'arcface.pdparams', 'MobileFaceSwap_224.pdparams'}:
            destination = directory / Path(member.name).name
            with tar.extractfile(member) as input_file, destination.open('wb') as output:
                import shutil
                shutil.copyfileobj(input_file, output)
            print(destination.name, destination.stat().st_size, flush=True)
(directory / 'provenance.json').write_text(json.dumps({'source':'https://github.com/Seanseattle/MobileFaceSwap/tree/master',
    'authors_download_id':'1ZIzGLDB15GRAZAbkfNR0hNWdgQpxeA_r', 'archive_sha256':digest}, indent=2))
print('Archive SHA256:', digest)
