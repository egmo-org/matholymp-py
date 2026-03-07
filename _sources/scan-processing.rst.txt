.. Documentation of matholymp scan processing.
   Copyright 2026 Joseph Samuel Myers.

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation; either version 3 of the
   License, or (at your option) any later version.

   This program is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see
   <https://www.gnu.org/licenses/>.

   Additional permission under GNU GPL version 3 section 7:

   If you modify this program, or any covered work, by linking or
   combining it with the OpenSSL project's OpenSSL library (or a
   modified version of that library), containing parts covered by the
   terms of the OpenSSL or SSLeay licenses, the licensors of this
   program grant you additional permission to convey the resulting
   work.  Corresponding Source for a non-source form of such a
   combination shall include the source code for the parts of OpenSSL
   used as well as that of the covered work.

.. _scan-processing:

Scan processing
===============

Matholymp has some support for processing scans of contestant scripts,
using barcoded cover sheets to support automatically splitting up a
PDF with scans of multiple scripts.

Matholymp provides a script :command:`mo-process-script-scans` to do
this processing.  It expects to be run from a directory containing a
file :file:`scans.cfg` with associated configuration information.  The
:file:`examples/scan-processing/` directory in the matholymp source
distribution includes a version of :download:`scans.cfg
<../examples/scan-processing/scans.cfg>` that may be used as a basis
for configuring this.  The other arguments are the names of
multi-script PDFs to process; :command:`mo-process-script-scans`
creates a corresponding log file for each of those files with ``.log``
appended to its name.  Alternatively, if it is run with the `--watch`
option, the other argument is the name of a directory to watch for new
multi-script PDFs having appeared; this is intended to be used with
the `db/queue_scan` subdirectory of the registration system directory,
and the PDFs must be complete before they appear in the named
directory with a `.pdf` filename suffix.

The file pointed to by ``cover_sheet_key_file`` should exist before
this command is run, with the same 20 bytes of random data (generated
afresh for each year's event) as in the file used in document
generation to generate the cover sheets.  The file pointed to by
``password_file`` should also exist, containing the password for the
registration system account (with the ``Scan`` role) to be used to
upload scripts.

Symlinks to individual uploaded scans are automatically created in
`db/scans` in the registration system directory.  The contents of this
directory can be made available to coordinators through a web server
to provide them with access to scans without needing a privileged
registration system account.

The process for uploading the PDFs with scans of multiple scripts
depends on the scanning process and systems, but an example script (in
which configuration settings need to be inserted) that uses the REST
interface for such uploads is :download:`watch-upload.py
<../examples/scan-processing/watch-upload.py>`.  A simpler version,
that only uploads PDFs from a given directory in which all required
PDFs exist at startup, without watching for new scans to appear, is
:download:`upload.py <../examples/scan-processing/upload.py>`.
