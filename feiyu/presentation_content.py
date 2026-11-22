"""Read PPTX content and check the package relationships that supply it."""

import hashlib
import io
import json
import os
import posixpath
import stat
import subprocess
import sys
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

_MIB = 1024**2
_MAX_ARCHIVE = 64 * _MIB
_MAX_ZIP_READ = 4 * _MIB  # Also limits zipfile's initial central directory allocation.
_MAX_ENTRIES = 10_000
_MAX_PART = 2 * _MIB
_MAX_XML = 24 * _MIB
_MAX_NODES_PER_PART = 60_000
_MAX_DEPTH = 64
_MAX_SLIDES = 300
_MAX_TEXT = 28_000
_MAX_REPLY = 12 * _MAX_TEXT + 1024  # A non-BMP character can use two JSON escapes.
_TIMEOUT = 10

_P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
_A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
_C = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
_R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
_CX = '{http://schemas.microsoft.com/office/drawing/2014/chartex}'
_MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
_CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
_STRICT = {
    '{http://purl.oclc.org/ooxml/presentationml/main}': _P,
    '{http://purl.oclc.org/ooxml/drawingml/main}': _A,
    '{http://purl.oclc.org/ooxml/drawingml/chart}': _C,
    '{http://purl.oclc.org/ooxml/officeDocument/relationships}': _R,
}
_REL_TYPES = (_R[1:-1] + '/', 'http://purl.oclc.org/ooxml/officeDocument/relationships/')
_CHART_EX_REL = 'http://schemas.microsoft.com/office/2014/relationships/chartEx'
_TRUNCATED = '（PPTX 文本达到输出上限，内容已截断）'


class PresentationError(ValueError):
    def __init__(self, message, code='pptx_invalid'):
        super().__init__(message)
        self.code = code


def _limit(message):
    return PresentationError(message, 'pptx_limit')


class _ZipInput(io.BufferedReader):
    def read(self, size=-1):
        if size > _MAX_ZIP_READ:
            raise _limit('PPTX ZIP 目录或单次读取超过 4 MiB')
        data = super().read(size if size >= 0 else _MAX_ZIP_READ + 1)
        if len(data) > _MAX_ZIP_READ:
            raise _limit('PPTX ZIP 目录或单次读取超过 4 MiB')
        return data


def _tag(name):
    namespace, sep, local = name.rpartition('}')
    return _STRICT.get(namespace + sep, namespace + sep) + local


class _XmlTree(ET.TreeBuilder):
    def __init__(self):
        super().__init__()
        self.nodes = self.depth = 0

    def start(self, tag, attrs):
        self.nodes += 1
        self.depth += 1
        if self.nodes > _MAX_NODES_PER_PART or self.depth > _MAX_DEPTH:
            raise _limit('PPTX XML 元素数量或嵌套深度超过上限')
        return super().start(_tag(tag), {_tag(key): value for key, value in attrs.items()})

    def end(self, tag):
        self.depth -= 1
        return super().end(_tag(tag))

    def doctype(self, name, pubid, system):
        raise PresentationError('PPTX XML 含有不允许的 DTD 声明')


@dataclass(frozen=True)
class _Relationship:
    kind: str
    target: str
    external: bool


def _part_path(source, target):
    if any(ord(char) < 32 for char in target):
        raise PresentationError('PPTX 包内关系含有无效的路径字符')
    uri = urlsplit(target)
    if uri.scheme or uri.netloc or uri.query or uri.fragment or target.startswith('//'):
        raise PresentationError('PPTX 包内关系的目标不是有效的部件路径')
    pieces = source.split('/')[:-1] if not uri.path.startswith('/') else []
    if not uri.path or uri.path.endswith('/'):
        raise PresentationError('PPTX 包内关系缺少部件文件名')
    for piece in uri.path.removeprefix('/').split('/'):
        decoded = unquote(piece, errors='strict')
        if not decoded or any(char in decoded for char in '/\\') or any(ord(char) < 32 for char in decoded):
            raise PresentationError('PPTX 包内关系含有无效的路径片段')
        if decoded == '..':
            if not pieces:
                raise PresentationError('PPTX 部件关系超出了包根目录')
            pieces.pop()
        elif decoded != '.':
            pieces.append(piece)
    return '/'.join(pieces)


