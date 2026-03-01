# Implement mo-process-script-scans script.

# Copyright 2026 Joseph Samuel Myers.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see
# <https://www.gnu.org/licenses/>.

# Additional permission under GNU GPL version 3 section 7:

# If you modify this program, or any covered work, by linking or
# combining it with the OpenSSL project's OpenSSL library (or a
# modified version of that library), containing parts covered by the
# terms of the OpenSSL or SSLeay licenses, the licensors of this
# program grant you additional permission to convey the resulting
# work.  Corresponding Source for a non-source form of such a
# combination shall include the source code for the parts of OpenSSL
# used as well as that of the covered work.

"""
The mo-process-script-scans script processes scans of multiple scripts
with barcoded cover sheets and uploads the individual script scans to
the registration system.  It should be run in a directory containing
'scans.cfg' with configuration settings.
"""

import argparse
import base64
import concurrent.futures
import hmac
import io
import os
import os.path
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree

from pypdf import PdfReader, PdfWriter
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import matholymp
from matholymp.fileutil import read_config
from matholymp.roundupreg.rest import RegSystemRest

__all__ = ['main']


def _read_scans_config(top_directory):
    cfg_file_name = os.path.join(top_directory, 'scans.cfg')
    cfg_str_keys = ['base_url', 'user', 'password_file',
                    'cover_sheet_key_file']
    cfg_int_keys = ['num_attempts', 'resolution', 'threshold']
    cfg_int_none_keys = []
    cfg_bool_keys = []
    cfg_data = read_config(cfg_file_name, 'matholymp.scans',
                           cfg_str_keys, cfg_int_keys, cfg_int_none_keys,
                           cfg_bool_keys)
    cfg_data['cover_sheet_key_file'] = os.path.join(
        top_directory, cfg_data['cover_sheet_key_file'])
    with open(cfg_data['cover_sheet_key_file'], 'rb') as key_file:
        cfg_data['cover_sheet_key'] = key_file.read()
    cfg_data['password_file'] = os.path.join(
        top_directory, cfg_data['password_file'])
    with open(cfg_data['password_file'], 'r', encoding='utf-8') as pw_file:
        cfg_data['password'] = pw_file.read().rstrip()
    return cfg_data


def _process_subscan(in_reader, start, end, person_id, d_or_p, scan_num,
                     cfg_data, logfile):
    out = PdfWriter()
    out.append(in_reader, pages=(start, end))
    with io.BytesIO() as out_file:
        out.write(out_file)
        out_bytes = out_file.getvalue()
    if d_or_p == 'P':
        prop = 'script_scan_p%s' % scan_num
    else:
        prop = 'scratch_scan_d%s' % scan_num
    rest = RegSystemRest(
        cfg_data['base_url'], cfg_data['user'], cfg_data['password'], logfile,
        cfg_data['num_attempts'])
    rest.upload_link_file(
        'script',
        {'name': 'scan.pdf',
         'type': 'application/pdf',
         'has_cover_sheet': '1'},
        out_bytes,
        'person',
        person_id,
        prop)


def _run_log(args, logfile, check=True):
    logfile.write('running %s\n' % repr(args))
    results = subprocess.run(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False)
    logfile.write('stdout: %s\nstderr: %s\nresult: %d\n'
                  % (results.stdout.decode('utf-8'),
                     results.stderr.decode('utf-8'),
                     results.returncode))
    if check:
        results.check_returncode()
    return results


