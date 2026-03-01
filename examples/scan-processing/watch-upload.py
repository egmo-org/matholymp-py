#! /usr/bin/env python3

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
Watch a directory for PDFs with scans of multiple scripts with
barcoded cover sheets and upload them to the registration system.
"""

import concurrent.futures
import os
import time

import requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


# Configuration settings.
base_url = 'INSERT-HERE'
user = 'INSERT-HERE'
password = 'INSERT-HERE'


def process_one_scan(scan):
    # The file may still be being written.
    while True:
        statinfo = os.stat(scan)
        if statinfo.st_mtime < time.time() - 5 and statinfo.st_size > 0:
            break
        time.sleep(0.1)
    with open(scan + '.log', 'w', encoding='utf-8') as log:
        base_rest_url = base_url + '/rest/data/'
        r = requests.post(
            base_rest_url + 'queue_scan',
            auth=(user, password),
            headers={'X-Requested-With': 'rest',
                     'Referer': base_url,
                     'Origin': base_url,
                     'Accept': 'application/json'},
            data={'name': 'scan.pdf',
                  'type': 'application/pdf'},
            files={'content': open(scan, 'rb').read()})
        log.write(r.text)
        r.raise_for_status()


def maybe_process_scan_from_watch(executor, path):
    if not os.access(path, os.F_OK):
        # File deletion or renaming event.
        return
    if os.access(path + '.lock', os.F_OK):
        # Already processed or being processed.
        return
    try:
        with open(path + '.lock', 'x', encoding='utf-8'):
            pass
    except FileExistsError:
        # Another thread has claimed this file.
        return
    executor.submit(process_one_scan, path)


class QueueScanEventHandler(FileSystemEventHandler):

    def __init__(self, executor):
        self.mo_executor = executor
        super().__init__()

    def on_any_event(self, event):
        if hasattr(event, 'dest_path') and event.dest_path:
            path = event.dest_path
        else:
            path = event.src_path
        if path and path.lower().endswith('.pdf'):
            maybe_process_scan_from_watch(
                self.mo_executor, path)


dir_to_watch = input('Directory to watch: ')

with concurrent.futures.ThreadPoolExecutor() as executor:
    handler = QueueScanEventHandler(executor)
    observer = Observer()
    observer.schedule(handler, dir_to_watch)
    observer.start()
    # Files already present at startup do not generate events, so make
    # sure to handle them; the use of locks ensures a file created
    # just after the watch starts is only processed once.
    for dirpath, dirnames, filenames in os.walk(dir_to_watch):
        for f in filenames:
            if f.lower().endswith('.pdf'):
                maybe_process_scan_from_watch(executor,
                                              os.path.join(dirpath, f))
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()