class _Package:
    def __init__(self, archive):
        self.archive = archive
        entries = archive.infolist()
        if len(entries) > _MAX_ENTRIES:
            raise _limit('PPTX ZIP 条目超过 10000 个')
        self.parts = {}
        for entry in entries:
            if entry.is_dir():
                continue
            key = entry.filename.lower()
            if key in self.parts:
                raise PresentationError(f'PPTX 有重复的 ZIP 部件 {entry.filename[:160]}')
            self.parts[key] = entry
        self.xml_left = _MAX_XML

    def xml(self, part, expected_root):
        entry = self.parts.get(part.lower())
        if entry is None:
            raise PresentationError(f'PPTX 缺少部件 {part[:160]}')
        if entry.file_size > _MAX_PART or entry.file_size > self.xml_left:
            raise _limit(f'PPTX XML 超过单部件 2 MiB 或累计 24 MiB 上限（{part[:160]}）')
        if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) or entry.flag_bits & 1:
            raise PresentationError(f'PPTX XML 部件已加密或压缩格式不受支持（{part[:160]}）')
        with self.archive.open(entry) as stream:
            raw = stream.read(min(_MAX_PART, self.xml_left) + 1)
        if len(raw) > min(_MAX_PART, self.xml_left):
            raise _limit('PPTX 解压后的 XML 超过上限')
        self.xml_left -= len(raw)
        try:
            root = ET.fromstring(raw, parser=ET.XMLParser(target=_XmlTree()))
        except (ET.ParseError, LookupError) as exc:
            raise PresentationError(f'PPTX XML 无法解析（{part[:160]}）') from exc
        if root.tag != expected_root:
            raise PresentationError(f'PPTX 部件的 XML 根元素类型不匹配（{part[:160]}）')
        return root

    def relationships(self, source='', *, required=False):
        folder, name = posixpath.split(source)
        part = posixpath.join(folder, '_rels', name + '.rels')
        if not required and part.lower() not in self.parts:
            return {}
        records = {}
        for rel in self.xml(part, _REL + 'Relationships').iterfind(_REL + 'Relationship'):
            rid, kind, target = (rel.get(key) for key in ('Id', 'Type', 'Target'))
            mode = rel.get('TargetMode', 'Internal')
            if not rid or not kind or not target or rid in records or mode not in ('Internal', 'External'):
                raise PresentationError(f'PPTX 部件关系缺失或重复（{part[:160]}）')
            for prefix in _REL_TYPES:
                if kind.startswith(prefix):
                    kind = kind[len(prefix):]
                    break
            else:
                if kind != _CHART_EX_REL:
                    kind = ''
            records[rid] = _Relationship(kind, target, mode == 'External')
        return records

    def target(self, source, rel, kind, *, allow_external=False):
        if rel is None or rel.kind != kind:
            raise PresentationError(f'PPTX 缺少有效的 {kind.rsplit("/", 1)[-1]} 关系（{source[:160] or "包根目录"}）')
        if rel.external:
            if allow_external:
                return None
            raise PresentationError(f'PPTX 的 {kind.rsplit("/", 1)[-1]} 部件必须位于包内')
        part = _part_path(source, rel.target)
        decoded = unquote(part, errors='strict')
        candidates = {name.lower() for name in (part, decoded) if name.lower() in self.parts}
        if len(candidates) != 1:
            issue = '有歧义的' if candidates else '缺少'
            raise PresentationError(f'PPTX {issue}部件 {part[:160]}')
        return self.parts[candidates.pop()].filename


def _shapes(parent):
    """Follow the shape tree, including nested groups and one compatibility branch."""
    for node in parent:
        if node.tag == _P + 'grpSp':
            yield from _shapes(node)
        elif node.tag == _MC + 'AlternateContent':
            fallback = node.find(_MC + 'Fallback')
            for choice in node.iterfind(_MC + 'Choice'):
                if any(shape.tag in (_P + 'sp', _P + 'pic', _P + 'graphicFrame', _P + 'grpSp',
                                     _P + 'cxnSp') for shape in choice):
                    yield from _shapes(choice)
                    break
            else:
                if fallback is not None:
                    yield from _shapes(fallback)
        else:
            yield node


