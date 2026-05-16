# SYLION v5.9.0 — Third-Party Licenses

Ten plik zawiera informacje o licencjach zewnętrznych zależności używanych przez SYLION.  
This file lists the licenses of third-party dependencies used by SYLION.

Źródło / Source: `requirements-lock.txt` (pinned, Python ≥3.10,<3.13)  
Data / Date: 2026-04-19

---

## Podsumowanie licencji / License Summary

| Pakiet | Wersja (locked) | Licencja | Typ |
|--------|-----------------|----------|-----|
| fastapi | 0.115.12 | MIT | Permissive |
| uvicorn | 0.34.2 | BSD-3-Clause | Permissive |
| starlette | 0.46.2 | BSD-3-Clause | Permissive |
| pydantic | 2.11.1 | MIT | Permissive |
| pydantic-core | 2.33.0 | MIT | Permissive |
| argon2-cffi | 23.1.0 | MIT | Permissive |
| argon2-cffi-bindings | 21.2.0 | MIT | Permissive |
| aiofiles | 24.1.0 | Apache-2.0 | Permissive |
| python-multipart | 0.0.20 | Apache-2.0 | Permissive |
| pypdf | 5.4.0 | BSD-3-Clause | Permissive |
| python-docx | 1.1.2 | MIT | Permissive |
| python-dotenv | 1.1.0 | BSD-3-Clause | Permissive |
| PyYAML | 6.0.2 | MIT | Permissive |
| httpx | 0.28.1 | BSD-3-Clause | Permissive |
| anyio | 4.9.0 | MIT | Permissive |
| litellm | 1.67.4.post1 | MIT | Permissive |
| numpy | 1.26.4 | BSD-3-Clause (+0BSD, MIT, Zlib, CC0-1.0) | Permissive |
| rich | 14.0.0 | MIT | Permissive |
| watchdog | 6.0.0 | Apache-2.0 | Permissive |
| typing-extensions | 4.13.2 | PSF-2.0 | Permissive |
| sniffio | 1.3.1 | MIT OR Apache-2.0 | Permissive |
| certifi | 2025.1.31 | MPL-2.0 | Weak copyleft (file-level) |
| idna | 3.10 | BSD-3-Clause | Permissive |
| pytest | 8.3.4 | MIT | Permissive (dev-only) |

**Brak zależności GPL, AGPL, LGPL, EUPL.**  
Jedyny słaby copyleft: `certifi` (MPL-2.0) — nie infekuje kodu SYLION.

---

## MIT License

Stosowany przez: fastapi, pydantic, pydantic-core, argon2-cffi, argon2-cffi-bindings,
python-docx, PyYAML, anyio, litellm, rich, sniffio (or Apache-2.0), pytest.

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Pełne kopie licencji i copyright notices poszczególnych pakietów dostępne na PyPI:
- FastAPI: https://github.com/fastapi/fastapi/blob/master/LICENSE
- Pydantic: https://github.com/pydantic/pydantic/blob/main/LICENSE
- argon2-cffi: https://github.com/hynek/argon2-cffi/blob/main/LICENSE
- python-docx: https://github.com/python-openxml/python-docx/blob/master/LICENSE
- PyYAML: https://github.com/yaml/pyyaml/blob/master/LICENSE
- anyio: https://github.com/agronholm/anyio/blob/master/LICENSE
- litellm: https://github.com/BerriAI/litellm/blob/main/LICENSE
- rich: https://github.com/Textualize/rich/blob/master/LICENSE
- pytest: https://github.com/pytest-dev/pytest/blob/main/LICENSE

---

## BSD 3-Clause License

Stosowany przez: uvicorn, starlette, pypdf, python-dotenv, httpx, numpy, idna.

```
BSD 3-Clause License

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### Copyright notices BSD-3-Clause

```
uvicorn        Copyright (c) 2017-present, Tom Christie
starlette      Copyright (c) 2018-present, Encode OSS Ltd.
pypdf          Copyright (c) 2006-2024, pypdf contributors
python-dotenv  Copyright (c) 2014, Saurabh Kumar (python-dotenv)
httpx          Copyright (c) 2019-present, Encode OSS Ltd.
numpy          Copyright (c) 2005-2024, NumPy Developers;
               Portions Copyright (c) 2001, Travis Oliphant
idna           Copyright (c) 2013-2024, Kim Davies and contributors
```

Pełne kopie:
- uvicorn: https://github.com/encode/uvicorn/blob/master/LICENSE.md
- starlette: https://github.com/encode/starlette/blob/master/LICENSE.md
- pypdf: https://github.com/py-pdf/pypdf/blob/main/LICENSE
- python-dotenv: https://github.com/theskumar/python-dotenv/blob/main/LICENSE
- httpx: https://github.com/encode/httpx/blob/master/LICENSE.md
- numpy: https://github.com/numpy/numpy/blob/main/LICENSE.txt
- idna: https://github.com/kjd/idna/blob/master/LICENSE.md

---

## Apache License 2.0

Stosowany przez: aiofiles, python-multipart, watchdog, (sniffio — alternately), (bcrypt — if used).

```
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. [...]

      [Full text available at: https://www.apache.org/licenses/LICENSE-2.0]

   Copyright 2024 aiofiles contributors
   Copyright 2024 python-multipart contributors
   Copyright 2011 Yesudeep Mangalapilly (watchdog)
   Copyright 2024 bcrypt contributors (if applicable)

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```

Pełne kopie:
- aiofiles: https://github.com/Tinche/aiofiles/blob/main/LICENSE
- python-multipart: https://github.com/Kludex/python-multipart/blob/master/LICENSE
- watchdog: https://github.com/gorakhargosh/watchdog/blob/master/LICENSE
- Apache-2.0 full text: https://www.apache.org/licenses/LICENSE-2.0.txt

---

## Mozilla Public License 2.0 (MPL-2.0)

Stosowany przez: certifi (Mozilla CA Bundle).

```
certifi: Copyright (c) 2022, Kenneth Reitz

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
```

Uwaga: MPL-2.0 to licencja słabo copyleft na poziomie pliku. Użycie `certifi`
bez modyfikacji plików certifi nie nakłada żadnych obowiązków na kod SYLION.

Pełna licencja: https://mozilla.org/MPL/2.0/  
Źródło: https://github.com/certifi/python-certifi/blob/master/LICENSE

---

## Python Software Foundation License 2.0 (PSF-2.0)

Stosowany przez: typing-extensions.

```
Copyright (c) 2001-present Python Software Foundation; All Rights Reserved

PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
--------------------------------------------
1. This LICENSE AGREEMENT is between the Python Software Foundation ("PSF"),
   and the Individual or Organization ("Licensee") accessing and otherwise
   using this software ("Python") in source or binary form and its associated
   documentation. [...]

PSF-2.0 full text: https://docs.python.org/3/license.html
```

Pełne kopie:
- typing-extensions: https://github.com/python/typing_extensions/blob/main/LICENSE

---

## SQLite (built-in, no package)

SYLION używa SQLite jako bazy danych. SQLite jest **public domain** — brak obowiązków licencyjnych.

Strona: https://www.sqlite.org/copyright.html

---

*Ten plik został wygenerowany automatycznie przez Legal Re-Audit Council w ramach SYLION v5.9.0.*  
*W przypadku rozbieżności między tym plikiem a oficjalnymi repozytoriami pakietów — pierwszeństwo mają oficjalne repozytoria.*
