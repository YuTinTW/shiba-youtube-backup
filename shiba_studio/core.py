"""下載核心：不接觸視窗；所有訊息透過 emit 傳給介面。"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, parse_qs


MAX_DIAGNOSTIC_CHARS = 2000
MIN_FREE_SPACE_BYTES = 100 * 1024 * 1024

_SENSITIVE_QUERY_RE = re.compile(
    r'([?&](?:token|sig|lsig|signature|key|api_key|apikey|auth|secret|password|passwd|session|cookie|credential)=)([^&#\s]+)',
    re.IGNORECASE,
)
_URL_USERINFO_RE = re.compile(r'(https?://)([^/@\s]+)@', re.IGNORECASE)
_AUTH_HEADER_RE = re.compile(r'((?:authorization|cookie|set-cookie)\s*:\s*)([^\r\n]+)', re.IGNORECASE)
_HOME_USERS_RE = re.compile(r'/Users/[^/\s]+')


def sanitize_diagnostic(text, max_chars=MAX_DIAGNOSTIC_CHARS):
    value = str(text if text is not None else '')
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', value)
    value = value.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
    value = _URL_USERINFO_RE.sub(r'\1[REDACTED]@', value)
    value = _SENSITIVE_QUERY_RE.sub(r'\1[REDACTED]', value)
    value = _AUTH_HEADER_RE.sub(r'\1[REDACTED]', value)
    try:
        home = str(Path.home())
        if home:
            value = value.replace(home, '~')
    except OSError:
        pass
    value = _HOME_USERS_RE.sub('/Users/[USER]', value)
    if len(value) > max_chars:
        suffix = '... [TRUNCATED]'
        keep = max(0, max_chars - len(suffix))
        value = value[:keep] + suffix
    return value


def check_disk_space(folder, estimated_bytes=0):
    required = MIN_FREE_SPACE_BYTES
    if isinstance(estimated_bytes, (int, float)) and estimated_bytes > 0:
        required = max(required, int(estimated_bytes * 1.2) + 50 * 1024 * 1024)
    try:
        free = shutil.disk_usage(folder).free
    except OSError:
        return
    if free < required:
        raise UserError('儲存位置可用磁碟空間不足。請清理空間或選擇其他資料夾後重試。')


class UserError(Exception):
    pass


def validate_url(value):
    value = value.strip()
    try:
        u = urlsplit(value)
        host = (u.hostname or '').lower()
        if u.scheme not in ('https', 'http') or u.username or u.password or u.port:
            raise ValueError()
        if host in ('youtu.be', 'www.youtu.be'):
            video_id = u.path.strip('/')
        elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
            video_id = parse_qs(u.query).get('v', [''])[0] if u.path == '/watch' else (
                u.path.split('/')[2] if re.match(r'^/(shorts|live|embed)/', u.path) else '')
        else:
            raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            raise ValueError()
    except (ValueError, IndexError):
        raise UserError('網址格式不正確。請貼上單支 YouTube 影片的完整網址，再讀取格式。')
    return 'https://www.youtube.com/watch?v=' + video_id


def check_folder(value):
    p = Path(value or '~/Downloads').expanduser()
    try:
        p.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=p) as f:
            f.write(b'check')
    except OSError as e:
        raise UserError('無法寫入儲存位置。請選擇有寫入權限的資料夾，並檢查磁碟空間。') from e
    return p.resolve()


ALLOWED_TOOLS = frozenset(('ffmpeg', 'ffprobe', 'deno'))


def tool(name):
    if name not in ALLOWED_TOOLS:
        raise UserError('不允許呼叫未授權的工具：' + str(name))
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    bundled = root / 'tools' / name
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    if not getattr(sys, 'frozen', False):
        found = shutil.which(name)
        if found:
            candidate = Path(found)
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    raise UserError('缺少必要工具 ' + name + '。請重新安裝完整的應用程式；開發環境請先安裝工具。')


def run_process(args, timeout=60):
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise UserError('處理時間過長。請稍後重試，或改選其他格式。') from e
    except (OSError, subprocess.CalledProcessError) as e:
        raise UserError('外部工具執行失敗。請檢查安裝完整性、磁碟空間，或改選其他格式。') from e


def preflight():
    for name in ('ffmpeg', 'ffprobe', 'deno'):
        run_process([tool(name), '--version' if name == 'deno' else '-version'], 15)


def ydl_options(emit):
    try:
        import yt_dlp
        import yt_dlp_ejs  # 隨附解題元件，避免首次使用時臨時下載
    except ImportError as e:
        raise UserError('下載元件不完整。請重新安裝 App；開發環境請安裝 requirements.txt。') from e

    class Logger:
        def debug(self, msg):
            pass
        def warning(self, msg):
            emit({'event': 'warning', 'detail': sanitize_diagnostic(msg)})
        def error(self, msg):
            emit({'event': 'diagnostic', 'detail': sanitize_diagnostic(msg)})
    return {
        'quiet': True, 'no_warnings': False, 'logger': Logger(), 'noplaylist': True,
        'allowed_extractors': ['youtube'],
        'nocheckcertificate': False,
        'cookiefile': None,
        'socket_timeout': 25, 'retries': 2, 'fragment_retries': 2,
        'ffmpeg_location': str(Path(tool('ffmpeg')).parent),
        'js_runtimes': {'deno': {'path': tool('deno')}},
        'remote_components': set(),
    }


def is_http_format_url(fmt):
    raw_url = fmt.get('url')
    if not raw_url:
        return True
    if not isinstance(raw_url, str):
        return False
    return urlsplit(raw_url.strip()).scheme.lower() in ('https', 'http')


def format_choices(info):
    rows = []
    ids = set()
    for f in info.get('formats') or []:
        fid = str(f.get('format_id', ''))
        if not fid or fid in ids or f.get('has_drm') or not is_http_format_url(f):
            continue
        video = f.get('vcodec') not in (None, 'none')
        audio = f.get('acodec') not in (None, 'none')
        size = f.get('filesize') or f.get('filesize_approx') or 0
        if not isinstance(size, (int, float)) or size < 0:
            size = 0
        if video and not audio and f.get('ext') == 'mp4':
            label = 'MP4 {} {}fps +音訊'.format(
                f.get('height') or '?', f.get('fps') or '?')
            rows.append({'id': fid, 'kind': 'video', 'label': label,
                         'height': f.get('height') or 0, 'ext': 'mp4', 'filesize': int(size)})
        elif audio and not video:
            abr = f.get('abr')
            ext = 'm4a' if f.get('ext') in ('mp4', 'm4a') else f.get('ext') or 'bin'
            bitrate = '{:g} kbps'.format(abr) if abr else '碼率未知'
            label = '{} 音訊 · {}'.format(ext.upper(), bitrate)
            rows.append({'id': fid, 'kind': 'audio', 'label': label, 'height': 0, 'ext': ext, 'filesize': int(size)})
        else:
            continue
        ids.add(fid)
    return sorted(rows, key=lambda r: (r['kind'] != 'video', -r['height'], r['id']))


def extract(url, emit):
    import yt_dlp
    preflight()
    emit({'event': 'stage', 'stage': 'reading', 'text': '正在讀取影片格式…'})
    opts = ydl_options(emit)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(validate_url(url), download=False)
    if not info or info.get('_type') in ('playlist', 'multi_video'):
        raise UserError('請使用單支影片網址，這個版本不支援播放清單。')
    if info.get('is_live'):
        raise UserError('這個版本不下載進行中的直播。請在直播結束後重試。')
    rows = format_choices(info)
    if not rows:
        raise UserError('沒有可下載的格式。請確認影片可公開觀看，或換一支影片重試。')
    emit({'event': 'formats', 'title': info.get('title') or '未命名影片',
          'video_id': info.get('id'), 'url': validate_url(url), 'choices': rows})
    return info, rows


def safe_name(text):
    value = re.sub(r'[\x00-\x1f/:\\?*"<>|]', '_', text).strip(' .')[:100]
    value = value.encode('utf-8')[:160].decode('utf-8', errors='ignore')
    return value or 'YouTube影片'


def verify_output(path, kind):
    p = Path(path).resolve()
    if not p.is_file() or p.stat().st_size == 0:
        raise UserError('輸出檔案不存在或為空。請檢查磁碟空間後重試。')
    result = run_process([tool('ffprobe'), '-v', 'error', '-show_streams', '-of', 'json', str(p)])
    try:
        types = {s.get('codec_type') for s in json.loads(result.stdout).get('streams', [])}
    except (ValueError, TypeError):
        raise UserError('無法確認輸出檔案內容，請重新下載。')
    if 'audio' not in types or (kind == 'video' and 'video' not in types):
        raise UserError('輸出檔缺少必要的影音串流。請改選其他格式重試。')


def safe_ext(text):
    value = re.sub(r'[^A-Za-z0-9]', '', str(text or ''))[:12]
    return value or 'bin'


def ensure_within_temp(path, temp_dir):
    candidate = Path(path)
    if candidate.is_symlink():
        raise UserError('暫存檔案路徑異常，已中止處理。')
    resolved_temp = Path(temp_dir).resolve()
    resolved_candidate = candidate.resolve()
    if not resolved_candidate.is_relative_to(resolved_temp) or resolved_candidate == resolved_temp:
        raise UserError('暫存檔案路徑超出安全範圍，已中止處理。')
    if not resolved_candidate.is_file():
        raise UserError('下載的暫存檔案不存在，請重試。')
    return resolved_candidate


def publish_file(source, folder, name):
    # 硬連結在同一檔案系統中原子建立，遇到既有檔名絕不覆蓋。
    base = Path(name)
    if not name or base.name != name or name in ('.', '..'):
        raise UserError('輸出檔名不合法，已中止儲存。')
    folder = Path(folder)
    dir_flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        dir_fd = os.open(folder, dir_flags)
    except OSError as e:
        raise UserError('儲存資料夾不可用或為不安全連結，請重新選擇資料夾。') from e
    try:
        for n in range(10000):
            filename = base.name if n == 0 else '{} ({}){}'.format(base.stem, n, base.suffix)
            target = folder / filename
            try:
                os.link(source, filename, dst_dir_fd=dir_fd)
                return target
            except FileExistsError:
                continue
            except OSError:
                # exFAT 等磁碟不支援硬連結；以排他建立模式避免覆蓋。
                open_flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL
                              | getattr(os, 'O_NOFOLLOW', 0))
                try:
                    fd = os.open(filename, open_flags, 0o644, dir_fd=dir_fd)
                except FileExistsError:
                    continue
                created_stat = os.fstat(fd)
                try:
                    with os.fdopen(fd, 'wb') as output, open(source, 'rb') as incoming:
                        shutil.copyfileobj(incoming, output)
                        output.flush()
                        os.fsync(output.fileno())
                    return target
                except BaseException:
                    try:
                        current = os.stat(filename, dir_fd=dir_fd, follow_symlinks=False)
                        if (current.st_dev == created_stat.st_dev
                                and current.st_ino == created_stat.st_ino):
                            os.unlink(filename, dir_fd=dir_fd)
                    except OSError:
                        pass
                    raise
        raise UserError('同名檔案過多，請更換儲存資料夾後重試。')
    finally:
        os.close(dir_fd)


def download(url, folder, selected_ids, emit):
    import yt_dlp
    safe_url = validate_url(url)
    folder = check_folder(folder)
    info, rows = extract(safe_url, emit)
    available = {r['id']: r for r in rows}
    if not selected_ids or len(set(selected_ids)) != len(selected_ids) or any(x not in available for x in selected_ids):
        raise UserError('格式已變更或尚未選取。請重新讀取格式並勾選。')
    audio = [f for f in info.get('formats', []) if f.get('acodec') not in (None, 'none')
             and f.get('vcodec') == 'none' and f.get('ext') in ('m4a', 'mp4')
             and not f.get('has_drm') and is_http_format_url(f)]
    audio.sort(key=lambda f: f.get('abr') or 0, reverse=True)
    outputs, errors = [], []
    for index, fid in enumerate(selected_ids, 1):
        row = available[fid]
        label = '第 {}/{} 項'.format(index, len(selected_ids))
        try:
            est_size = row.get('filesize') or 0
            if row.get('kind') == 'video' and audio:
                est_size += int(audio[0].get('filesize') or audio[0].get('filesize_approx') or 0)
            check_disk_space(folder, est_size)
            with tempfile.TemporaryDirectory(prefix='.shiba-', dir=folder, ignore_cleanup_errors=True) as temp:
                temp = Path(temp)
                last_progress = [0.0]
                def hook(data):
                    status = data.get('status')
                    if status == 'downloading':
                        now = time.monotonic()
                        if now - last_progress[0] < .15:
                            return
                        last_progress[0] = now
                        total = data.get('total_bytes')  # 不把估計大小當精確百分比
                        done = data.get('downloaded_bytes') or 0
                        pct = min(100, done * 100 / total) if total else None
                        emit({'event': 'progress', 'percent': pct,
                              'text': label + '：下載中（目前串流）', 'bytes': done})
                    elif status == 'finished':
                        emit({'event': 'stage', 'stage': 'processing',
                              'text': label + '：串流下載結束，正在處理…'})
                opts = ydl_options(emit)
                opts.update({'format': fid, 'outtmpl': str(temp / 'source.%(ext)s'),
                             'progress_hooks': [hook], 'continuedl': False})
                emit({'event': 'stage', 'stage': 'downloading', 'text': label + '：正在下載…'})
                with yt_dlp.YoutubeDL(opts) as ydl:
                    result = ydl.extract_info(safe_url, download=True)
                    video_path = ensure_within_temp(ydl.prepare_filename(result), temp)
                if row['kind'] == 'video':
                    if not audio:
                        raise UserError('找不到可搭配的 MP4 音訊。請改選純音訊或其他影片。')
                    opts.update({'format': str(audio[0]['format_id']), 'outtmpl': str(temp / 'sound.%(ext)s')})
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        result = ydl.extract_info(safe_url, download=True)
                        audio_path = ensure_within_temp(ydl.prepare_filename(result), temp)
                    emit({'event': 'stage', 'stage': 'merging', 'text': label + '：正在合併影像與音訊…'})
                    final = temp / 'merged.mp4'
                    run_process([tool('ffmpeg'), '-nostdin', '-v', 'error', '-n', '-i', str(video_path),
                                 '-i', str(audio_path), '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', str(final)], 3600)
                else:
                    final = video_path
                emit({'event': 'stage', 'stage': 'verifying', 'text': label + '：正在檢查輸出檔…'})
                verify_output(final, row['kind'])
                name = '{} [{}]_{}.{}'.format(safe_name(info.get('title', '影片')),
                                              safe_name(info['id']), safe_name(fid), safe_ext(row['ext']))
                target = publish_file(final, folder, name)
                outputs.append(str(target))
                emit({'event': 'item_done', 'path': str(target)})
        except Exception as e:
            errors.append({'id': fid, 'message': friendly_error(e)})
            emit({'event': 'diagnostic', 'detail': sanitize_diagnostic(repr(e))})
    emit({'event': 'result', 'outputs': outputs, 'errors': errors,
          'status': 'done' if outputs and not errors else 'partial' if outputs else 'error'})


def friendly_error(error):
    if isinstance(error, UserError):
        return str(error)
    msg = str(error).lower()
    if '403' in msg and any(x in msg for x in ('http', 'forbidden')):
        return '影音下載請求遭拒絕（HTTP 403）。請先更新下載元件，關閉並重新啟動 App，再讀取格式後重試；若仍失敗，請提供影片網址與診斷記錄。'
    if any(x in msg for x in ('network', 'timed out', 'resolve', 'connection', 'urlopen')):
        return '連線失敗。請檢查網路，稍後重新讀取格式。'
    if any(x in msg for x in ('private', 'unavailable', 'not available', 'sign in', 'login', 'age-restricted')):
        return '無法存取這支影片。請確認它可公開觀看，或改用其他影片。'
    if any(x in msg for x in ('permission', 'read-only', 'space', 'disk')):
        return '無法寫入檔案。請確認資料夾權限與可用空間，或選擇其他位置。'
    if isinstance(error, ImportError):
        return '下載元件不完整。請重新安裝完整 App，或依 README 安裝開發套件。'
    return '處理失敗。請重新讀取格式後重試；若仍失敗，請查看診斷記錄並更新 App。'
