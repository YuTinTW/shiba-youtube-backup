"""可測試的下載元件更新器：互斥鎖、暫存安裝、驗證切換、失敗恢復與可追溯性。"""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

DEFAULT_PACKAGE = 'yt-dlp[default]'
PYPI_SIMPLE_URL = 'https://pypi.org/simple'


class UpdateError(Exception):
    pass


def _default_pip_runner(python_exe, staging_dir, package_spec, allow_pre=False, extra_args=()):
    cmd = [
        str(python_exe), '-m', 'pip', 'install',
        '--index-url', PYPI_SIMPLE_URL,
        '--upgrade',
        '--target', str(staging_dir),
    ]
    if allow_pre:
        cmd.append('--pre')
    cmd.extend(extra_args)
    cmd.append(package_spec)
    env = dict(os.environ)
    env['PIP_CONFIG_FILE'] = '/dev/null'
    env['PIP_NO_INDEX'] = '0'
    for key in ('PYTHONSTARTUP', 'PYTHONINSPECT', 'PYTHONPATH'):
        env.pop(key, None)
    return subprocess.run(cmd, env=env, text=True)


def _default_verify_runner(python_exe, staging_dir):
    code = (
        'import json, importlib.metadata as md, yt_dlp, yt_dlp_ejs; '
        'from yt_dlp.version import __version__; '
        'dists = {}; '
        'for name in ("yt-dlp", "yt-dlp-ejs"): '
        '    dists[name] = md.version(name); '
        'print(json.dumps({"yt_dlp": __version__, "dists": dists}, ensure_ascii=False))'
    )
    env = dict(os.environ)
    env['PYTHONPATH'] = str(staging_dir)
    for key in ('PYTHONSTARTUP', 'PYTHONINSPECT'):
        env.pop(key, None)
    res = subprocess.run([str(python_exe), '-B', '-c', code], env=env,
                         capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        raise UpdateError('新元件匯入檢查失敗：' + (res.stderr.strip() or res.stdout.strip() or '未知錯誤'))
    try:
        info = json.loads(res.stdout.strip().splitlines()[-1])
        if not isinstance(info, dict) or 'yt_dlp' not in info:
            raise ValueError()
        return info
    except (ValueError, IndexError) as e:
        raise UpdateError('無法解析新元件版本資訊。') from e


def _collect_dist_hashes(staging_dir):
    records = {}
    for record_file in sorted(Path(staging_dir).glob('*.dist-info/RECORD')):
        dist_name = record_file.parent.name
        records[dist_name] = hashlib.sha256(record_file.read_bytes()).hexdigest()
    return records


def _default_mover(src, dst):
    shutil.move(str(src), str(dst))


def update_runtime_packages(
    project_root,
    python_exe=None,
    package_spec=DEFAULT_PACKAGE,
    allow_pre=False,
    extra_pip_args=(),
    pip_runner=None,
    verify_runner=None,
    mover=None,
):
    root = Path(project_root).resolve()
    python_exe = Path(python_exe or sys.executable)
    pip_runner = pip_runner or _default_pip_runner
    verify_runner = verify_runner or _default_verify_runner
    mover = mover or _default_mover

    runtime_dir = root / '.runtime-packages'
    lock_path = root / '.runtime-update.lock'
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise UpdateError('另一個更新程序正在執行中，請稍候再試。') from e

        staging_dir = Path(tempfile.mkdtemp(prefix='.runtime-update.', dir=root))
        backup_dir = None
        backup_pkg_dir = None
        switched = False
        try:
            pip_res = pip_runner(python_exe, staging_dir, package_spec,
                                 allow_pre=allow_pre, extra_args=extra_pip_args)
            if getattr(pip_res, 'returncode', 1) != 0:
                raise UpdateError('套件下載或安裝失敗，原有下載元件未變更。')

            verify_info = verify_runner(python_exe, staging_dir)
            manifest = {
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'package_spec': package_spec,
                'allow_pre': bool(allow_pre),
                'index_url': PYPI_SIMPLE_URL,
                'versions': verify_info,
                'dist_record_sha256': _collect_dist_hashes(staging_dir),
            }
            (staging_dir / '.update-manifest.json').write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

            if runtime_dir.exists():
                backup_dir = Path(tempfile.mkdtemp(prefix='.runtime-backup.', dir=root))
                backup_pkg_dir = backup_dir / 'packages'
                try:
                    mover(runtime_dir, backup_pkg_dir)
                except Exception as e:
                    raise UpdateError('備份現有元件失敗，原有下載元件未變更。') from e

            try:
                mover(staging_dir, runtime_dir)
                switched = True
            except Exception as switch_err:
                if backup_pkg_dir is not None and backup_pkg_dir.exists():
                    try:
                        mover(backup_pkg_dir, runtime_dir)
                    except Exception as restore_err:
                        raise UpdateError(
                            '切換新元件失敗且自動還原失敗，請手動將 {} 移回 {}。'.format(
                                backup_pkg_dir, runtime_dir)
                        ) from restore_err
                    raise UpdateError('無法切換新元件，已還原原有元件。') from switch_err
                raise UpdateError('無法切換新元件，原有狀態未完成更新。') from switch_err

            return {
                'status': 'updated',
                'manifest': manifest,
                'backup_dir': str(backup_dir) if backup_dir else None,
            }
        finally:
            if not switched and staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            if switched and backup_dir is not None and backup_dir.exists():
                # 只保留最新一份成功切換前備份，避免無限累積同時保留人工復原途徑
                for old in sorted(root.glob('.runtime-backup.*')):
                    if old != backup_dir and old.is_dir():
                        shutil.rmtree(old, ignore_errors=True)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    allow_pre = '--pre' in argv
    root = Path(__file__).resolve().parent.parent
    try:
        result = update_runtime_packages(root, python_exe=sys.executable, allow_pre=allow_pre)
    except UpdateError as e:
        print(str(e), file=sys.stderr)
        return 1
    versions = result['manifest']['versions']
    print('更新版本：', versions.get('yt_dlp', 'unknown'))
    print('更新完成。請關閉並重新啟動 App，再讀取格式與下載。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