def _paragraphs(parent):
    for paragraph in parent.iterfind(_A + 'p'):
        line = ''.join(
            '\n' if run.tag == _A + 'br' else run.findtext(_A + 't', '')
            for run in paragraph
        ).strip()
        if line:
            yield line


def _tree(root, part):
    tree = root.find(f'{_P}cSld/{_P}spTree')
    if tree is None:
        raise PresentationError(f'PPTX 部件缺少幻灯片形状树（{part[:160]}）')
    return tree


def _table(table):
    yield '【表格】'
    for row in table.iterfind(_A + 'tr'):
        cells = []
        for cell in row.iterfind(_A + 'tc'):
            body = cell.find(_A + 'txBody')
            text = '\n'.join(_paragraphs(body)) if body is not None else ''
            cells.append(text.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t'))
        yield '\t'.join(cells)


def _chart_title(tx):
    if tx is None:
        return ''
    return (' '.join(line for body in tx.iter(_C + 'rich') for line in _paragraphs(body))
            or tx.findtext(_C + 'v', '') or tx.findtext(f'.//{_C}pt/{_C}v', ''))


def _chart_points(points, value):
    # Keep explicit indices when the cache is sparse or out of order.
    pairs = [(point.get('idx', str(i)), value(point)) for i, point in enumerate(points)]
    values = [text for _, text in pairs] if all(index == str(i) for i, (index, _) in enumerate(pairs)) else pairs
    return json.dumps(values, ensure_ascii=False)


def _classic_chart(root, part):
    chart = root.find(_C + 'chart')
    plots = None if chart is None else chart.find(_C + 'plotArea')
    if plots is None:
        raise PresentationError(f'PPTX 图表缺少绘图区（{part[:160]}）')
    title = _chart_title(chart.find(f'{_C}title/{_C}tx'))
    if title:
        yield f'标题：{title}'
    for plot in plots:
        name = plot.tag.removeprefix(_C)
        if not plot.tag.startswith(_C) or not name.endswith(('Chart', 'Chart3D')):
            continue
        yield f'类型：{name}'
        for i, series in enumerate(plot.iterfind(_C + 'ser'), 1):
            label = _chart_title(series.find(_C + 'tx'))
            yield f'系列 {i}' + (f'：{label}' if label else '')
            for key, caption in (('cat', '类别'), ('val', '数值'), ('xVal', 'X 值'),
                                 ('yVal', 'Y 值'), ('bubbleSize', '气泡大小')):
                data = series.find(_C + key)
                if data is None:
                    continue
                levels = data.findall(f'.//{_C}lvl')
                for level, group in enumerate(levels or [data], 1):
                    points = list(group.iter(_C + 'pt'))
                    if points:
                        label = f'{caption}（层 {level}）' if len(levels) > 1 else caption
                        yield f'{label}：{_chart_points(points, lambda point: point.findtext(_C + "v", ""))}'
                    else:
                        yield f'{caption}：（无缓存数据）'


def _extended_chart(root, part):
    chart = root.find(_CX + 'chart')
    if chart is None or chart.find(_CX + 'plotArea') is None:
        raise PresentationError(f'PPTX 扩展图表缺少绘图区（{part[:160]}）')
    title = chart.find(_CX + 'title')
    if title is not None:
        for text in title.iter(_A + 't'):
            if text.text:
                yield f'标题：{text.text}'
    for series in chart.iter(_CX + 'series'):
        data_id = series.find(_CX + 'dataId')
        label = series.findtext(f'{_CX}tx/{_CX}txData/{_CX}v', '')
        layout = series.get('layoutId', '')
        suffix = f'（数据 {data_id.get("val", "")}）' if data_id is not None else ''
        yield f'系列：{label or layout}{suffix}'
    for data in root.iterfind(f'{_CX}chartData/{_CX}data'):
        yield f'数据 {data.get("id", "")}'
        for dimension in data:
            if dimension.tag not in (_CX + 'strDim', _CX + 'numDim'):
                continue
            for level in dimension.iterfind(_CX + 'level'):
                values = _chart_points(level.iterfind(_CX + 'pt'), lambda point: point.text or '')
                yield f'{dimension.get("type", "")}：{values}'


def _slide(package, part, slide):
    tree = _tree(slide, part)
    rels = package.relationships(part)
    for shape in _shapes(tree):
        body = shape.find(_P + 'txBody')
        if body is not None:
            yield from _paragraphs(body)
        if shape.tag == _P + 'pic':
            metadata = shape.find(f'{_P}nvPicPr/{_P}cNvPr')
            descriptions = [] if metadata is None else [
                value for key in ('title', 'descr') if (value := metadata.get(key, '').strip())
            ]
            blip = shape.find(f'{_P}blipFill/{_A}blip')
            if blip is not None:
                for attr in ('embed', 'link'):
                    rid = blip.get(_R + attr)
                    if rid:
                        package.target(part, rels.get(rid), 'image', allow_external=attr == 'link')
            yield '【图片替代文字】' + (' / '.join(descriptions) or '（无）')
        if shape.tag == _P + 'graphicFrame':
            data = shape.find(f'{_A}graphic/{_A}graphicData')
            if data is None:
                continue
            for item in data:
                if item.tag == _A + 'tbl':
                    yield from _table(item)
                elif item.tag in (_C + 'chart', _CX + 'chart'):
                    classic = item.tag == _C + 'chart'
                    kind = 'chart' if classic else _CHART_EX_REL
                    target = package.target(part, rels.get(item.get(_R + 'id')), kind)
                    root = package.xml(target, (_C if classic else _CX) + 'chartSpace')
                    yield '【图表】'
                    yield from (_classic_chart if classic else _extended_chart)(root, target)
    notes = [rel for rel in rels.values() if rel.kind == 'notesSlide']
    if len(notes) > 1:
        raise PresentationError(f'PPTX 幻灯片有多个备注部件（{part[:160]}）')
    if notes:
        target = package.target(part, notes[0], 'notesSlide')
        tree = _tree(package.xml(target, _P + 'notes'), target)
        yield '【演讲者备注】'
        for shape in _shapes(tree):
            body = shape.find(_P + 'txBody')
            placeholder = shape.find(f'{_P}nvSpPr/{_P}nvPr/{_P}ph')
            if body is not None and (placeholder is None or placeholder.get('type', 'obj') in ('body', 'obj')):
                yield from _paragraphs(body)


class _Text:
    def __init__(self):
        self.lines = []
        self.left = _MAX_TEXT - len(_TRUNCATED) - 1
        self.truncated = False

    def add(self, line):
        if self.truncated:
            return
        if len(line) + 1 > self.left:
            self.lines.append(line[:max(self.left - 1, 0)])
            self.lines.append(_TRUNCATED)
            self.truncated = True
        else:
            self.lines.append(line)
            self.left -= len(line) + 1


def _inspect(archive, offset, limit):
    package = _Package(archive)
    package.xml('[Content_Types].xml', _CT + 'Types')
    documents = [rel for rel in package.relationships(required=True).values() if rel.kind == 'officeDocument']
    if len(documents) != 1:
        raise PresentationError('PPTX 必须有且仅有一个文稿入口关系')
    main = package.target('', documents[0], 'officeDocument')
    root = package.xml(main, _P + 'presentation')
    ids = root.findall(f'{_P}sldIdLst/{_P}sldId')
    if len(ids) > _MAX_SLIDES:
        raise _limit('PPTX 幻灯片超过 300 页')
    rels = package.relationships(main, required=bool(ids))
    text = _Text()
    text.add(f'PPTX 共 {len(ids)} 页')
    end = min(len(ids), offset + limit - 1) if limit is not None else len(ids)
    if limit == 0:
        text.add('（本次未请求输出幻灯片内容）')
    elif ids and offset > end:
        text.add('（请求的页码超出了文稿范围）')
    elif ids and (offset > 1 or end < len(ids)):
        text.add(f'（显示第 {offset}–{end} 页）')
    seen_ids, seen_parts = set(), set()
    for i, slide_id in enumerate(ids, 1):
        target = package.target(main, rels.get(slide_id.get(_R + 'id')), 'slide')
        sid = slide_id.get('id')
        if not sid or sid in seen_ids or target in seen_parts:
            raise PresentationError(f'PPTX 第 {i} 页的幻灯片 ID 缺失或重复')
        seen_ids.add(sid)
        seen_parts.add(target)
        slide = package.xml(target, _P + 'sld')
        selected = offset <= i <= end
        if selected:
            hidden = '（隐藏）' if slide.get('show') in ('0', 'false') else ''
            text.add(f'\n== 第 {i} 页{hidden} ==')
        for line in _slide(package, target, slide):
            if selected:
                text.add(line)
    return '\n'.join(text.lines), text.truncated


def _read_in_worker(path, offset, limit):
    flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0)
    with _ZipInput(io.FileIO(os.open(path, flags), 'rb')) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise PresentationError('PPTX 路径必须指向普通文件')
        if before.st_size > _MAX_ARCHIVE:
            raise _limit('PPTX 文件超过 64 MiB')
        with zipfile.ZipFile(stream) as archive:
            text, truncated = _inspect(archive, offset, limit)

        stream.seek(0)
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(256 * 1024), b''):
            digest.update(chunk)
            if stream.tell() > _MAX_ARCHIVE:
                raise _limit('PPTX 文件超过 64 MiB')
        after = os.fstat(stream.fileno())
        if ((before.st_mtime_ns, before.st_ctime_ns, before.st_size) !=
                (after.st_mtime_ns, after.st_ctime_ns, after.st_size)
                or not os.path.samestat(after, os.stat(path))):
            raise PresentationError('PPTX 文件在读取期间发生了变化，请重新读取', 'pptx_changed')
        return dict(text=text, truncated=truncated, stamp=[after.st_mtime_ns, after.st_size],
                    digest=digest.hexdigest())


