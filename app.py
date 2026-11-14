"""入口：一般啟動顯示視窗；--worker 為背景工作的內部入口。"""
import json
import sys

MAX_WORKER_REQUEST_BYTES = 16384
MAX_URL_LENGTH = 2048
MAX_FOLDER_LENGTH = 4096
MAX_SELECTED_ITEMS = 100
MAX_FORMAT_ID_LENGTH = 64


def parse_worker_request(raw_line):
    if not isinstance(raw_line, str) or not raw_line.strip():
        raise ValueError('Empty worker request')
    if len(raw_line.encode('utf-8', errors='replace')) > MAX_WORKER_REQUEST_BYTES:
        raise ValueError('Worker request too large')
    request = json.loads(raw_line)
    if not isinstance(request, dict):
        raise ValueError('Worker request must be a JSON object')
    action = request.get('action')
    if action not in ('read', 'download'):
        raise ValueError('Unknown action')
    url = request.get('url')
    if not isinstance(url, str) or not url.strip() or len(url) > MAX_URL_LENGTH:
        raise ValueError('Invalid url field')
    if action == 'download':
        folder = request.get('folder')
        if not isinstance(folder, str) or len(folder) > MAX_FOLDER_LENGTH:
            raise ValueError('Invalid folder field')
        selected = request.get('selected')
        if (not isinstance(selected, list) or not selected
                or len(selected) > MAX_SELECTED_ITEMS
                or any(not isinstance(item, str) or not item or len(item) > MAX_FORMAT_ID_LENGTH
                       for item in selected)):
            raise ValueError('Invalid selected field')
    return request


def run_worker(stdin=None, stdout=None):
    from shiba_studio.core import extract, download, friendly_error, sanitize_diagnostic
    in_stream = stdin if stdin is not None else sys.stdin
    out_stream = stdout if stdout is not None else sys.stdout

    def emit(event):
        out_stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        out_stream.flush()

    try:
        raw_line = in_stream.readline(MAX_WORKER_REQUEST_BYTES + 1)
        if len(raw_line.encode('utf-8', errors='replace')) > MAX_WORKER_REQUEST_BYTES:
            raise ValueError('Worker request too large')
        request = parse_worker_request(raw_line)
        if request['action'] == 'read':
            extract(request['url'], emit)
        else:
            download(request['url'], request['folder'], request['selected'], emit)
    except Exception as e:
        emit({'event': 'diagnostic', 'detail': sanitize_diagnostic(repr(e))})
        emit({'event': 'error', 'message': friendly_error(e)})
        return 1
    return 0


def main():
    if '--worker' in sys.argv:
        return run_worker()
    from shiba_studio.gui import run
    run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
