# REST support for Roundup registration system for matholymp package.

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
This module provides support for REST API interaction with the Roundup
registration system.
"""

import json

import requests

__all__ = ['RegSystemRest']


class RegSystemRest:

    """
    A RegSystemRest handles REST interaction with the registration system.
    """

    def __init__(self, base_url, user, password, logfile=None,
                 num_attempts=10):
        """Initialise a RegSystemRest."""
        self._base_url = base_url.rstrip('/')
        self._user = user
        self._password = password
        self._logfile = logfile
        self._num_attempts = num_attempts

    def get_auth(self):
        """Return authentication data to use."""
        return (self._user, self._password)

    def get_headers(self, is_json=False):
        """Return request headers to use."""
        ret = {'X-Requested-With': 'rest',
               'Referer': self._base_url,
               'Origin': self._base_url,
               'Accept': 'application/json'}
        if is_json:
            ret['Content-Type'] = 'application/json'
        return ret

    def rest_url_class(self, cls):
        """Return the REST URL for a class of item."""
        return '%s/rest/data/%s' % (self._base_url, cls)

    def rest_url_item(self, cls, item):
        """Return the REST URL for an individual item."""
        return '%s/%s' % (self.rest_url_class(cls), item)

    def maybe_log(self, text):
        """Log some text if a log file is in use."""
        if self._logfile:
            self._logfile.write(text)

    def create(self, cls, data, files=None):
        """Create an item using the REST API."""
        self.maybe_log('creating %s: %s\n' % (cls, repr(data)))
        r = requests.post(  # pylint: disable=missing-timeout
            self.rest_url_class(cls),
            auth=self.get_auth(),
            headers=self.get_headers(),
            data=data,
            files=files)
        self.maybe_log('results: %s\n' % r.text)
        r.raise_for_status()
        return r.json()['data']['id']

    def get(self, cls, item):
        """Get the current data for an item using the REST API."""
        self.maybe_log('getting %s %s\n' % (cls, item))
        r = requests.get(  # pylint: disable=missing-timeout
            self.rest_url_item(cls, item),
            auth=self.get_auth(),
            headers=self.get_headers())
        self.maybe_log('results: %s\n' % r.text)
        r.raise_for_status()
        return r.json()['data']

    def set(self, cls, item, prop, value):
        """Set a property on an item using the REST API."""
        for _ in range(self._num_attempts):
            etag = self.get(cls, item)['@etag']
            self.maybe_log('trying to set %s %s %s = %s\n'
                           % (cls, item, prop, repr(value)))
            r = requests.put(  # pylint: disable=missing-timeout
                self.rest_url_item(cls, item),
                auth=self.get_auth(),
                headers=self.get_headers(is_json=True),
                data=json.dumps({prop: value, '@etag': etag}))
            self.maybe_log('results: %s\n' % r.text)
            rjson = r.json()
            if ('error' in rjson and (
                    'If-Match is missing or does not match'
                    in rjson['error']['msg'])):
                # Possible race condition with other edits, retry.
                continue
            r.raise_for_status()
            break

    def upload_link_file(self, file_class, file_props, file_content,
                         cls, item, prop):
        """Upload a file and link to it in another item."""
        file_item = self.create(
            file_class, file_props, files={'content': file_content})
        self.set(cls, item, prop, file_item)
