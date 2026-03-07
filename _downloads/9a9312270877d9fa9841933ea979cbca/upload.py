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
Take a directory for PDFs with scans of multiple scripts with barcoded
cover sheets and upload them to the registration system.
"""

import os

import requests


# Configuration settings.
base_url = 'INSERT-HERE'
user = 'INSERT-HERE'
password = 'INSERT-HERE'


def process_one_scan(scan):
    print('uploading %s' % scan)
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


dir_to_upload = input('Directory with scans: ')

for dirpath, dirnames, filenames in os.walk(dir_to_upload):
    for f in filenames:
        if f.lower().endswith('.pdf'):
            process_one_scan(os.path.join(dirpath, f))
