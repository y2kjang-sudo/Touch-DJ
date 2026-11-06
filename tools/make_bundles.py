#!/usr/bin/env python3
"""Pack a rekordbox USB into bundles the StanbyMe browser can open.

The TV browser can only pick single files, and FAT32 USB sticks cannot hold
files over 4 GB, so the USB is packed into plain (uncompressed) tar files:

  dj1_rekordbox.tar   PIONEER folder without artwork (playlists, cues, grids)
  dj2_music.tar ...   Contents folder, split so each file stays under 3.8 GB

After a re-export that only changed playlists or cues, run with --rekordbox-only.

Usage:  python3 make_bundles.py /Volumes/USB [--rekordbox-only]
"""
import os, sys, tarfile

LIMIT = 3_800_000_000

def walk(root, top, skip=()):
    out = []
    for d, ds, fs in os.walk(os.path.join(root, top)):
        ds[:] = sorted(x for x in ds if os.path.relpath(os.path.join(d, x), root) not in skip)
        out += [os.path.relpath(os.path.join(d, f), root) for f in sorted(fs) if not f.startswith('._')]
    return out

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
    if not args:
        print(__doc__); sys.exit(1)
    root = os.path.abspath(args[0])
    if not os.path.isdir(os.path.join(root, 'PIONEER')):
        sys.exit('PIONEER folder not found in ' + root + ' (choose the top folder of the rekordbox USB)')
    write(root, iter(['dj1_rekordbox.tar']), walk(root, 'PIONEER', ('PIONEER/Artwork',)))
    if '--rekordbox-only' not in sys.argv:
        old = [f for f in os.listdir(root) if f.startswith('dj') and f.endswith('_music.tar')]
        for f in old: os.remove(os.path.join(root, f))
        write(root, ('dj%d_music.tar' % n for n in range(2, 100)), walk(root, 'Contents'))
    print('done. On the TV: open dj1_rekordbox.tar first, then add each dj*_music.tar.')

if __name__ == '__main__':
    main()
