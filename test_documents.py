"""Real document extraction and validation checks."""
import base64
import io
import unittest
import zipfile
from unittest.mock import patch
import server


def docx(text='Word attachment hello'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()


def pdf(text='PDF attachment hello'):
    stream = ('BT /F1 12 Tf 72 720 Td (' + text + ') Tj ET').encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>', b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
    result = b'%PDF-1.4\n'
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += str(i).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    xref = len(result)
    result += b'xref\n0 6\n0000000000 65535 f \n'
    result += b''.join(('%010d 00000 n \n' % offset).encode() for offset in offsets[1:])
    return result + b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(xref).encode() + b'\n%%EOF\n'


def payload(name, raw):
    return {'name': name, 'data': base64.b64encode(raw).decode()}


class DocumentTests(unittest.TestCase):
    def test_real_documents(self):
        for name, raw, expected in [('file.pdf', pdf(), 'PDF attachment hello'), ('file.docx', docx('Hej æøå'), 'Hej æøå')]:
            self.assertIn(expected, server.extract_document(payload(name, raw))['text'])

    def test_invalid_empty_and_large(self):
        for name, raw in [('bad.pdf', b'%PDF-broken'), ('bad.docx', b'bad'), ('empty.docx', docx('')), ('scan.pdf', pdf('')), ('long.docx', docx('x' * 12001)), ('old.doc', b'old'), ('huge.pdf', b'x' * 3000001)]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                server.extract_document(payload(name, raw))

    def test_missing_pdf_reader(self):
        with patch.object(server.shutil, 'which', return_value=None), self.assertRaisesRegex(ValueError, 'pdftotext'):
            server.extract_document(payload('file.pdf', pdf()))

class DocumentBrowserTests(unittest.TestCase):
    def test_drop_documents_through_server(self):
        import json
        import shutil
        import subprocess
        import tempfile
        import threading
        from pathlib import Path
        from http.server import ThreadingHTTPServer
        chrome = shutil.which('google-chrome') or shutil.which('chromium')
        if not chrome:
            self.skipTest('Chrome/Chromium required')
        fixtures = json.dumps([payload('letter.docx', docx()), payload('letter.pdf', pdf())])
        script = '''(async()=>{
          const check=(ok,msg)=>{if(!ok)throw Error(msg);};
          const denied=await fetch('/api/attachments/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
          check(denied.status===403,'document endpoint requires token');
          await status();
          const dt=new DataTransfer();
          for(const f of FIXTURES)dt.items.add(new File([Uint8Array.from(atob(f.data),c=>c.charCodeAt(0))],f.name));
          window.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}));
          for(let i=0;i<1000&&readingFiles;i++)await new Promise(r=>setTimeout(r,10));
          check(document.querySelectorAll('.attachment-item').length===2,'document previews');
          await $('form').onsubmit({preventDefault(){}});
          check(document.querySelectorAll('.attachment-item').length===2,'failed send retains documents');
          await $('form').onsubmit({preventDefault(){}});
          check(!document.querySelector('.attachment-item'),'successful send clears documents');
          check($('messages').textContent.includes('EXTRACTED_OK'),'both document contents reached chat');
          document.body.innerHTML='<pre id="test-result">PASS document drop and send</pre>';
        })().catch(e=>{document.body.innerHTML='<pre id="test-result">FAIL '+e.message+'</pre>';});'''.replace('FIXTURES', fixtures)
        class TestHandler(server.Handler):
            def local_host(self):
                return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)

            def do_GET(self):
                if self.path == '/test':
                    page = (server.ROOT / 'index.html').read_text().replace('</body>', '<script defer src="/document-test.js"></script></body>')
                    return self.send(200, page, 'text/html')
                if self.path == '/document-test.js':
                    return self.send(200, script, 'text/javascript')
                if self.path == '/api/status':
                    return self.send(200, {'token': server.TOKEN, 'ready': True, 'model': 'test'})
                return super().do_GET()

        attempts = []
        def chat(data):
            attempts.append(data)
            if len(attempts) == 1:
                raise ValueError('Simuleret afsendelsesfejl')
            content = data['messages'][-1]['content']
            self.assertIn('Word attachment hello', content)
            self.assertIn('PDF attachment hello', content)
            return {'answer': 'EXTRACTED_OK'}

        httpd = ThreadingHTTPServer(('127.0.0.1', 0), TestHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder, patch.object(server, 'chat', side_effect=chat):
                result = subprocess.run([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--no-first-run', '--user-data-dir=' + folder, '--virtual-time-budget=20000', '--dump-dom', 'http://127.0.0.1:%s/test' % httpd.server_port], capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('<pre id="test-result">PASS document drop and send</pre>', result.stdout, result.stdout)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