def _process_one_scan_main(scan, cfg_data, logfile):
    in_reader = PdfReader(scan)
    num_pages = len(in_reader.pages)
    logfile.write('Processing %s (%d pages)\n' % (scan, num_pages))
    with tempfile.TemporaryDirectory() as tmpdir:
        page_digits = len(str(num_pages))
        scan_ppm_fmt = 'scan-%%0%dd.ppm' % page_digits
        cur_start = None
        cur_data = ()
        for n in range(num_pages):
            _run_log(
                ['pdftoppm', '-scale-to', str(cfg_data['resolution']),
                 '-f', str(n + 1), '-l', str(n + 1), scan,
                 os.path.join(tmpdir, 'scan')],
                logfile)
            scan_ppm = os.path.join(tmpdir, scan_ppm_fmt % (n + 1))
            scan_png = os.path.join(tmpdir, 'scan-%d.png' % (n + 1))
            _run_log(
                ['convert', scan_ppm,
                 '+repage', '-threshold', '%d%%' % cfg_data['threshold'],
                 '-morphology', 'open', 'square:1', scan_png],
                logfile)
            os.remove(scan_ppm)
            results = _run_log(
                ['zbarimg', '-q', '--xml', '-Sdisable', '-Sqrcode.enable',
                 os.path.join(tmpdir, 'scan-%d.png' % (n + 1))],
                logfile,
                check=False)
            os.remove(scan_png)
            this_data = None
            if results.returncode == 4:
                pass
            else:
                results.check_returncode()
                data = xml.etree.ElementTree.fromstring(
                    results.stdout.decode('utf-8')).find(
                        'source/index/symbol/data',
                        namespaces={'': 'http://zbar.sourceforge.net/2008/'
                                    'barcode'}).text
                m = re.fullmatch(r'([0-9]+) ([DP])([0-9]+) (.*)', data)
                if m:
                    mtxt = '%s %s%s' % (m.group(1), m.group(2), m.group(3))
                    mmac = m.group(4)
                    xmac = base64.b32encode(hmac.digest(
                        cfg_data['cover_sheet_key'], mtxt.encode('utf-8'),
                        'sha1')).decode('utf-8')
                    if xmac == mmac:
                        this_data = (m.group(1), m.group(2), m.group(3))
            if this_data is None:
                if cur_start is None:
                    # Missing barcode at start, still try to process
                    # the rest.
                    logfile.write('missing barcode at start\n')
                continue
            if cur_start is not None:
                _process_subscan(in_reader, cur_start, n, cur_data[0],
                                 cur_data[1], cur_data[2], cfg_data, logfile)
            cur_start = n
            cur_data = this_data
        if cur_start is not None:
            _process_subscan(in_reader, cur_start, num_pages, cur_data[0],
                             cur_data[1], cur_data[2], cfg_data, logfile)


def _process_one_scan(scan, cfg_data):
    with open(scan + '.log', 'w', encoding='utf-8') as logfile:
        try:
            _process_one_scan_main(scan, cfg_data, logfile)
        except Exception as e:
            logfile.write('exception raised processing %s: %s\n'
                          % (scan, str(e)))
            raise


def _maybe_process_scan_from_watch(executor, cfg_data, path):
    if not os.access(path, os.F_OK, follow_symlinks=False):
        # File deletion or renaming event.
        return
    if os.access(path + '.log', os.F_OK):
        # Already processed or being processed.
        return
    try:
        with open(path + '.lock', 'x', encoding='utf-8'):
            pass
    except FileExistsError:
        # Another thread has claimed this file.
        return
    while True:
        # Because Roundup reactors run because files have been renamed
        # to their final names, a symlink to an uploaded scan is
        # created to what will be the final path but does not yet
        # exist at that point.
        if os.access(path, os.F_OK, follow_symlinks=True):
            break
        time.sleep(0.1)
    executor.submit(_process_one_scan, path, cfg_data)


class _ScanEventHandler(FileSystemEventHandler):

    def __init__(self, executor, cfg_data):
        self.mo_executor = executor
        self.mo_cfg_data = cfg_data
        super().__init__()

    def on_any_event(self, event):
        if hasattr(event, 'dest_path') and event.dest_path:
            path = event.dest_path
        else:
            path = event.src_path
        if path and path.endswith('.pdf'):
            _maybe_process_scan_from_watch(
                self.mo_executor, self.mo_cfg_data, path)


def _do_watch(executor, cfg_data, dir_to_watch):
    handler = _ScanEventHandler(executor, cfg_data)
    observer = Observer()
    observer.schedule(handler, dir_to_watch)
    observer.start()
    # Files already present at startup do not generate events, so make
    # sure to handle them; the use of locks ensures a file created
    # just after the watch starts is only processed once.
    for f in os.scandir(dir_to_watch):
        _maybe_process_scan_from_watch(executor, cfg_data, f.path)
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()


def main():
    """Main program for mo-process-script-scans."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + matholymp.__version__)
    parser.add_argument('--watch', action='store_true',
                        help='watch directory for new PDFs')
    parser.add_argument('files', nargs='*',
                        help='input directory or list of input PDFs')
    args = vars(parser.parse_args())
    if args['watch'] and len(args['files']) != 1:
        raise ValueError('--watch must be used with a single directory')

    top_directory = os.getcwd()
    cfg_data = _read_scans_config(top_directory)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        if args['watch']:
            _do_watch(executor, cfg_data, args['files'][0])
        else:
            for scan in args['files']:
                executor.submit(_process_one_scan, scan, cfg_data)
