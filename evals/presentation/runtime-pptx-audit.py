"""Cross-check both delivered business decks against the editable Studio source."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import zipfile
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

root = Path(__file__).resolve().parents[2] / 'docs/presentation/runtime-pptx'
source = json.loads((root / 'after/source.deck.json').read_text(encoding='utf-8'))
slides = source['slides']
ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
      's': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def digest(file):
    return sha256(file.read_bytes()).hexdigest()


def strings(node, query):
    return [element.text for element in node.findall(query, ns)]


with zipfile.ZipFile(root / 'before/deck.pptx') as before, zipfile.ZipFile(root / 'after/deck.pptx') as after:
    results = {}
    for side, archive in [('before', before), ('after', after)]:
        review = root / side / 'review'
        report = json.loads((review / 'report.json').read_text(encoding='utf-8'))
        assert report['pptxSha256'] == digest(root / side / 'deck.pptx')
        assert report['pdfSha256'] == digest(review / 'deck.pdf')
        assert len(report['pages']) == len(slides) == 3
        for i, (page, slide) in enumerate(zip(report['pages'], slides), 1):
            assert digest(review / page['png']) == page['sha256'] and slide['id'] == page['slideId']
            xml = ET.fromstring(archive.read(f'ppt/slides/slide{i}.xml'))
            editable = strings(xml, './/a:t')
            assert slide['title'] in editable
            for item in slide['items']:
                if slide['layout'] != 'chart' and item['label']:
                    assert item['label'] in editable
                if item['text']:
                    assert item['text'] in editable
            notes = ET.fromstring(archive.read(f'ppt/notesSlides/notesSlide{i}.xml'))
            assert slide['notes'] in strings(notes, './/a:t')
        chart_slide, = [s for s in slides if s['layout'] == 'chart']
        pairs = [(r['label'], str(r['value'])) for r in chart_slide['items']]
        chart, = [n for n in archive.namelist() if n.startswith('ppt/charts/chart') and n.endswith('.xml')]
        plot = ET.fromstring(archive.read(chart))
        assert list(zip(strings(plot, './/c:cat//c:pt/c:v'), strings(plot, './/c:val//c:pt/c:v'))) == pairs
        sheet, = [n for n in archive.namelist() if n.endswith('.xlsx')]
        with zipfile.ZipFile(BytesIO(archive.read(sheet))) as workbook:
            shared = strings(ET.fromstring(workbook.read('xl/sharedStrings.xml')), './/s:si/s:t')
            rows = ET.fromstring(workbook.read('xl/worksheets/sheet1.xml')).findall('.//s:row', ns)[1:]
            cells = [strings(row, 's:c/s:v') for row in rows]
            assert [(shared[int(label)], value) for label, value in cells] == pairs
        results[side] = {'pptxSha256': report['pptxSha256'], 'status': report['status'], 'chartData': pairs}
    pages = []
    for i in range(1, len(slides) + 1):
        part = f'ppt/slides/slide{i}.xml'
        xml = [archive.read(part) for archive in (before, after)]
        assert Counter(strings(ET.fromstring(xml[0]), './/a:t')) == Counter(strings(ET.fromstring(xml[1]), './/a:t'))
        images = [Image.open(root / side / f'review/slide-{i}.png').convert('RGB') for side in results]
        pages.append({'page': i, 'identicalSlideXml': xml[0] == xml[1],
                      'changedPixelBounds': ImageChops.difference(*images).getbbox()})
    print(json.dumps({'files': results, 'pages': pages}, ensure_ascii=False, indent=2))