def worker_main(args):
    path, offset, limit = args
    try:
        result = _read_in_worker(path, int(offset), int(limit) if limit else None)
    except PresentationError as exc:
        result = dict(error=str(exc), code=exc.code)
    except (zipfile.BadZipFile, zlib.error, ValueError, OverflowError, OSError) as exc:
        result = dict(error=f'PPTX 无法读取或 ZIP 包损坏（{str(exc)[:180]}）', code='pptx_invalid')
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=True).encode('ascii'))
    return 0


@dataclass(frozen=True)
class PresentationContent:
    text: str
    truncated: bool


def inspect_content(path: Path, *, offset=1, limit=None, watcher=None, control=None):
    """Run the parser in a fresh task directory and reap it before cleanup."""
    from . import processwait
    from .runcontrol import RunStopped

    if path.suffix.lower() != '.pptx':
        raise PresentationError('请选择 .pptx 文件')
    command = ([sys.executable, '--_presentation-content-worker'] if getattr(sys, 'frozen', False)
               else [sys.executable, '-I', str(Path(__file__).resolve())])
    command.extend((str(path.absolute()), str(max(1, offset)), '' if limit is None else str(max(0, limit))))
    try:
        with tempfile.TemporaryDirectory(prefix='feiyu-pptx-') as directory:
            with (Path(directory) / 'result.json').open('w+b') as output:
                done = processwait.run(command, cwd=directory, env=None, stdout=output,
                                       stderr=subprocess.DEVNULL, timeout=_TIMEOUT, control=control)
                if done.reason == 'timeout':
                    raise PresentationError(f'PPTX 内容提取超时（{_TIMEOUT:g} 秒）', 'pptx_timeout')
                if done.reason:
                    raise RunStopped(done.reason)
                if done.code or done.error:
                    raise PresentationError('PPTX 解析进程异常退出', 'pptx_worker')
                output.seek(0)
                raw = output.read(_MAX_REPLY + 1)
    except OSError as exc:
        raise PresentationError('无法启动或访问 PPTX 解析进程', 'pptx_worker') from exc
    try:
        if len(raw) > _MAX_REPLY:
            raise ValueError('reply too large')
        reply = json.loads(raw)
        if 'error' in reply:
            raise PresentationError(reply['error'], reply['code'])
        if watcher is not None:
            watcher.record_fingerprint(path, tuple(reply['stamp']), reply['digest'])
        return PresentationContent(reply['text'], reply['truncated'])
    except PresentationError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        raise PresentationError('PPTX 解析进程返回了无效结果', 'pptx_worker') from exc


if __name__ == '__main__':
    raise SystemExit(worker_main(sys.argv[1:]))
