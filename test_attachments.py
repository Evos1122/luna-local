"""Browser integration checks using Chrome; no Ollama request is sent."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHROME = shutil.which('google-chrome') or shutil.which('chromium')


class AttachmentBrowserTests(unittest.TestCase):
    @unittest.skipUnless(CHROME, 'Chrome/Chromium is required')
    def test_attachment_workflow(self):
        mock = """window.fetch=async(path,options)=>{
          if(path==='/api/status')return {json:async()=>({token:'test',ready:true,model:'test'})};
          if(path==='/api/chat'){
            window.lastBody=JSON.parse(options.body);
            return {ok:!window.failChat,json:async()=>window.failChat?{error:'test failure'}:{answer:'Test answer'}};
          }throw Error(path);
        };"""
        html = (ROOT / 'index.html').read_text().replace('<script defer src="/app.js"></script>', '')
        html = html.replace('<link rel="stylesheet" href="/style.css">', '')
        scripts = [mock, (ROOT / 'app.js').read_text(), (ROOT / 'test_attachments.js').read_text()]
        html = html.replace('</body>', ''.join('<script>' + s + '</script>' for s in scripts) + '</body>')
        with tempfile.TemporaryDirectory(prefix='luna-browser-') as folder:
            page = Path(folder) / 'test.html'
            page.write_text(html)
            result = subprocess.run([
                CHROME, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                '--no-first-run', '--user-data-dir=' + folder + '/profile',
                '--virtual-time-budget=10000', '--dump-dom', page.as_uri(),
            ], capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('<pre id="test-result">PASS ', result.stdout, result.stdout)


if __name__ == '__main__':
    unittest.main()
