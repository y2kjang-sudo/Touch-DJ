#!/usr/bin/env python3
"""Pack a rekordbox USB into bundles the StanbyMe browser can open.

The TV browser can only pick single files, and FAT32 USB sticks cannot hold
files over 4 GB, so the USB is packed into plain (uncompressed) tar files:

  dj1_rekordbox.tar   PIONEER folder without artwork (playlists, cues, grids)
  dj2_music.tar ...   Contents folder, split so each file stays under 3.8 GB

Usage:
  python3 make_bundles.py /Volumes/USB            update: rebuild dj1, pack only new or changed
                                                  songs (first run builds everything)
  python3 make_bundles.py /Volumes/USB --rebuild  build all music bundles again from scratch

New songs are added to the last music bundle while it is small (under 1.5 GB), otherwise
they start the next one, so the number of files stays low. Every bundle is written under a
temporary name and renamed only when complete: pulling the USB out half way never breaks
the bundles that were already there.
"""
import os, re, sys, shutil, tarfile, unicodedata

LIMIT = 3_800_000_000        # max bytes per bundle (FAT32 allows just under 4 GiB)
MERGE_UNDER = 1_500_000_000  # keep adding new songs to the last bundle while it is smaller than this
MUSIC = re.compile(r'^dj(\d+)_music\.tar$')
CHUNK = 1 << 22


def key(path):
    # macOS stores Hangul decomposed, rekordbox composed; compare in one form
    return unicodedata.normalize('NFC', path)


def walk(root, top, skip=()):
    out = []
    for d, ds, fs in os.walk(os.path.join(root, top)):
        ds[:] = sorted(x for x in ds if os.path.relpath(os.path.join(d, x), root) not in skip and not x.startswith('.'))
        out += [os.path.relpath(os.path.join(d, f), root) for f in sorted(fs) if not f.startswith('.')]
    return out


def music_bundles(root):
    found = []
    for f in os.listdir(root):
        m = MUSIC.match(f)
        if m: found.append((int(m.group(1)), f))
    return [f for _, f in sorted(found)]


def scan(path):
    """(name -> size, byte offset where the end-of-archive marker starts) for one bundle."""
    have, end = {}, 0
    with tarfile.open(path, 'r:') as tf:
        for m in tf:
            if m.isfile(): have[key(m.name)] = m.size
            end = m.offset_data + (m.size + 511) // 512 * 512
    return have, end


def size_of(root, rel):
    try: return os.path.getsize(os.path.join(root, rel))
    except OSError: return -1


def pack(root, names, files, seed=None, log=print):
    """Write files into tars named by the names iterator.
    seed=(path, nbytes): copy the first nbytes of an existing bundle first (to add songs to it).
    Writes go to hidden .tmp files that replace the real names only after everything succeeded."""
    done, fh, pos = [], None, 0

    def start():
        nonlocal fh, pos
        final = os.path.join(root, next(names)); tmp = os.path.join(root, '.' + os.path.basename(final) + '.tmp')
        fh = open(tmp, 'wb'); pos = 0; done.append((final, tmp)); log('writing ' + os.path.basename(final))

    def close():
        fh.write(b'\0' * 1024); fh.close()

    try:
        if seed:
            start()
            with open(seed[0], 'rb') as src:
                left = seed[1]
                while left > 0:
                    b = src.read(min(CHUNK, left))
                    if not b: raise IOError('bundle shorter than expected: ' + seed[0])
                    fh.write(b); left -= len(b)
            pos = fh.tell()
        for rel in files:
            fp = os.path.join(root, rel)
            try:
                size = os.path.getsize(fp); src = open(fp, 'rb')
            except OSError:
                log('  skipped (unreadable): ' + rel); continue
            if fh is None or (pos and pos + size + 4096 > LIMIT):
                if fh: close()
                start()
            info = tarfile.TarInfo(key(rel)); info.size = size; info.mtime = int(os.path.getmtime(fp)); info.mode = 0o644
            fh.write(info.tobuf(tarfile.PAX_FORMAT, 'utf-8', 'surrogateescape'))
            with src:
                left = size
                while left > 0:
                    b = src.read(min(CHUNK, left))
                    if not b: raise IOError('file changed while packing: ' + rel)
                    fh.write(b); left -= len(b)
            if size % 512: fh.write(b'\0' * (512 - size % 512))
            pos = fh.tell()
        if fh: close()
    except BaseException:
        if fh and not fh.closed: fh.close()
        for _, tmp in done:
            try: os.remove(tmp)
            except OSError: pass
        raise
    for final, tmp in done:
        if os.path.exists(final): os.remove(final)
        os.rename(tmp, final)
    return [f for f, _ in done]


def update(root, rebuild=False, log=print):
    """Bring the bundles on a rekordbox USB up to date. Returns a summary dict."""
    root = os.path.abspath(root)
    if not os.path.isdir(os.path.join(root, 'PIONEER')):
        raise SystemExit('PIONEER folder not found in ' + root + ' (choose the top folder of the rekordbox USB)')
    for f in os.listdir(root):                       # leftovers of an interrupted run
        if f.startswith('.dj') and f.endswith('.tar.tmp'):
            try: os.remove(os.path.join(root, f))
            except OSError: pass

    pack(root, iter(['dj1_rekordbox.tar']), walk(root, 'PIONEER', ('PIONEER/Artwork',)), log=log)
    old = music_bundles(root)
    songs = walk(root, 'Contents')
    res = {'songs': len(songs), 'added': 0, 'changed': 0, 'bundles': []}

    if rebuild or not old:
        made = pack(root, ('dj%d_music.tar' % n for n in range(2, 100)), songs, log=log)
        for f in old:
            p = os.path.join(root, f)
            if p not in made and os.path.exists(p): os.remove(p)
        res.update(added=len(songs), bundles=['dj1_rekordbox.tar'] + [os.path.basename(p) for p in made])
        return res

    have, ends = {}, {}
    for b in old:
        try:
            h, ends[b] = scan(os.path.join(root, b)); have.update(h)
        except (tarfile.TarError, OSError) as e:
            log('  could not read %s - %s (its songs will be packed again)' % (b, e))
    todo = [f for f in songs if have.get(key(f)) != size_of(root, f)]
    res['changed'] = sum(1 for f in todo if key(f) in have)
    res['added'] = len(todo) - res['changed']
    if todo:
        last = old[-1]; lastp = os.path.join(root, last); n = int(MUSIC.match(last).group(1))
        need = sum(max(0, size_of(root, f)) + 1024 for f in todo)
        free = shutil.disk_usage(root).free
        seed = None
        if last in ends and ends[last] < MERGE_UNDER and ends[last] + need < LIMIT and free > ends[last] + need + 50_000_000:
            seed = (lastp, ends[last])
        if free < need + 50_000_000 and not seed:
            raise SystemExit('not enough free space on the USB (%.1f GB needed)' % (need / 1e9))
        names = iter(([last] if seed else []) + ['dj%d_music.tar' % k for k in range(n + 1, 100)])
        pack(root, names, todo, seed=seed, log=log)
    res['bundles'] = ['dj1_rekordbox.tar'] + music_bundles(root)
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    if not args:
        print(__doc__); sys.exit(1)
    r = update(args[0], rebuild='--rebuild' in flags)
    print('%d new and %d changed song file(s) packed.' % (r['added'], r['changed']))
    print('done. On the TV open: ' + ', '.join(r['bundles']))


if __name__ == '__main__':
    main()
