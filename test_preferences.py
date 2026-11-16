"""Browser regression: checkbox choices survive new chats and real reloads."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHROME = shutil.which('google-chrome') or shutil.which('chromium')


class PreferenceBrowserTests(unittest.TestCase):
    @unittest.skipUnless(CHROME, 'Chrome/Chromium is required')
    def test_choices_survive_reload_and_new_chat(self):
        mock = """window.availableConnections={folders:true,github:true,mcp:true};
        window.fetch=async(path,options)=>{
          if(path==='/api/status')return {json:async()=>({token:'test',ready:true,model:'test',connections:window.availableConnections})};
          if(path==='/api/settings')return {ok:true,json:async()=>({github:{token:'',user:''},mcp:[],folders:[],model:'test'})};
          if(path==='/api/chat'){window.lastBody=JSON.parse(options.body);return {ok:true,json:async()=>({answer:'Test'})};}
          throw Error(path);
        };"""
        checks = """(async()=>{
          const ids=['solo','memory','think','agents','tools','edit','web','full','confirm','folders','github','mcp'];
          const check=(ok,msg)=>{if(!ok)throw Error(msg);};
          const phase=Number(sessionStorage.getItem('preference-test-phase')||0);
          await status();
          if(phase===0){
            for(const id of ids){check($(id).checked===(id==='confirm'),'unchanged default: '+id);if(id==='think')$(id).checked=true;else $(id).click();}
            // Gem captures the visible choices, including browser-restored fields without a change event.
            await openSettings();await $('settingsSave').onclick();
            check($('saveHint').textContent.includes('Gemt'),'save button succeeds');
            for(const id of ids)check($(id).checked===(id!=='confirm'),'save preserves '+id);
            $('settingsClose').click();await openSettings();
            for(const id of ids)check($(id).checked===(id!=='confirm'),'reopen settings preserves '+id);
            $('new').click();
            for(const id of ids)check($(id).checked===(id!=='confirm'),'new chat preserves '+id);
            sessionStorage.setItem('preference-test-phase','1');location.reload();return;
          }
          if(phase===1){
            for(const id of ids)check($(id).checked===(id!=='confirm'),'reload preserves '+id);
            $('prompt').value='Test';await $('form').onsubmit({preventDefault(){}});
            for(const id of ids)check(window.lastBody[id]===(id!=='confirm'),'chat uses saved '+id);
            window.availableConnections={};await status();
            check(!$('mcp').checked,'disconnected MCP is inactive');
            $('think').click();await $('settingsSave').onclick();
            window.availableConnections={folders:true,github:true,mcp:true};await status();
            check($('mcp').checked,'MCP choice returns with connection');
            for(const id of ids)if($(id).checked!==(id==='confirm'))$(id).click();
            sessionStorage.setItem('preference-test-phase','2');location.reload();return;
          }
          for(const id of ids)check($(id).checked===(id==='confirm'||(phase===3&&id==='tools')),'off choice persists: '+id);
          document.querySelector('[data-prompt^="List"]').click();
          if(phase===2){sessionStorage.setItem('preference-test-phase','3');location.reload();return;}
          document.body.innerHTML='<pre id="test-result">PASS preferences</pre>';
        })().catch(e=>{document.body.innerHTML='<pre id="test-result">FAIL '+e.message+'</pre>';});"""
        html = (ROOT / 'index.html').read_text().replace('<script defer src="/app.js"></script>', '').replace('<link rel="stylesheet" href="/style.css">', '')
        html = html.replace('</body>', ''.join('<script>'+s+'</script>' for s in [mock, (ROOT/'app.js').read_text(), checks])+'</body>')
        with tempfile.TemporaryDirectory(prefix='luna-preferences-') as folder:
            page = Path(folder) / 'test.html'
            page.write_text(html)
            result = subprocess.run([CHROME, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--no-first-run', '--user-data-dir='+folder+'/profile', '--virtual-time-budget=10000', '--dump-dom', page.as_uri()], capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('<pre id="test-result">PASS preferences</pre>', result.stdout, result.stdout[-2000:])


if __name__ == '__main__':
    unittest.main()
