from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from feiyu import mentions, presentation_content as content, processwait
from feiyu.tools import Toolbox


ROOT = Path(__file__).resolve().parents[1]
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
C = 'http://schemas.openxmlformats.org/drawingml/2006/chart'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CX = 'http://schemas.microsoft.com/office/drawing/2014/chartex'


def rels(*records):
    return (f'<Relationships xmlns="{REL}">' + ''.join(
        f'<Relationship Id="{rid}" Type="{kind if "://" in kind else R + "/" + kind}" Target="{target}" {mode}/>'
        for rid, kind, target, mode in records
    ) + '</Relationships>')


def slide(body):
    return f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree>{body}</p:spTree></p:cSld></p:sld>'


def shape(body, metadata=''):
    return f'<p:sp>{metadata}<p:txBody><a:p>{body}</a:p></p:txBody></p:sp>'


def run(text):
    return f'<a:r><a:t>{text}</a:t></a:r>'


def frame(body):
    return f'<p:graphicFrame><a:graphic><a:graphicData>{body}</a:graphicData></a:graphic></p:graphicFrame>'


def package_parts():
    title = shape(run('分段') + run('标题') + '<a:br/>' + run('下一行'))
    table = frame('''<a:tbl><a:tr><a:tc><a:txBody><a:p><a:r><a:t>类别</a:t></a:r></a:p>
        </a:txBody></a:tc><a:tc/><a:tc><a:txBody><a:p><a:r><a:t>数值</a:t></a:r></a:p>
        </a:txBody></a:tc></a:tr></a:tbl>''')
    picture = '''<p:pic><p:nvPicPr><p:cNvPr name="不应当作为替代文字" title="到访趋势"
        descr="柱形图突出第三周"/></p:nvPicPr><p:blipFill><a:blip r:embed="photo"/>
        </p:blipFill></p:pic>'''
    chart = frame(f'<c:chart xmlns:c="{C}" r:id="chart"/>')
    notes = slide(
        shape(run('演讲者内容'), '<p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr>')
        + shape(run('不应读到的备注页码'),
                '<p:nvSpPr><p:nvPr><p:ph type="sldNum"/></p:nvPr></p:nvSpPr>')
    ).replace('p:sld', 'p:notes')
    return {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        '_rels/.rels': rels(('doc', 'officeDocument', 'deck/main.xml', '')),
        'deck/main.xml': (
            f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'
            '<p:sldId id="256" r:id="ten"/><p:sldId id="257" r:id="two"/>'
            '<p:sldId id="258" r:id="one"/></p:sldIdLst></p:presentation>'
        ),
        'deck/_rels/main.xml.rels': rels(
            ('two', 'slide', 'slides/slide2.xml', ''),
            ('one', 'slide', '/deck/slides/slide1.xml', ''),
            ('ten', 'slide', 'slides/slide10.xml', ''),
        ),
        'deck/slides/slide1.xml': slide(shape(run('文稿末页'))),
        'deck/slides/slide2.xml': slide(shape(run('文稿第二页'))).replace('<p:sld ', '<p:sld show="0" '),
        'deck/slides/slide10.xml': slide(f'<p:grpSp>{title}{table}{picture}</p:grpSp>{chart}'),
        'deck/slides/slide99.xml': slide(shape(run('未被引用的孤立页'))),
        'deck/slides/_rels/slide10.xml.rels': rels(
            ('photo', 'image', '../media/%E5%88%B0%E8%AE%BF.png', ''),
            ('chart', 'chart', '../charts/one.xml', ''),
            ('notes', 'notesSlide', '../notes/ten.xml', ''),
        ),
        'deck/media/到访.png': b'images are not decoded',
        'deck/notes/ten.xml': notes,
        'deck/charts/one.xml': f'''<c:chartSpace xmlns:c="{C}" xmlns:a="{A}">
          <c:chart><c:title><c:tx><c:rich><a:p>{run('到访人次')}</a:p></c:rich></c:tx></c:title>
            <c:plotArea><c:barChart><c:ser><c:tx><c:v>到访</c:v></c:tx>
              <c:cat><c:strLit><c:pt idx="0"><c:v>首周</c:v></c:pt>
                <c:pt idx="1"><c:v>第三周</c:v></c:pt></c:strLit></c:cat>
              <c:val><c:numRef><c:numCache><c:pt idx="1"><c:v>48</c:v></c:pt>
                <c:pt idx="0"><c:v>26</c:v></c:pt></c:numCache></c:numRef></c:val>
            </c:ser></c:barChart></c:plotArea>
          </c:chart></c:chartSpace>''',
    }


def write_deck(path, parts):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload)
    return path


class PresentationContentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.deck = write_deck(self.root / '商务样例.PPTX', package_parts())

    def test_toolbox_read_file_uses_relationship_order_and_structured_content(self):
        deck = self.deck
        box = Toolbox(deck.parent)
        result = box.run('read_file', {'path': deck.name})
        assert not result.is_error, result
        assert result.source == 'builtin'
        text = result.content
        assert text.startswith('PPTX 共 3 页\n\n== 第 1 页 ==')
        assert text.index('分段标题\n下一行') < text.index('文稿第二页') < text.index('文稿末页')
        assert '== 第 2 页（隐藏） ==' in text
        assert '【表格】\n类别\t\t数值' in text
        assert '【图片替代文字】到访趋势 / 柱形图突出第三周' in text
        assert '【图表】\n标题：到访人次\n类型：barChart\n系列 1：到访' in text
        assert '类别：["首周", "第三周"]' in text
        assert '数值：[["1", "48"], ["0", "26"]]' in text
        assert '【演讲者备注】\n演讲者内容' in text
        assert '不应' not in text and '孤立页' not in text
        assert box.files.seen(deck)
        assert not box.files.stale(deck)
        with deck.open('ab') as stream:
            stream.write(b'changed')
        assert box.files.stale(deck)


    def test_tool_paginates_by_slide_and_mentions_reuse_extractor(self):
        deck = self.deck
        box = Toolbox(deck.parent)
        result = box.run('read_file', {'path': deck.name, 'offset': 2, 'limit': 1})
        assert '显示第 2–2 页' in result.content and '文稿第二页' in result.content
        assert '分段标题' not in result.content and '文稿末页' not in result.content
        text, summary = mentions._one(deck.name, deck, 10_000, box.files)
        assert '演讲者内容' in text and summary == 'pptx'


    def test_strict_ooxml_and_external_linked_image(self):
        tmp_path = self.root
        parts = package_parts()
        name = 'deck/slides/slide10.xml'
        parts[name] = parts[name].replace('r:embed="photo"', 'r:link="photo"')
        name = 'deck/slides/_rels/slide10.xml.rels'
        parts[name] = parts[name].replace(
            '../media/%E5%88%B0%E8%AE%BF.png"', 'https://invalid.example/never-fetch.png" TargetMode="External"')
        namespaces = {
            P: 'http://purl.oclc.org/ooxml/presentationml/main',
            A: 'http://purl.oclc.org/ooxml/drawingml/main',
            C: 'http://purl.oclc.org/ooxml/drawingml/chart',
            R: 'http://purl.oclc.org/ooxml/officeDocument/relationships',
        }
        for name, data in parts.items():
            if isinstance(data, str):
                for before, after in namespaces.items():
                    data = data.replace(before, after)
                parts[name] = data
        read = content.inspect_content(write_deck(tmp_path / 'strict.pptx', parts))
        assert '到访趋势 / 柱形图突出第三周' in read.text and '系列 1：到访' in read.text
        assert 'invalid.example' not in read.text


    def test_extended_chart_reads_one_compatibility_branch(self):
        tmp_path = self.root
        parts = package_parts()
        chart = frame(f'<cx:chart xmlns:cx="{CX}" r:id="chart"/>')
        fallback = shape(run('不应重复输出图表后备图形'))
        parts['deck/slides/slide2.xml'] = slide(f'''<mc:AlternateContent
            xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
            xmlns:cx="{CX}"><mc:Choice Requires="cx">{chart}</mc:Choice>
            <mc:Fallback>{fallback}</mc:Fallback></mc:AlternateContent>''')
        parts['deck/slides/_rels/slide2.xml.rels'] = rels(
            ('chart', 'http://schemas.microsoft.com/office/2014/relationships/chartEx', '../charts/extended.xml', ''),
        )
        parts['deck/charts/extended.xml'] = f'''<cx:chartSpace xmlns:cx="{CX}">
          <cx:chartData><cx:data id="0"><cx:numDim type="val"><cx:level ptCount="1">
            <cx:pt idx="0">48</cx:pt></cx:level></cx:numDim></cx:data></cx:chartData>
          <cx:chart><cx:plotArea><cx:plotAreaRegion><cx:series layoutId="waterfall">
            <cx:dataId val="0"/></cx:series></cx:plotAreaRegion></cx:plotArea></cx:chart></cx:chartSpace>'''
        result = content.inspect_content(write_deck(tmp_path / 'extended.pptx', parts))
        assert '系列：waterfall（数据 0）\n数据 0\nval：["48"]' in result.text
        assert '不应重复' not in result.text


    def test_structural_errors_even_outside_selected_pages(self):
        cases = [
            ('missing_slide', '缺少部件'),
            ('duplicate_slide', '重复'),
            ('missing_chart', '缺少部件'),
            ('missing_notes', '缺少部件'),
            ('missing_image', '缺少部件'),
            ('invalid_slide_xml', '无法解析'),
            ('wrong_type', '有效的 slide 关系'),
            ('external_slide', '必须位于包内'),
            ('traversal', '超出了包根目录'),
            ('doctype', 'DTD'),
        ]
        for damage, message in cases:
            with self.subTest(damage=damage):
                self._assert_structural_error(damage, message)


    def _assert_structural_error(self, damage, message):
        tmp_path = self.root
        parts = package_parts()
        main = 'deck/_rels/main.xml.rels'
        if damage in ('missing_slide', 'missing_chart', 'missing_notes', 'missing_image'):
            del parts[{
                'missing_slide': 'deck/slides/slide2.xml',
                'missing_chart': 'deck/charts/one.xml',
                'missing_notes': 'deck/notes/ten.xml',
                'missing_image': 'deck/media/到访.png',
            }[damage]]
        elif damage == 'duplicate_slide':
            parts['deck/main.xml'] = parts['deck/main.xml'].replace('id="257"', 'id="256"')
        elif damage == 'invalid_slide_xml':
            parts['deck/slides/slide2.xml'] = '<broken>'
        elif damage == 'wrong_type':
            parts[main] = parts[main].replace(f'{R}/slide', 'slide')
        elif damage == 'external_slide':
            parts[main] = parts[main].replace(
                'slides/slide2.xml"', 'https://invalid.example/slide.xml" TargetMode="External"')
        elif damage == 'traversal':
            parts[main] = parts[main].replace('slides/slide2.xml', '../../outside.xml')
        elif damage == 'doctype':
            slide_name = 'deck/slides/slide2.xml'
            parts[slide_name] = ('<!DOCTYPE p:sld>' + parts[slide_name]).encode('utf-16')
        deck = write_deck(tmp_path / 'damage.pptx', parts)
        result = Toolbox(tmp_path).run('read_file', {'path': deck.name, 'offset': 3, 'limit': 1})
        assert result.is_error and result.error_code == 'pptx_invalid'
        assert message in result.content


    def test_limits_compressed_xml_archive_size_and_unicode_output(self):
        tmp_path = self.root
        path = tmp_path / 'limits.pptx'
        box = Toolbox(tmp_path)
        parts = package_parts()
        parts['deck/slides/slide2.xml'] = slide(shape(run('A' * (2 * 1024**2))))
        write_deck(path, parts)
        assert path.stat().st_size < 10_000
        assert box.run('read_file', {'path': path.name}).error_code == 'pptx_limit'
        with path.open('wb') as file:
            file.truncate(64 * 1024**2 + 1)
        assert box.run('read_file', {'path': path.name}).error_code == 'pptx_limit'
        parts = package_parts()
        parts['deck/slides/slide10.xml'] = slide(shape(run('😀' * 32_000)))
        write_deck(path, parts)
        result = box.run('read_file', {'path': path.name})
        assert not result.is_error and result.truncated
        assert '内容已截断' in result.content and len(result.content) < 30_000

    def test_cli_signals_truncated_output_in_the_same_json_object(self):
        parts = package_parts()
        parts['deck/slides/slide10.xml'] = slide(shape(run('大' * 32_000)))
        write_deck(self.deck, parts)
        command = [sys.executable, '-m', 'feiyu', '--presentation-content', str(self.deck)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=15, check=True)
        self.assertEqual(result.stderr, b'')
        self.assertEqual(len(result.stdout.splitlines()), 1)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload), {'text', 'truncated'})
        self.assertIs(payload['truncated'], True)
        self.assertIn('内容已截断', payload['text'])


    def test_worker_isolation_and_cleanup_on_parallel_reads(self):
        deck = self.deck
        actual = processwait.run
        directories = []

        def observe(*args, cwd, **kwargs):
            directory = Path(cwd)
            assert directory.is_dir()
            assert directory != deck.parent
            directories.append(directory)
            return actual(*args, cwd=cwd, **kwargs)

        with patch.object(processwait, 'run', observe), ThreadPoolExecutor(max_workers=3) as pool:
            reads = list(pool.map(lambda offset: content.inspect_content(deck, offset=offset, limit=1),
                                  (1, 2, 3)))
        assert len(set(directories)) == 3 and not any(path.exists() for path in directories)
        assert '分段标题' in reads[0].text and '文稿第二页' in reads[1].text and '文稿末页' in reads[2].text


    def test_timeout_is_a_tool_error_and_worker_directory_is_removed(self):
        deck = self.deck
        stalled_worker = deck.parent / 'stalled_worker.py'
        started = deck.parent / 'worker-cwd.txt'
        stalled_worker.write_text(
            f'from pathlib import Path\nimport time\n'
            f'Path({str(started)!r}).write_text(str(Path.cwd()))\ntime.sleep(20)\n', encoding='utf-8')
        with patch.object(content, '__file__', str(stalled_worker)), patch.object(content, '_TIMEOUT', 1):
            result = Toolbox(deck.parent).run('read_file', {'path': deck.name})
        assert result.is_error and result.error_code == 'pptx_timeout' and '超时' in result.content
        assert not Path(started.read_text()).exists()


    def test_cli_writes_one_json_object_on_success_and_stderr_on_failure(self):
        deck = self.deck
        command = [sys.executable, '-m', 'feiyu', '--presentation-content', str(deck)]
        env = dict(os.environ, PYTHONIOENCODING='ascii')
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=15, check=True)
        assert not result.stderr and len(result.stdout.splitlines()) == 1
        assert json.loads(result.stdout) == {'text': content.inspect_content(deck).text}
        deck.write_bytes(b'not a zip file')
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=15)
        assert result.returncode == 1 and not result.stdout
        assert 'ZIP 包损坏' in result.stderr.decode('utf-8')
