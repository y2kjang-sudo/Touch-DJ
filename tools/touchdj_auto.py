#!/usr/bin/env python3
"""Touch DJ automatic bundle update for macOS (runs every 30 s from a LaunchAgent).

Looks at every mounted USB that already has dj1_rekordbox.tar. When rekordbox has exported
to it since the bundles were made (export.pdb is newer than dj1_rekordbox.tar) and the
export has been quiet for a minute, it updates the bundles and shows a notification.

  touchdj_auto.py                 one check (what the LaunchAgent runs)
  touchdj_auto.py --now /Volumes/X   update that USB right away (also makes bundles on a new USB)
"""
import os, sys, time, json, shlex, fcntl, subprocess, tempfile, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_bundles as mb  # noqa: E402

SETTLE = 60          # seconds without changes before an export counts as finished
LOG = os.path.expanduser('~/Library/Logs/touchdj.log')
LOCK = os.path.join(tempfile.gettempdir(), 'touchdj.lock')   # not on the USB: FAT32 has no file locks
STATE = os.path.join(HERE, 'state.json')
SAY = None   # set to print when run from the double-click file, so progress shows in the window


def log(msg):
    if SAY: SAY(msg)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 1_000_000: os.remove(LOG)
        with open(LOG, 'a') as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')
    except OSError: pass


def notify(text, sub=''):
    q = lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    script = 'display notification %s with title "터치 DJ"%s' % (q(text), (' subtitle ' + q(sub)) if sub else '')
    try: subprocess.run(['osascript', '-e', script], timeout=10)
    except Exception: pass


def mtime(p):
    try: return os.path.getmtime(p)
    except OSError: return 0


def newest(root):
    """latest modification under the parts rekordbox writes during an export"""
    t = max(mtime(os.path.join(root, 'PIONEER', 'rekordbox', f)) for f in ('export.pdb', 'exportExt.pdb', 'exportLibrary.db'))
    for top in ('PIONEER/USBANLZ', 'Contents'):
        for d, ds, fs in os.walk(os.path.join(root, top)):
            t = max([t, mtime(d)] + [mtime(os.path.join(d, f)) for f in fs if not f.startswith('.')])
    return t


def pending(root):
    pdb = os.path.join(root, 'PIONEER', 'rekordbox', 'export.pdb')
    dj1 = os.path.join(root, 'dj1_rekordbox.tar')
    return os.path.isfile(pdb) and os.path.isfile(dj1) and mtime(pdb) > mtime(dj1) + 2


def load_state():
    try:
        with open(STATE) as f: return json.load(f)
    except (OSError, ValueError): return {}


def save_state(st):
    try:
        with open(STATE, 'w') as f: json.dump(st, f)
    except OSError: pass


def in_terminal(root):
    """macOS often refuses USB access to background programs. Terminal already has it (the first update ran
    there), so open a Terminal window that runs the same update."""
    cmd = os.path.join(HERE, 'touchdj-update.command')
    with open(cmd, 'w') as f:
        f.write('#!/bin/zsh\nclear\necho "터치 DJ 묶음 업데이트 · %s"\necho "끝날 때까지 USB를 빼지 마세요."\necho\n'
                '%s %s --now %s\necho\necho "이 창은 닫아도 돼요."\n'
                % (os.path.basename(root), shlex.quote(sys.executable), shlex.quote(os.path.join(HERE, 'touchdj_auto.py')), shlex.quote(root)))
    os.chmod(cmd, 0o755)
    subprocess.run(['open', '-a', 'Terminal', cmd], timeout=20)
    log('handed over to Terminal ' + root)


def run(root, auto=False):
    name = os.path.basename(root.rstrip('/'))
    if auto:
        try: os.listdir(root)
        except PermissionError:
            in_terminal(root); return 0
    notify('USB 묶음을 업데이트하고 있어요. 알림이 끝날 때까지 USB를 빼지 마세요.', name)
    log('update start ' + root)
    try:
        r = mb.update(root, log=log)
    except PermissionError as e:
        log('no USB permission ' + root)
        if auto:
            in_terminal(root); return 0
        notify('USB를 읽을 권한이 없어요. 시스템 설정 > 개인정보 보호 및 보안 > 파일 및 폴더에서 터미널의 \'이동식 볼륨\'을 켜 주세요.', name)
        return 1
    except BaseException as e:
        log('update failed ' + root + '\n' + traceback.format_exc())
        notify('업데이트하지 못했어요: ' + str(e)[:120], name)
        return 1
    what = []
    if r['added']: what.append('새 곡 %d개' % r['added'])
    if r['changed']: what.append('바뀐 곡 %d개' % r['changed'])
    if r.get('rekordbox') == 'same' and not r['added'] and not r['changed']:
        notify('바뀐 게 없어서 그대로 뒀어요. USB를 빼도 돼요.', name)
        log('nothing changed %s' % root); print('바뀐 게 없어서 그대로 뒀어요.'); return 0
    what.append('플레이리스트·큐 반영')
    notify(' · '.join(what) + '. 이제 USB를 빼도 돼요.', name)
    log('update done %s %s' % (root, r))
    print('완료: ' + ' · '.join(what))
    print('TV에서 고를 파일: ' + ', '.join(r['bundles']))
    return 0


def main():
    global SAY
    now = len(sys.argv) > 2 and sys.argv[1] == '--now'
    lock = open(LOCK, 'w')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:                               # another update is still running
        if now: print('이미 다른 업데이트가 진행 중이에요. 알림이 뜰 때까지 기다려 주세요.')
        return 2 if now else 0
    if now:
        SAY = lambda m: print(m.replace('writing ', '쓰는 중: '), flush=True)
        return run(os.path.abspath(sys.argv[2]))
    try: vols = [os.path.join('/Volumes', v) for v in os.listdir('/Volumes')]
    except OSError: return 0
    st = load_state()
    for root in vols:
        try:
            if pending(root) and time.time() - newest(root) > SETTLE:
                # one export = at most two tries (10 minutes apart), so a failure never repeats every 30 s
                pm = mtime(os.path.join(root, 'PIONEER', 'rekordbox', 'export.pdb'))
                s = st.get(root) or {}
                if s.get('pdb') == pm and (s.get('tries', 0) >= 2 or time.time() - s.get('t', 0) < 600):
                    continue
                st[root] = {'pdb': pm, 'tries': (s.get('tries', 0) + 1) if s.get('pdb') == pm else 1, 't': time.time()}
                save_state(st)
                run(root, auto=True)
        except PermissionError:
            log('no permission for ' + root + ' (allow removable volumes for python3 in System Settings)')
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
