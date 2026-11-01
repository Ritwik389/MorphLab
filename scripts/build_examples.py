"""Build deterministic test fixtures from attributed bundled portraits."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

root = Path(__file__).resolve().parents[1] / 'assets/examples'
portrait = Image.open(root / 'source.png').convert('RGB')
portrait.rotate(12, resample=Image.Resampling.BICUBIC, fillcolor='#dce5df').save(root / 'rotated.jpg', quality=92)
portrait.filter(ImageFilter.GaussianBlur(5)).save(root / 'blurred.jpg', quality=92)
multiple = Image.new('RGB', (1024, 512), '#eaf0ec')
multiple.paste(portrait.resize((512, 512)), (0, 0))
second = Image.open(root / 'sally.jpg').convert('RGB')
second.thumbnail((450, 512))
multiple.paste(second, (512 + (512-second.width)//2, 0))
multiple.save(root / 'multiple-faces.jpg', quality=92)
text = Image.new('RGB', (640, 480), '#eaf0ec')
draw = ImageDraw.Draw(text)
draw.multiline_text((55, 165), 'No faces here.\nMorphLab validation sample', fill='#192b25', font=ImageFont.load_default(size=34), spacing=20)
text.save(root / 'text-only.png')
scene = Image.new('RGB', (640, 480), '#d9e8ed')
draw = ImageDraw.Draw(scene)
draw.polygon([(0, 400), (200, 140), (400, 400)], fill='#739386')
draw.polygon([(240, 400), (490, 190), (640, 400)], fill='#4e7562')
draw.rectangle((0, 390, 640, 480), fill='#b4cdb6')
scene.save(root / 'no-face.png')
manifest = {'pairs': [
    {'id': 'collins-hopper', 'name': 'Eileen → Grace', 'source': '/examples/source.png', 'target': '/examples/target.jpg', 'description': 'Original sample pair'},
    {'id': 'ride-johnson', 'name': 'Sally → Katherine', 'source': '/examples/sally.jpg', 'target': '/examples/katherine.jpg', 'description': 'Color source and monochrome target'},
    {'id': 'johnson-ride', 'name': 'Katherine → Sally', 'source': '/examples/katherine.jpg', 'target': '/examples/sally.jpg', 'description': 'Monochrome source and color target'}],
    'fixtures': [
        {'name': 'Text only', 'url': '/examples/text-only.png', 'expected': 'No face; show a helpful message.'},
        {'name': 'Scene without faces', 'url': '/examples/no-face.png', 'expected': 'No face; show a helpful message.'},
        {'name': 'Rotated portrait', 'url': '/examples/rotated.jpg', 'expected': 'Detect and align the tilted face.'},
        {'name': 'Blurred portrait', 'url': '/examples/blurred.jpg', 'expected': 'Reduced detail; inspect output quality.'},
        {'name': 'Two faces', 'url': '/examples/multiple-faces.jpg', 'expected': 'Reject ambiguous source; target supports all-face editing.'}],
    'credits': [
        {'name':'Eileen Collins','creator':'NASA, via scikit-image astronaut sample','license':'Public domain','url':'https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.astronaut'},
        {'name':'Grace Hopper','creator':'US Navy','license':'Public domain','url':'https://matplotlib.org/stable/gallery/cbook/image_demo.html'},
        {'name':'Sally Ride, 1979','creator':'NASA / Glenn Research Center','license':'Public domain','url':'https://commons.wikimedia.org/wiki/File:Sally_Ride_1979.jpg'},
        {'name':'Katherine Johnson, 1966 (original)','creator':'NASA','license':'Public domain','url':'https://commons.wikimedia.org/wiki/File:Katherine_Johnson_at_NASA,_in_1966_-_Original.jpg'}]}
(root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print('Built three portrait pairs and five validation fixtures.')
