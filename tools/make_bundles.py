#!/usr/bin/env python3
"""Pack a rekordbox USB into bundles the StanbyMe browser can open.

The TV browser can only pick single files, and FAT32 USB sticks cannot hold
files over 4 GB, so the USB is packed into plain (uncompressed) tar files:

  dj1_rekordbox.tar   PIONEER folder without artwork (playlists, cues, grids)
  dj2_music.tar ...   Contents folder, split so each file stays under 3.8 GB

Usage:
  python3 make_bundles.py /Volumes/USB             build everything from scratch
  python3 make_bundles.py /Volumes/USB --update    after a new rekordbox export: rebuild
                                                   dj1 and pack only songs that are not in
                                                   any dj*_music.tar yet (new file djN_music.tar)
  python3 make_bundles.py /Volumes/USB --rekordbox-only
                                                   only playlists/cues changed, no new songs
"""
import os, re, sys, tarfile, unicodedata

LIMIT = 3_800_000_000
MUSIC = re.compile(r'^dj(\d+)_music\.tar$')


def key(path):
    # macOS stores Hangul decomposed, rekordbox composed; compare in one form
    return unicodedata.normalize('NFC', path)


def walk(root, top, skip=()):
    out = []
    for d, ds, fs in os.walk(os.path.join(root, top)):
        ds[:] = sorted(x for x in ds if os.path.relpath(os.path.join(d, x), root) not in skip)
        out += [os.path.relpath(os.path.join(d, f), root) for f in sorted(fs) if not f.startswith('._')]
    return out


def music_bundles(root):
    found = []
    for f in os.listdir(root):
        m = MUSIC.match(f)
        if m: found.append((int(m.group(1)), f))
    return [f for _, f in sorted(found)]


def packed(root, bundles):
    """name -> size for every file already inside the music bundles."""
    have = {}
    for b in bundles:
        try:
            with tarfile.open(os.path.join(root, b), 'r:') as tf:
                for m in tf:
                    if m.isfile(): have[key(m.name)] = m.size
        except (tarfile.TarError, OSError) as e:
            print('  could not read', b, '-', e, '(its songs will be packed again)')
    return have


def write(root, names, files):
    """Write files into one or more tars named by the names iterator; returns the paths written."""
    written, fh, pos = [], None, 0
    for rel in files:
        fp = os.path.join(root, rel)
        try:
            size = os.path.getsize(fp); src = open(fp, 'rb')
        except OSError:
            print('  skipped (unreadable):', rel); continue
        if fh is None or (pos and pos + size + 4096 > LIMIT):
            if fh: fh.write(b'\0' * 1024); fh.close()
            path = os.path.join(root, next(names)); fh = open(path, 'wb'); pos = 0; written.append(path)
            print('writing', os.path.basename(path))
        info = tarfile.TarInfo(rel); info.size = size; info.mtime = int(os.path.getmtime(fp)); info.mode = 0o644
        fh.write(info.tobuf(tarfile.PAX_FORMAT, 'utf-8', 'surrogateescape'))
        with src:
            while True:
                b = src.read(1 << 22)
                if not b: break
                fh.write(b)
        if size % 512: fh.write(b'\0' * (512 - size % 512))
        pos = fh.tell()
    if fh: fh.write(b'\0' * 1024); fh.close()
    return written


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    if not args:
        print(__doc__); sys.exit(1)
    root = os.path.abspath(args[0])
    if not os.path.isdir(os.path.join(root, 'PIONEER')):
        sys.exit('PIONEER folder not found in ' + root + ' (choose the top folder of the rekordbox USB)')

    write(root, iter(['dj1_rekordbox.tar']), walk(root, 'PIONEER', ('PIONEER/Artwork',)))
    if '--rekordbox-only' in flags:
        print('done. Open dj1_rekordbox.tar first, then the dj*_music.tar files.'); return

    old = music_bundles(root)
    songs = walk(root, 'Contents')
    if '--update' in flags and old:
        have = packed(root, old)
        new = [f for f in songs if key(f) not in have]
        changed = [f for f in songs if key(f) in have and have[key(f)] != os.path.getsize(os.path.join(root, f))]
        if changed:
            print(len(changed), 'song file(s) changed since they were packed; run without --update to rebuild everything:')
            for f in changed[:10]: print('  ', f)
        if not new:
            print('no new songs. done. Open dj1_rekordbox.tar, then', ', '.join(old))
            return
        start = max(int(MUSIC.match(f).group(1)) for f in old) + 1
        made = write(root, ('dj%d_music.tar' % n for n in range(start, 100)), new)
        print('%d new song file(s) packed into %s' % (len(new), ', '.join(os.path.basename(p) for p in made)))
        print('done. Open dj1_rekordbox.tar, then', ', '.join(old + [os.path.basename(p) for p in made]))
        return

    for f in old: os.remove(os.path.join(root, f))
    made = write(root, ('dj%d_music.tar' % n for n in range(2, 100)), songs)
    print('done. Open dj1_rekordbox.tar, then', ', '.join(os.path.basename(p) for p in made))


if __name__ == '__main__':
    main()
