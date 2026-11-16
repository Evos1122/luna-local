import base64
import http.client
import http.server
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import server

# A minimal MCP server speaking newline-delimited JSON-RPC on stdin/stdout.
FAKE_MCP_SCRIPT = '''
import json, sys
TOOLS = [
    {"name": "echo", "description": "Giver teksten igen",
     "inputSchema": {"type": "object", "properties": {"tekst": {"type": "string"}},
                     "required": ["tekst"]}},
    {"name": "sum", "description": "Lægger to tal sammen",
     "inputSchema": {"type": "object", "properties": {"a": {"type": "number"},
                                                      "b": {"type": "number"}},
                     "required": ["a", "b"]}},
]
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    if not isinstance(msg, dict) or "id" not in msg:
        continue
    method, params, mid = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fake", "version": "1.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        args = params.get("arguments") or {}
        if params.get("name") == "echo":
            text = "Echo: " + str(args.get("tekst"))
        else:
            text = str(args.get("a", 0) + args.get("b", 0))
        result = {"content": [{"type": "text", "text": text}], "isError": False}
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid,
                                     "error": {"code": -32601, "message": method}}) + "\\n")
        sys.stdout.flush()
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\\n")
    sys.stdout.flush()
'''

# A second fake server whose only tool reports the LUNA_TEST environment variable.
FAKE_ENV_MCP_SCRIPT = '''
import json, os, sys
TOOLS = [
    {"name": "hent", "description": "Viser miljøvariabelen LUNA_TEST",
     "inputSchema": {"type": "object", "properties": {}}},
]
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    if not isinstance(msg, dict) or "id" not in msg:
        continue
    method, params, mid = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "env-fake", "version": "1.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": os.environ.get("LUNA_TEST", "(ikke sat)")}],
                  "isError": False}
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid,
                                     "error": {"code": -32601, "message": method}}) + "\\n")
        sys.stdout.flush()
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\\n")
    sys.stdout.flush()
'''


class LunaTests(unittest.TestCase):
    def setUp(self):
        # Every test gets its own settings file, so a real one on disk cannot interfere.
        self._temp = tempfile.TemporaryDirectory()
        self._settings = patch.object(server,'SETTINGS_FILE',Path(self._temp.name)/'settings.json')
        self._settings.start()
        server.MCP_CACHE.clear()
        server.PULL.update({'name':'','running':False,'done':0,'total':0,'error':'','proc':None})

    def tearDown(self):
        self._settings.stop()
        server.MCP_CACHE.clear()
        self._temp.cleanup()

    def test_conversation_and_thinking(self):
        data={'messages':[{'role':'user','content':'Hej'},{'role':'assistant','content':'Hej Lars'},{'role':'user','content':'Husk mit navn'}], 'think':True}
        with patch.object(server,'ollama',return_value={'message':{'content':'Lars','thinking':'Svar på dansk'}}) as model:
            result=server.chat(data)
            self.assertEqual(result['answer'],'Lars')
            self.assertTrue(model.call_args.args[1]['think'])
            self.assertEqual(len(model.call_args.args[1]['messages']),4)

    def test_live_status_hides_thinking_and_reports_tool_use(self):
        events=[]
        def fake_chat(endpoint,payload,on_chunk=None):
            if on_chunk:
                on_chunk({'message':{'thinking':'HEMMELIG_INTERN_TÆNKNING'}})
                on_chunk({'message':{'content':'Hej'}})
            return {'message':{'content':'Hej','thinking':'HEMMELIG_INTERN_TÆNKNING'}}
        with patch.object(server,'ollama',side_effect=fake_chat):
            result=server.chat({'messages':[{'role':'user','content':'Hej'}]},on_event=events.append)
        self.assertEqual(result['answer'],'Hej')
        self.assertTrue(any(e.get('text','').startswith('Modellen arbejder') for e in events))
        self.assertTrue(any(e.get('type')=='delta' and e.get('text')=='Hej' for e in events))
        self.assertNotIn('HEMMELIG_INTERN_TÆNKNING',json.dumps(events,ensure_ascii=False))

        events=[]
        calls=[{'function':{'name':'list_files','arguments':{}}}]
        round_no=[0]
        def fake_tool_chat(endpoint,payload,on_chunk=None):
            round_no[0]+=1
            if round_no[0]==1:
                if on_chunk:on_chunk({'message':{'tool_calls':calls}})
                return {'message':{'content':'','tool_calls':calls}}
            if on_chunk:on_chunk({'message':{'content':'Kontrolleret'}})
            return {'message':{'content':'Kontrolleret'}}
        with patch.object(server,'ollama',side_effect=fake_tool_chat), patch.object(server,'run_tool',return_value='filoversigt'):
            result=server.chat({'messages':[{'role':'user','content':'List filer'}],'tools':True},
                               on_event=events.append)
        self.assertEqual(result['tools'][0]['name'],'list_files')
        self.assertTrue(any(e.get('text')=='Modellen forbereder et værktøjskald…' for e in events))
        self.assertTrue(any(e.get('text','').startswith('Udfører:') for e in events))

    def test_raw_tool_call_recovery_preserves_approval(self):
        raw={'message':{'role':'assistant','content':'<tool_call> <function=run_command> <parameter=command> pwd </parameter> </function> </tool_call>'}}
        data={'messages':[{'role':'user','content':'Undersøg installationsmappen'}],'full':True,'confirm':True}
        with patch.object(server,'ollama',side_effect=[raw,{'message':{'content':'Færdig'}}]) as model, patch.object(server,'run_command',return_value='testmappe') as run:
            result=server.chat(data)
            self.assertIn('pending',result)
            run.assert_not_called()
            self.assertIn('tools',model.call_args.args[1])
            self.assertEqual(model.call_count,1)
            result=server.confirm({'id':result['pending_id'],'approve':[True]})
            run.assert_called_once_with({'command':' pwd '})
            self.assertEqual(result['answer'],'Færdig')

    def test_raw_tool_call_invalid_or_disabled_never_runs(self):
        valid='<tool_call><function=run_command><parameter=command>pwd</parameter></function></tool_call>'
        malformed=valid.replace('</parameter>', '')
        for content, enabled in ((valid,False),(malformed,True)):
            with self.subTest(enabled=enabled), patch.object(server,'ollama',return_value={'message':{'content':content}}) as model, patch.object(server,'run_command') as run:
                with self.assertRaises(RuntimeError):
                    server.chat({'messages':[{'role':'user','content':'Prøv nu'}],'full':enabled})
                self.assertLessEqual(model.call_count,2)
                run.assert_not_called()

    def test_raw_tool_calls_deny_and_round_limit(self):
        raw={'message':{'content':'<tool_call><function=run_command><parameter=command>pwd</parameter></function></tool_call>'}}
        data={'messages':[{'role':'user','content':'Prøv nu'}],'full':True,'confirm':True}
        with patch.object(server,'ollama',side_effect=[raw,{'message':{'content':'Afvist'}}]), patch.object(server,'run_command') as run:
            pending=server.chat(data)
            result=server.confirm({'id':pending['pending_id'],'approve':[False]})
            run.assert_not_called()
            self.assertIn('afviste',result['tools'][0]['result'])
        with patch.object(server,'ollama',return_value=raw), patch.object(server,'run_command') as run:
            result=server.loop({'messages':[],'data':data,'turn':server.MAX_TOOL_ROUNDS,'thinking':[],'log':[]})
            self.assertIn('ikke bekræftet færdig',result['answer'])
            run.assert_not_called()

    def test_raw_tool_parser_preserves_commands_and_rejects_ambiguity(self):
        text="<tool_call>\n<function=run_command>\n<parameter=command>\nprintf '%s' 'a&b'; test 1 -lt 2 && echo '<ok>'\n</parameter>\n</function>\n</tool_call>"
        normalized=server.normalize_tool_text({'content':text},[server.RUN_COMMAND])
        self.assertEqual(server.call_parts(normalized['tool_calls'][0]),('run_command',{'command':"printf '%s' 'a&b'; test 1 -lt 2 && echo '<ok>'"}))
        for quoted in ('Eksempel: '+text,'```xml\n'+text+'\n```'):
            self.assertEqual(server.normalize_tool_text({'content':quoted},[server.RUN_COMMAND]),{'content':quoted})
        for invalid in (text+' trailing',text.replace('<parameter=command>','<parameter=unknown>'),text.replace('</function>','<parameter=command>echo bad</parameter></function>'),text.replace('<parameter=command>', '<parameter=command><tool_call>')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                server.normalize_tool_text({'content':invalid},[server.RUN_COMMAND])
        with self.assertRaises(ValueError):
            server.normalize_tool_text({'content':text*5},[server.RUN_COMMAND])
        batch=server.normalize_tool_text({'content':text+text},[server.RUN_COMMAND])
        self.assertEqual(len(batch['tool_calls']),2)
        missing='<tool_call><function=run_command></function></tool_call>'
        with self.assertRaises(ValueError):
            server.normalize_tool_text({'content':missing},[server.RUN_COMMAND])
        native={'content':text,'tool_calls':[{'function':{'name':'run_command','arguments':{'command':'pwd'}}}]}
        self.assertEqual(server.normalize_tool_text(native,[server.RUN_COMMAND]),native)

    def test_raw_tool_call_runs_through_http_approval(self):
        # Rigtigt HTTP-forløb + shell; kun modelsvaret erstattes af det fejlende format.
        command='echo LUNA_TOOL_OK'
        raw={'message':{'content':'<tool_call><function=run_command><parameter=command>'+command+'</parameter></function></tool_call>'}}
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=httpd.serve_forever,daemon=True).start()
        def post(path,body):
            conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
            try:
                conn.request('POST',path,json.dumps(body),{'Host':'127.0.0.1:5000','Content-Type':'application/json','X-Luna-Token':server.TOKEN})
                res=conn.getresponse()
                return res.status,json.loads(res.read())
            finally:
                conn.close()
        try:
            with patch.object(server,'ollama',side_effect=[raw,{'message':{'content':'Kommandoen er kørt'}}]):
                status,pending=post('/api/chat',{'messages':[{'role':'user','content':'Kør echo LUNA_TOOL_OK'}],'full':True,'confirm':True})
                self.assertEqual(status,200)
                self.assertEqual(pending['pending'][0]['name'],'run_command')
                status,answer=post('/api/confirm',{'id':pending['pending_id'],'approve':[True]})
                self.assertEqual(status,200)
                self.assertIn('LUNA_TOOL_OK',answer['tools'][0]['result'])
                self.assertIn('Exit-kode 0',answer['tools'][0]['result'])
        finally:
            httpd.shutdown();httpd.server_close()

    def test_system_message_stays_first_during_retry_and_completion(self):
        malformed={'message':{'role':'assistant','content':'<tool_call><function=run_command><parameter=command>echo OK'}}
        call={'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'run_command','arguments':{'command':'echo OK'}}}]}}
        for sequence in ([malformed,call,{'message':{'content':'OK'}}], [call,call,call,{'message':{'content':'OK'}}]):
            captured=[]
            def fake(endpoint,payload=None,timeout=None):
                captured.append(json.loads(json.dumps(payload)))
                self.assertEqual([i for i,m in enumerate(payload['messages']) if m['role']=='system'],[0])
                self.assertIn('Luna Local',payload['messages'][0]['content'])
                return sequence[len(captured)-1]
            with self.subTest(rounds=len(sequence)), patch.object(server,'ollama',side_effect=fake), patch.object(server,'run_command',return_value='Exit-kode 0\nOK'):
                result=server.chat({'messages':[{'role':'user','content':'Kør echo OK'}],'full':True})
                self.assertEqual(result['answer'],'OK')
                self.assertEqual(len(captured),len(sequence))
                self.assertEqual(len(result['tools']),1 if len(sequence)==3 else 3)
                # Tilføjelser må ikke ændre tidligere kalds beskeder.
                self.assertNotIn('tool round limit',captured[0]['messages'][0]['content'])
                if len(sequence)==3:
                    self.assertEqual(captured[1]['messages'][-1]['role'],'user')
                    self.assertNotIn(malformed['message'],captured[1]['messages'])
                if len(sequence)==4:
                    self.assertIn('tools',captured[-1])

    def test_backend_malformed_call_retries_before_approval(self):
        self.addCleanup(server.PENDING.clear)
        error = RuntimeError('llama-server returned invalid tool call arguments for "write_file": unexpected end of JSON input')
        call = {'message': {'role': 'assistant', 'tool_calls': [{'function': {
            'name': 'write_file', 'arguments': {'path': 'example.txt', 'content': 'OK'}}}]}}
        with patch.object(server, 'ollama', side_effect=[error, call]), patch.object(server, 'run_tool') as run:
            result = server.chat({'messages': [{'role': 'user', 'content': 'Skriv filen'}],
                                  'full': True, 'confirm': True})
            self.assertIn('pending_id', result)
            run.assert_not_called()
        with patch.object(server, 'ollama', side_effect=error) as backend:
            with self.assertRaisesRegex(RuntimeError, 'ufuldstændigt'):
                server.chat({'messages': [{'role': 'user', 'content': 'Skriv filen'}], 'full': True})
            self.assertEqual(backend.call_count, 2)

    def test_backend_context_failure_preserves_completed_tool_results(self):
        call = {'message': {'role': 'assistant', 'tool_calls': [{'function': {
            'name': 'run_command', 'arguments': {'command': 'echo OK'}}}]}}
        error = RuntimeError('Ollama afviste kaldet: No user query found in messages.')
        with patch.object(server, 'ollama', side_effect=[call, error]), patch.object(server, 'run_tool', return_value='Exit-kode 0: OK') as run:
            result = server.chat({'messages': [{'role': 'user', 'content': 'Kør echo OK'}], 'full': True})
            self.assertIn('kontekst', result['answer'])
            self.assertIn('Exit-kode 0: OK', result['answer'])
            self.assertEqual(len(result['tools']), 1)
            run.assert_called_once()

    def test_installation_can_use_six_approved_tool_rounds(self):
        call={'message':{'role':'assistant','tool_calls':[{'function':{'name':'run_command','arguments':{'command':'echo CHECK'}}}]}}
        with patch.object(server,'ollama',side_effect=[call]*6+[{'message':{'content':'Kontrolleret'}}]), patch.object(server,'run_command',return_value='Exit-kode 0\nCHECK') as run:
            result=server.chat({'messages':[{'role':'user','content':'Udfør seks kontroller'}],'full':True,'confirm':True})
            for i in range(6):
                self.assertIn('pending_id',result)
                self.assertEqual(run.call_count,i)
                result=server.confirm({'id':result['pending_id'],'approve':[True]})
            self.assertEqual(result['answer'],'Kontrolleret')
            self.assertEqual(run.call_count,6)
            self.assertEqual(len(result['tools']),6)

    def test_round_budget_survives_approval_and_reports_results(self):
        call={'message':{'role':'assistant','tool_calls':[{'function':{'name':'run_command','arguments':{'command':'echo LAST_RESULT'}}}]}}
        with patch.object(server,'MAX_TOOL_ROUNDS',2), patch.object(server,'ollama',return_value=call) as model, patch.object(server,'run_command',return_value='Exit-kode 0\nLAST_RESULT') as run:
            result=server.chat({'messages':[{'role':'user','content':'Kontrollér'}],'full':True,'confirm':True})
            for i in range(2):
                self.assertEqual(run.call_count,i)
                result=server.confirm({'id':result['pending_id'],'approve':[True]})
            self.assertEqual(model.call_count,2)
            self.assertEqual(run.call_count,2)
            self.assertIn('LAST_RESULT',result['answer'])
            self.assertIn('ikke bekræftet færdig',result['answer'])
            self.assertEqual(len(result['tools']),2)

    def test_oversized_batch_retries_without_running_partial_batch(self):
        call={'function':{'name':'run_command','arguments':{'command':'echo OK'}}}
        oversized={'message':{'role':'assistant','tool_calls':[call]*5}}
        valid={'message':{'role':'assistant','tool_calls':[call]}}
        for replies, count in (([oversized,valid,{'message':{'content':'OK'}}],1),([oversized,oversized],0)):
            with self.subTest(count=count), patch.object(server,'ollama',side_effect=replies), patch.object(server,'run_command',return_value='OK') as run:
                result=server.chat({'messages':[{'role':'user','content':'Kontrollér'}],'full':True})
                self.assertEqual(run.call_count,count)
                self.assertEqual(len(result['tools']),count)
                if not count:self.assertIn('De blev ikke udført',result['answer'])

    def test_image_forwarded(self):
        image=base64.b64encode(b'\x89PNG\r\n\x1a\nexample').decode()
        data={'messages':[{'role':'user','content':'Hvad ser du?','images':[image]}]}
        def fake(endpoint,payload=None,timeout=None):
            if endpoint=='show':return {'capabilities':['completion','vision']}
            return {'message':{'content':'Et billede'}}
        with patch.object(server,'ollama',side_effect=fake) as model:
            server.VISION_CACHE.clear()
            server.chat(data)
            self.assertEqual(model.call_args.args[1]['messages'][-1]['images'],[image])
            server.VISION_CACHE.clear()
    def test_image_needs_a_vision_model(self):
        # Modellen uden billed-understøttelse får en klar fejl FØR et modelkald spildes
        image=base64.b64encode(b'\x89PNG\r\n\x1a\nexample').decode()
        msgs=[{'role':'user','content':'Hvad ser du?','images':[image]}]
        server.VISION_CACHE.clear()
        with patch.object(server,'active_model',return_value='qwen3.5-9b-uncensored'), \
             patch.object(server,'ollama',return_value={'capabilities':['completion','tools','thinking']}):
            with self.assertRaises(ValueError) as ctx:
                server.require_vision(msgs)
            self.assertIn('kan derfor ikke se dit billede',str(ctx.exception))
            # samme fejl hele vejen gennem chat()
            with self.assertRaises(ValueError):
                server.chat({'messages':msgs})
        server.VISION_CACHE.clear()
        # vision-model går igennem uden undtagelse
        with patch.object(server,'active_model',return_value='qwen3.5:9b'), \
             patch.object(server,'ollama',return_value={'capabilities':['completion','vision']}):
            server.require_vision(msgs)
        server.VISION_CACHE.clear()
        # ingen billeder -> Ollama slet ikke spurgt
        with patch.object(server,'ollama') as model:
            server.require_vision([{'role':'user','content':'hej'}])
            model.assert_not_called()
        # Ollama kan ikke spørges -> lad chat-kaldet selv svare frem for at gætte
        with patch.object(server,'ollama',side_effect=RuntimeError('nede')):
            server.require_vision(msgs)
        server.VISION_CACHE.clear()
    def test_input_limits(self):
        for data in ({'messages':[]},{'messages':[{'role':'system','content':'override'}]}, {'messages':[{'role':'user','content':'x'*(server.CHAT_LIMIT+1)}]}, {'messages':[{'role':'user','content':'x','images':['invalid']}]}, {'messages':[{'role':'user','content':'x'}],'tools':'yes'}):
            with self.assertRaises(ValueError):server.validate(data)
    def test_listed_paths_can_be_read_without_rebasing(self):
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp)/'project';workspace=project/'workspace'
            nested=workspace/'workspace'/'LoraMint';nested.mkdir(parents=True)
            (nested/'training_config.py').write_text('CONFIG_OK')
            (project/'project.txt').write_text('PROJECT_OK')
            full=dict(server.READ_ONLY,full=True,read=True,folders=True)
            with patch.object(server,'WORKSPACE',workspace):
                for directory in (None,str(project),str(nested),'workspace/LoraMint'):
                    args={} if directory is None else {'path':directory}
                    paths=json.loads(server.list_files(args,full))
                    found=[p for p in paths if p.endswith('training_config.py')]
                    self.assertEqual(len(found),1)
                    self.assertEqual(server.read_file({'path':found[0]},full),'CONFIG_OK')
                paths=json.loads(server.list_files({'path':str(project)},full))
                external=next(p for p in paths if p.endswith('project.txt'))
                self.assertTrue(Path(external).is_absolute())
                with self.assertRaises(ValueError):
                    server.read_file({'path':external},server.READ_ONLY)
                paths=json.loads(server.list_files({'path':'workspace/LoraMint'},server.READ_ONLY))
                self.assertEqual(server.read_file({'path':paths[0]},server.READ_ONLY),'CONFIG_OK')

    def test_workspace_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace';root.mkdir();(root/'hello.txt').write_text('hello')
            secret=Path(temp)/'secret.txt';secret.write_text('secret')
            try:
                (root/'link.txt').symlink_to(secret)
            except OSError:
                self.skipTest('symlinks kræver udvikler-/adminrettigheder på Windows')
            (root/'large.txt').write_text('x'*32001)
            with patch.object(server,'WORKSPACE',root):
                self.assertEqual(server.run_tool('read_file',{'path':'hello.txt'}),'hello')
                for path in ('../secret.txt',str(secret),'link.txt','large.txt'):
                    self.assertTrue(server.run_tool('read_file',{'path':path}).startswith('Værktøjsfejl'))
                self.assertNotIn('link.txt',server.run_tool('list_files',{}))
                self.assertTrue(server.run_tool('shell',{}).startswith('Værktøjsfejl'))
                self.assertTrue(server.run_tool('run_command',{'command':'echo hi'}).startswith('Værktøjsfejl'))
                self.assertTrue(server.run_tool('write_file',{'path':'x.txt','content':'y'}).startswith('Værktøjsfejl'))
                self.assertTrue(server.run_tool('fetch_url',{'url':'https://example.com'}).startswith('Værktøjsfejl'))

    def test_edit_tool_inside_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace';root.mkdir()
            write={'edit':True,'tools':True}
            with patch.object(server,'WORKSPACE',root):
                out=server.run_tool('write_file',{'path':'sub/note.txt','content':'hej'},server.access_for(write))
                self.assertIn('Skrev 3 tegn',out)
                self.assertEqual((root/'sub'/'note.txt').read_text(encoding='utf-8'),'hej')
                self.assertEqual(server.run_tool('read_file',{'path':'sub/note.txt'},server.access_for(write)),'hej')
                for path in ('../evil.txt',str(Path(temp)/'evil.txt')):
                    self.assertTrue(server.run_tool('write_file',{'path':path,'content':'x'},server.access_for(write)).startswith('Værktøjsfejl'))
                    self.assertFalse((Path(temp)/'evil.txt').exists())
                self.assertTrue(server.run_tool('write_file',{'path':'a.txt','content':'x'*200001},server.access_for(write)).startswith('Værktøjsfejl'))

    def test_full_access_runs_command(self):
        with patch.object(server,'WORKSPACE',Path(tempfile.gettempdir())):
            denied=server.run_tool('run_command',{'command':'echo hi'},server.access_for({'edit':True}))
            self.assertTrue(denied.startswith('Værktøjsfejl'))
            allowed=server.run_tool('run_command',{'command':'echo luna'},server.access_for({'full':True}))
            self.assertTrue(allowed.startswith('Exit-kode 0'))
            self.assertIn('luna',allowed)
            empty=server.run_tool('run_command',{'command':'   '},server.access_for({'full':True}))
            self.assertTrue(empty.startswith('Værktøjsfejl'))

    def test_skills_are_listed_loaded_and_contained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'cat'/'demo'/'references').mkdir(parents=True)
            (root/'cat'/'demo'/'SKILL.md').write_text('---\nname: demo\ndescription: >\n  Laver demoer.\n  Brug ved test.\n---\n# Demo\nGør sådan.',encoding='utf-8')
            (root/'cat'/'demo'/'references'/'guide.md').write_text('guide-tekst',encoding='utf-8')
            (root/'_drafts'/'kladde').mkdir(parents=True)
            (root/'_drafts'/'kladde'/'SKILL.md').write_text('---\nname: kladde\n---\n',encoding='utf-8')
            (root/'hemmelig.txt').write_text('nej',encoding='utf-8')
            with patch.object(server,'SKILLS_DIRS',[root]):
                self.assertEqual(list(server.skill_index()),['demo'])
                self.assertIn('- demo: Laver demoer. Brug ved test.',server.skill_listing())
                access=server.access_for({'skills':True})
                self.assertTrue(access['skills'])
                self.assertIn('use_skill',server.allowed(access))
                self.assertIn('Gør sådan.',server.run_tool('use_skill',{'name':'demo'},access))
                self.assertEqual(server.run_tool('read_skill_file',{'name':'demo','path':'references/guide.md'},access),'guide-tekst')
                self.assertIn('references/guide.md',server.run_tool('read_skill_file',{'name':'demo'},access))
                self.assertTrue(server.run_tool('read_skill_file',{'name':'demo','path':'../../hemmelig.txt'},access).startswith('Værktøjsfejl'))
                self.assertTrue(server.run_tool('use_skill',{'name':'kladde'},access).startswith('Værktøjsfejl'))
                self.assertTrue(server.run_tool('use_skill',{'name':'demo'},server.access_for({})).startswith('Værktøjsfejl'))
                self.assertFalse(server.needs_approval('use_skill',{'name':'demo'},access))
            with patch.object(server,'SKILLS_DIRS',[root/'findes-ikke']):
                self.assertFalse(server.access_for({'skills':True})['skills'])

    def test_access_flags_are_validated(self):
        for flag in ('edit','web','full','confirm','tools','think','solo','memory','folders','github','mcp','agents','skills'):
            with self.assertRaises(ValueError):server.validate({'messages':[{'role':'user','content':'x'}],flag:'yes'})
        self.assertEqual(server.access_for({'full':True}),{'read':True,'edit':True,'web':False,'github':False,'mcp':False,'agents':False,'skills':False,'folders':True,'full':True})
        self.assertEqual(server.access_for({'tools':True}),{'read':True,'edit':False,'web':False,'github':False,'mcp':False,'agents':False,'skills':False,'folders':False,'full':False})
        self.assertFalse(server.access_for({})['agents'])
        self.assertFalse(server.needs_approval('fetch_url',{'url':'https://example.com'},server.access_for({})))
        self.assertTrue(server.needs_approval('run_command',{'command':'dir'},server.access_for({'full':True})))
        self.assertTrue(server.needs_approval('read_file',{'path':'C:/Users/x/secret.txt'},server.access_for({'full':True})))
        # The new switches stay off until the matching connection exists in settings.
        self.assertFalse(server.access_for({'github':True,'mcp':True,'folders':True})['github'])
        self.assertFalse(server.access_for({'github':True,'mcp':True,'folders':True})['mcp'])
        server.save_settings({'github':{'token':'tok_123456','user':'lars'},'folders':[self._temp.name],
                              'mcp':[{'name':'Notes','command':'notes.exe'}]})
        on=server.access_for({'github':True,'mcp':True,'folders':True})
        self.assertTrue(on['github'] and on['mcp'] and on['folders'] and on['read'])
        self.assertEqual(server.connections(),{'github':True,'mcp':1,'folders':1})

    def test_confirmation_gate_and_resume(self):
        calls={'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'write_file','arguments':{'path':'a.txt','content':'ny'}}}]}}
        done={'message':{'content':'Filen er skrevet.'}}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace';root.mkdir()
            with patch.object(server,'WORKSPACE',root), patch.object(server,'ollama',side_effect=[calls,done]) as model:
                data={'messages':[{'role':'user','content':'Skriv filen'}],'edit':True,'confirm':True}
                first=server.chat(data)
                self.assertIn('pending',first)
                self.assertEqual(first['pending'][0]['name'],'write_file')
                self.assertIn('a.txt',first['pending'][0]['title'])
                self.assertEqual(model.call_count,1)
                self.assertFalse((root/'a.txt').exists())
                self.assertEqual(len(server.PENDING),1)
                result=server.confirm({'id':first['pending_id'],'approve':[True]})
                self.assertEqual(result['answer'],'Filen er skrevet.')
                self.assertEqual((root/'a.txt').read_text(encoding='utf-8'),'ny')
                self.assertEqual(len(server.PENDING),0)
                self.assertEqual(model.call_count,2)
                self.assertTrue(model.call_args.args[1]['messages'][-1]['content'].startswith('Skrev'))

    def test_confirmation_rejection(self):
        calls={'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'write_file','arguments':{'path':'a.txt','content':'ny'}}}]}}
        done={'message':{'content':'Okay, intet er ændret.'}}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace';root.mkdir()
            with patch.object(server,'WORKSPACE',root), patch.object(server,'ollama',side_effect=[calls,done]):
                data={'messages':[{'role':'user','content':'Skriv filen'}],'edit':True,'confirm':True}
                first=server.chat(data)
                result=server.confirm({'id':first['pending_id'],'approve':[False]})
                self.assertEqual(result['answer'],'Okay, intet er ændret.')
                self.assertFalse((root/'a.txt').exists())
                self.assertIn('afviste',result['tools'][0]['result'])

    def test_confirmation_rejects_stale_or_bad_id(self):
        with self.assertRaises(ValueError):server.confirm({'id':'kort'})
        server.PENDING.clear()
        with self.assertRaises(ValueError):server.confirm({'id':'x'*32})

    def test_save_command_matches_only_short_orders(self):
        for ok in ('gem','Gem!','save','SAVE.','gem svaret','gem samtale','gem det','save fil'):
            self.assertTrue(server.save_command(ok), ok)
        for no in ('gemme filer bedre','save the date for tomorrow','Hjælp mig med at gemme data','',
                   'gem '+('x'*50),'hukommelse gem'):
            self.assertFalse(server.save_command(no), no)

    def test_save_writes_memory_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace'
            with patch.object(server,'WORKSPACE',root), patch.object(server,'ollama') as model:
                first=server.chat({'messages':[{'role':'user','content':'gem'}]})
                self.assertIn('intet at gemme',first['answer'])
                msgs=[{'role':'user','content':'Hvad hedder du?'},
                      {'role':'assistant','content':'Jeg hedder Luna.'},
                      {'role':'user','content':'gem'}]
                out=server.chat({'messages':msgs})
                model.assert_not_called()
                self.assertIn('Gemt',out['answer'])
                self.assertTrue((root/'Luna.md').is_file())
                data=(root/'Luna.md').read_text(encoding='utf-8')
                self.assertIn('# Luna',data)
                self.assertIn('Hvad hedder du?',data)
                self.assertIn('Jeg hedder Luna.',data)
                server.chat({'messages':msgs+[{'role':'assistant','content':'Andet svar.'},
                                              {'role':'user','content':'save'}]})
                data2=(root/'Luna.md').read_text(encoding='utf-8')
                self.assertIn('Andet svar.',data2)
                self.assertGreater(len(data2),len(data))
                self.assertEqual(data2.count('— LUNA'),2)
                # dobbelt tryk på gem dublerer ikke
                again=server.chat({'messages':msgs})
                self.assertIn('allerede',again['answer'])
                self.assertEqual((root/'Luna.md').read_text(encoding='utf-8'),data2)
                # automatic compact: en overfyldt fil komprimeres i stedet for at afvise brugeren
                (root/'Luna.md').write_text('x'*server.MAX_MEMORY,encoding='utf-8')
                comp=server.chat({'messages':msgs})
                self.assertIn('Gemt',comp['answer'])
                data3=(root/'Luna.md').read_text(encoding='utf-8')
                self.assertLess(len(data3),server.MAX_MEMORY)
                self.assertIn('Hvad hedder du?',data3)

    def test_save_compacts_oldest_and_strips_tool_calls(self):
        # Filen er vokset forbi COMPACT_AT: de ældste par falder ud, og rå værktøjskald ryddes væk
        gammelt = ''.join(
            '## 2026-09-%02d 10:00 — DIG\nspørgsmål %d\n\n## 2026-09-%02d 10:00 — LUNA\nsvar %d\n'
            % (i, i, i, i) + 'y' * 4600 + '\n' for i in range(1, 37))
        header = '# Luna — hukommelse\n\nSparret med kommandoerne `gem` og `save`.\n'
        # det nyeste svar indeholder rå værktøjskald, som ikke må gemmes
        larm = ('\n\n## 2026-09-30 10:00 — DIG\nfind noget\n\n## 2026-09-30 10:00 — LUNA\n'
                'Her er resultatet:\n\n用微信扫\n<function=search_files>\n{"query": "x"}\n'
                '</function>\n vazgeær\n')
        self.assertGreater(len(header) + len(gammelt), server.COMPACT_AT)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'workspace'
            root.mkdir(parents=True)
            (root / 'Luna.md').write_text(header + gammelt + larm, encoding='utf-8')
            with patch.object(server, 'WORKSPACE', root), patch.object(server, 'ollama') as model:
                ud = server.chat({'messages': [{'role': 'user', 'content': 'Hvad hedder du?'},
                                               {'role': 'assistant', 'content': 'Jeg hedder Luna.'},
                                               {'role': 'user', 'content': 'gem'}]})
                model.assert_not_called()                      # gem tager stadig intet modelkald
                self.assertIn('komprimeret', ud['answer'])
            data = (root / 'Luna.md').read_text(encoding='utf-8')
            self.assertLessEqual(len(data), server.COMPACT_AT)  # plads til flere gem
            self.assertNotIn('spørgsmål 1\n', data)             # de ældste faldt ud
            self.assertNotIn('spørgsmål 2\n', data)
            self.assertIn('y' * 4600, data)                     # de nyeste består
            self.assertIn('Hvad hedder du?', data)               # det nye par lagde sig nederst
            self.assertIn('Jeg hedder Luna.', data)
            self.assertNotIn('用微信扫', data)            # rå værktøjskald er renset bort
            self.assertNotIn('<function=', data)
            self.assertNotIn('{"query"', data)
            self.assertIn('# Luna — hukommelse', data)           # overskriften består
            self.assertIn('`gem`', data)                         # backticks i tekst bevares
            # det rensede svar er stadig læsbart for modellen
            memo = server.memory_text()
            self.assertNotIn('用微信扫', memo)

    def test_solo_sends_only_the_last_message(self):
        msgs=[{'role':'user','content':'Hvad er 1+1?'},
              {'role':'assistant','content':'2'},
              {'role':'user','content':'Og 2+2?'}]
        with patch.object(server,'ollama',return_value={'message':{'content':'4'}}) as model:
            server.chat({'messages':msgs,'solo':True})
            sent=model.call_args.args[1]['messages']
            self.assertEqual([m['role'] for m in sent],['system','user'])
            self.assertEqual(sent[-1]['content'],'Og 2+2?')
            server.chat({'messages':msgs})
            normal=model.call_args.args[1]['messages']
            self.assertEqual(len(normal),4)
            self.assertEqual([m['content'] for m in normal[1:]],['Hvad er 1+1?','2','Og 2+2?'])
        with self.assertRaises(ValueError):
            server.chat({'messages':msgs,'solo':'ja'})

    def test_solo_still_saves_and_keeps_tools(self):
        msgs=[{'role':'user','content':'Hvad hedder du?'},
              {'role':'assistant','content':'Jeg hedder Luna.'},
              {'role':'user','content':'gem'}]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace'
            with patch.object(server,'WORKSPACE',root), patch.object(server,'ollama') as model:
                out=server.chat({'messages':msgs,'solo':True})
                self.assertIn('Gemt',out['answer'])
                self.assertIn('Jeg hedder Luna.',(root/'Luna.md').read_text(encoding='utf-8'))
                model.assert_not_called()
        # værktøjer kører også når historikken er skåret fra
        results=[{'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'list_files','arguments':{}}}]}},
                 {'message':{'content':'Filerne er listet'}}]
        with patch.object(server,'ollama',side_effect=results) as model:
            out=server.chat({'messages':[{'role':'user','content':'a'},{'role':'assistant','content':'b'},
                                         {'role':'user','content':'List filer'}],'tools':True,'solo':True})
            self.assertEqual(out['tools'][0]['name'],'list_files')
            # historikken 'a'/'b' må ikke findes i nogen af de sendte beskeder
            sent=model.call_args.args[1]['messages']
            contents=[m.get('content','') for m in sent]
            self.assertNotIn('a',contents)
            self.assertNotIn('b',contents)
            self.assertEqual(sent[1]['content'],'List filer')
            self.assertEqual(len(sent),4)

    def test_memory_reads_luna_md_into_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace'
            root.mkdir(exist_ok=True)
            with patch.object(server,'WORKSPACE',root), patch.object(server,'ollama',return_value={'message':{'content':'Hej'}}) as model:
                server.chat({'messages':[{'role':'user','content':'hej'}],'memory':True})
                self.assertNotIn('Mit navn er Lars',model.call_args.args[1]['messages'][0]['content'])
                (root/'Luna.md').write_text('# Luna — hukommelse\n\n## 1 — DIG\nMit navn er Lars.\n\n## 1 — LUNA\nHej Lars.\n',encoding='utf-8')
                server.chat({'messages':[{'role':'user','content':'hej'}],'memory':True})
                prompt=model.call_args.args[1]['messages'][0]['content']
                self.assertIn('Din hukommelse fra Luna.md',prompt)
                self.assertIn('Mit navn er Lars.',prompt)
                # fra som standard læses filen ikke
                server.chat({'messages':[{'role':'user','content':'hej'}]})
                self.assertNotIn('Mit navn er Lars.',model.call_args.args[1]['messages'][0]['content'])
            with self.assertRaises(ValueError):
                server.chat({'messages':[{'role':'user','content':'hej'}],'memory':'ja'})

    def test_memory_is_capped_to_the_recent_part(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace'
            root.mkdir(exist_ok=True)
            big='# Luna — hukommelse\n'+''.join(
                '## %d — DIG\n%s\n\n## %d — LUNA\n%s\n' % (i,'q'*100,i,'a'*100) for i in range(200))
            (root/'Luna.md').write_text(big,encoding='utf-8')
            with patch.object(server,'WORKSPACE',root), patch.object(server,'ollama',return_value={'message':{'content':'Hej'}}) as model:
                server.chat({'messages':[{'role':'user','content':'hej'}],'memory':True})
                prompt=model.call_args.args[1]['messages'][0]['content']
                self.assertLess(len(prompt),6000)
                self.assertIn('ældre udeladt',prompt)
                self.assertIn('## 199 — LUNA',prompt)
            self.assertLessEqual(len(server.memory_text()),server.MEMORY_LIMIT+260)
    def test_tool_roundtrip(self):
        results=[{'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'list_files','arguments':{}}}]}},{'message':{'content':'Filerne er listet'}}]
        with patch.object(server,'ollama',side_effect=results) as model:
            result=server.chat({'messages':[{'role':'user','content':'List filer'}],'tools':True})
            self.assertEqual(result['tools'][0]['name'],'list_files')
            self.assertEqual(model.call_args.args[1]['messages'][-1]['role'],'tool')
    def test_disabled_tools_do_not_execute(self):
        result={'message':{'tool_calls':[{'function':{'name':'read_file','arguments':{'path':'a'}}}]}}
        with patch.object(server,'ollama',return_value=result),patch.object(server,'run_tool') as tool:
            with self.assertRaises(RuntimeError):server.chat({'messages':[{'role':'user','content':'hi'}]})
            tool.assert_not_called()
    def test_tool_loop_bounded(self):
        result={'message':{'role':'assistant','tool_calls':[{'function':{'name':'list_files','arguments':{}}}]}}
        with patch.object(server,'ollama',return_value=result) as model:
            answer=server.chat({'messages':[{'role':'user','content':'hi'}],'tools':True})
            self.assertEqual(model.call_count,server.MAX_TOOL_ROUNDS)
            self.assertEqual(len(answer['tools']),server.MAX_TOOL_ROUNDS)
            self.assertIn('ikke bekræftet færdig',answer['answer'])
            self.assertIn('list_files',answer['answer'])
    def test_http_access_and_errors(self):
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        def req(method,path,body=None,headers=None):
            conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
            conn.request(method,path,body,headers or {'Host':'127.0.0.1:5000'})
            res=conn.getresponse();out=(res.status,res.read());conn.close();return out
        try:
            self.assertEqual(req('GET','/')[0],200)
            self.assertEqual(req('GET','/',headers={'Host':'evil.example'})[0],403)
            self.assertEqual(req('POST','/api/chat','{}')[0],403)
            headers={'Host':'127.0.0.1:5000','X-Luna-Token':server.TOKEN}
            self.assertEqual(req('POST','/api/chat','{}',headers)[0],400)
            with patch.object(server,'ollama',side_effect=RuntimeError('Ollama offline')):
                code,raw=req('POST','/api/chat',json.dumps({'messages':[{'role':'user','content':'hi'}]}),headers)
                self.assertEqual(code,502);self.assertIn('offline',json.loads(raw)['error'])
            with patch.object(server,'ollama',return_value={'message':{'content':'Hej'}}):
                code,raw=req('POST','/api/chat',json.dumps({'messages':[{'role':'user','content':'hi'}]}),headers)
                self.assertEqual(code,200);self.assertEqual(json.loads(raw)['answer'],'Hej')
        finally:httpd.shutdown();httpd.server_close();thread.join()

    def test_settings_roundtrip_and_masking(self):
        stored=server.save_settings({'github':{'token':'ghp_abcdefghijkl','user':''}})
        self.assertEqual(stored['github']['token'],'ghp_abcdefghijkl')
        public=server.public_settings()
        self.assertEqual(public['github']['token'],'••••ijkl')
        self.assertTrue(public['github']['connected'])
        again=server.save_settings({'github':{'token':public['github']['token'],'user':'lars'}})
        self.assertEqual(again['github']['token'],'ghp_abcdefghijkl')
        self.assertEqual(again['github']['user'],'lars')
        server.save_settings({'github':{'token':'','user':'lars'}})
        self.assertEqual(server.load_settings()['github']['token'],'')
        server.save_settings({'github':{'token':'abc123','user':'lars'},'model':'qwen3.5:9b'})
        server.save_settings({'model':'mistral:7b'})
        self.assertEqual(server.load_settings()['github']['token'],'abc123')
        self.assertEqual(server.load_settings()['github']['user'],'lars')
        for bad in ('nope',{'model':'dum model\nher'},{'folders':['slet ikke/en/sti']},
                    {'folders':['C:/']},{'folders':[42]},
                    {'mcp':[{'name':'x','url':'http://a','command':'node y'}]},
                    {'mcp':[{'name':'','url':'http://a'}]},
                    {'mcp':[{'name':'x','url':'ftp://a'}]},'liste'):
            with self.assertRaises(ValueError):server.save_settings(bad)
        self.assertEqual(server.load_settings()['model'],'mistral:7b')

    def test_model_override_from_settings(self):
        self.assertEqual(server.active_model(),server.MODEL)
        server.save_settings({'model':'mistral:7b'})
        self.assertEqual(server.active_model(),'mistral:7b')

    def test_approved_folders_extend_file_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace';root.mkdir();(root/'w.txt').write_text('ws')
            share=Path(temp)/'share';share.mkdir();(share/'s.txt').write_text('hemmelig')
            other=Path(temp)/'other';other.mkdir();(other/'o.txt').write_text('x')
            server.save_settings({'folders':[str(share)]})
            with patch.object(server,'WORKSPACE',root):
                on=server.access_for({'folders':True})
                self.assertTrue(on['folders'] and on['read']);self.assertFalse(on['edit'])
                self.assertEqual(server.run_tool('read_file',{'path':str(share/'s.txt')},on),'hemmelig')
                self.assertIn('s.txt',server.run_tool('list_files',{'path':str(share)},on))
                self.assertIn('w.txt',server.run_tool('list_files',{},on))
                off=server.access_for({})
                self.assertFalse(off['folders'])
                self.assertTrue(server.run_tool('read_file',{'path':str(share/'s.txt')},off).startswith('Værktøjsfejl'))
                self.assertTrue(server.run_tool('list_files',{'path':str(share)},off).startswith('Værktøjsfejl'))
                self.assertTrue(server.run_tool('read_file',{'path':str(other/'o.txt')},on).startswith('Værktøjsfejl'))
                self.assertTrue(server.run_tool('write_file',{'path':str(share/'ny.txt'),'content':'ny'},on).startswith('Værktøjsfejl'))
                with_edit=server.access_for({'folders':True,'edit':True})
                out=server.run_tool('write_file',{'path':str(share/'ny.txt'),'content':'ny'},with_edit)
                self.assertTrue(out.startswith('Skrev'))
                self.assertEqual((share/'ny.txt').read_text(encoding='utf-8'),'ny')
                self.assertTrue(server.needs_approval('read_file',{'path':str(share/'s.txt')},on))
                self.assertFalse(server.needs_approval('list_files',{},on))
                self.assertTrue(server.needs_approval('list_files',{'path':str(share)},on))
                self.assertIn('approved in Settings',server.system(on))

    def test_github_tool_reads_repositories(self):
        server.save_settings({'github':{'token':'tok_123456','user':''}})
        def fake(path,token,timeout=25):
            self.assertEqual(token,'tok_123456')
            if path.startswith('/user/repos'):return [{'full_name':'lars/proj','private':False,'description':'Min ting'}]
            if path.startswith('/repos/lars/proj/contents'):
                return {'content':base64.b64encode('print(1)'.encode()).decode(),'encoding':'base64'}
            if path.startswith('/repos/lars/proj/issues'):return [{'number':7,'title':'Fejl i start'},{'number':8,'title':'PR','pull_request':{}}]
            if path=='/user':return {'login':'lars'}
            raise AssertionError('ukendt sti '+path)
        with patch.object(server,'github_request',side_effect=fake):
            self.assertIn('lars/proj',server.github_call({'action':'repos'}))
            self.assertEqual(server.github_call({'action':'contents','repo':'lars/proj','path':'a.py'}),'print(1)')
            issues=server.github_call({'action':'issues','repo':'lars/proj'})
            self.assertIn('#7 Fejl i start',issues);self.assertNotIn('#8',issues)
            with self.assertRaises(ValueError):server.github_call({'action':'contents','repo':'forket navn'})
            with self.assertRaises(ValueError):server.github_call({'action':'tul'})
            with self.assertRaises(ValueError):server.github_call({'action':'contents'})
        access=server.access_for({'github':True})
        self.assertEqual([t['function']['name'] for t in server.tools_for(access)],['github'])
        self.assertFalse(server.needs_approval('github',{'action':'repos'},access))
        self.assertIn('GitHub',server.system(access))
        server.save_settings({'github':{'token':'','user':''}})
        with self.assertRaises(ValueError):server.github_call({'action':'repos'})
        self.assertFalse(server.access_for({'github':True})['github'])

    def test_mcp_tools_from_local_command(self):
        import sys
        script=Path(self._temp.name)/'fake_mcp.py'
        script.write_text(FAKE_MCP_SCRIPT,encoding='utf-8')
        server.save_settings({'mcp':[{'name':'Test','command':'"%s" "%s"'%(sys.executable,script)}]})
        access=server.access_for({'mcp':True})
        names=[t['function']['name'] for t in server.tools_for(access)]
        self.assertIn('mcp__Test__echo',names)
        self.assertIn('mcp__Test__sum',names)
        self.assertIn('mcp__Test__echo',server.allowed(access))
        self.assertTrue(server.needs_approval('mcp__Test__echo',{'tekst':'hej'},access))
        self.assertEqual(server.run_tool('mcp__Test__echo',{'tekst':'hej'},access),'Echo: hej')
        self.assertEqual(server.run_tool('mcp__Test__sum',{'a':2,'b':3},access),'5')
        self.assertTrue(server.run_tool('mcp__Test__sum',{'a':2},access).startswith('Værktøjsfejl'))
        self.assertIn('mcp__Test__echo',server.describe('mcp__Test__echo',{'tekst':'hej'}))
        self.assertIn('MCP',server.system(access))
        self.assertEqual(server.access_for({})['mcp'],False)
        self.assertEqual([t['function']['name'] for t in server.tools_for(server.access_for({}))],[])
        probe=server.mcp_probe(server.load_settings()['mcp'][0])
        self.assertIn('2 værktøjer',probe)

    def test_mcp_env_reaches_the_command(self):
        import sys
        script=Path(self._temp.name)/'env_mcp.py'
        script.write_text(FAKE_ENV_MCP_SCRIPT,encoding='utf-8')
        # Miljø gemmes som dict og når helt frem til den lokale underproces
        server.save_settings({'mcp':[
            {'name':'Med','command':'"%s" "%s"'%(sys.executable,script),'env':'LUNA_TEST=kom_sanden'},
            {'name':'Uden','command':'"%s" "%s"'%(sys.executable,script)}]})
        lagret=server.load_settings()['mcp']
        self.assertEqual(lagret[0]['env'],{'LUNA_TEST':'kom_sanden'})
        self.assertEqual(lagret[1]['env'],{})
        access=server.access_for({'mcp':True})
        self.assertEqual(server.run_tool('mcp__Med__hent',{},access),'kom_sanden')
        self.assertEqual(server.run_tool('mcp__Uden__hent',{},access),'(ikke sat)')
        # De to servere har samme kommando men forskelligt miljø — de må ikke dele cache-nøgle
        self.assertNotEqual(server.mcp_key(lagret[0]),server.mcp_key(lagret[1]))
        # Klienten ser miljøet som en tekstlinje
        self.assertIn('LUNA_TEST=kom_sanden',server.public_settings()['mcp'][0]['env'])
        # Ugyldige varianter afvises ved gemning
        for env in ('UDEN_LIGMED','1UGYLDIG=x',['ikke','dict'],'X='+'y'*401,{'??':'x'},['a=b','c']):
            with self.assertRaises(ValueError):
                server.save_settings({'mcp':[{'name':'x','command':'node y','env':env}]})
        # Tomt betyder intet — og der er højst 12 variabler
        self.assertEqual(server.validate_env({'env':''}),{})
        with self.assertRaises(ValueError):
            server.validate_env({'env':'; '.join('V%d=x'%i for i in range(13))})

    def test_mcp_install_a_server(self):
        import sys
        script=Path(self._temp.name)/'fake_mcp.py'
        script.write_text(FAKE_MCP_SCRIPT,encoding='utf-8')
        start='"%s" "%s"'%(sys.executable,script)
        # En forhindret server gør at MCP-slået-til overhovedet er muligt
        server.save_settings({'mcp':[{'name':'Forhaand','command':'node x-der-ikke-findes'}]})
        access=server.access_for({'mcp':True})
        self.assertTrue(access['mcp'])

        # Værktøjet findes med MCP slået til, kræver altid godkendelse og beskrives pænt
        self.assertIn('mcp_install',[t['function']['name'] for t in server.tools_for(access)])
        self.assertNotIn('mcp_install',server.allowed(server.access_for({})))
        self.assertTrue(server.needs_approval('mcp_install',{'name':'x'},access))
        beskriv=server.describe('mcp_install',{'name':'x','command':'uvx y','installer':'python -m pip install y'})
        self.assertIn('uvx y',beskriv)
        self.assertIn('python -m pip install y',beskriv)

        # Hele kørslen: installationskommando, gemning, forbindelse og værktøjsliste
        ud=server.run_tool('mcp_install',{'name':'Ny','command':start,
                                          'installer':'echo pakken'},access)
        self.assertIn('installeret',ud)
        self.assertIn('2 værktøjer',ud)
        self.assertIn('pakken',ud)
        navne=[m['name'] for m in server.load_settings()['mcp']]
        self.assertEqual(navne,['Forhaand','Ny'])
        self.assertIn('mcp__Ny__echo',server.allowed(access))
        self.assertEqual(server.run_tool('mcp__Ny__echo',{'tekst':'hej'},access),'Echo: hej')

        # Samme navn igen = opdatering, ikke en dobbeltgang
        ud=server.run_tool('mcp_install',{'name':'ny','command':start},access)
        self.assertIn('opdateret',ud)
        self.assertEqual([m['name'] for m in server.load_settings()['mcp']],['Forhaand','Ny'])

        # Ugyldigt input afvises uden at gemme noget
        for args in ({'name':''},{'name':'x','command':'a','url':'http://b'},
                     {'name':'x'},{'name':'x','command':'node y','env':'SKRAET'}):
            with self.assertRaises(ValueError):
                server.mcp_install_call(args)
        self.assertEqual([m['name'] for m in server.load_settings()['mcp']],['Forhaand','Ny'])

        # En installationskommando der fejler, stopper det hele før gemning
        with self.assertRaises(ValueError):
            server.mcp_install_call({'name':'Daarlig','command':start,'installer':'exit 3'})
        self.assertEqual([m['name'] for m in server.load_settings()['mcp']],['Forhaand','Ny'])

        # En server der ikke svarer, rulles helt tilbage — også ved opdatering af en eksisterende
        with self.assertRaises(ValueError):
            server.mcp_install_call({'name':'Stille','command':'xyz-eksisterer-ikke-97'})
        with self.assertRaises(ValueError):
            server.mcp_install_call({'name':'Ny','command':'xyz-eksisterer-ikke-97'})
        self.assertEqual([m['name'] for m in server.load_settings()['mcp']],['Forhaand','Ny'])

    def test_ollama_rejects_in_danish_and_logs_breaks(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        # Ollama's 400 ved for stor kontekst bliver til en besked, brugeren kan handle på
        afvist = ('{"error":{"code":400,"message":"request (32431 tokens) exceeds the available '
                  'context size (20480 tokens)","type":"exceed_context_size_error"}}')
        ud = server.ollama_afvisning(afvist)
        self.assertIn('for stor til modellens kontekst',ud)
        self.assertIn('Start en ny samtale',ud)
        self.assertTrue(server.ollama_afvisning('{"error":"model not found"}').startswith('Ollama afviste kaldet'))

        # Hver afbrydelse skrives til loggen med forsøg, tid og hvor langt svaret var nået
        log=Path(self._temp.name)/'fejl.log'
        server.log_ollama_fejl(ConnectionResetError('forbundet afbrudt'),2,0,3.4,fil=log)
        server.log_ollama_fejl(TimeoutError('tidsgrænse'),1,17,600.0,fil=log)
        indhold=log.read_text(encoding='utf-8')
        linjer=indhold.strip().splitlines()
        self.assertEqual(len(linjer),2)
        self.assertIn('ConnectionResetError',linjer[0])
        self.assertIn('0 linjer modtaget',linjer[0])
        self.assertIn('17 linjer modtaget',linjer[1])
        self.assertIn('600.0s',linjer[1])

        # Et tabt forbindelse uden svar prøves én gang igen — svaret kommer fra andet forsøg
        class Broek(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                if not getattr(self.server,'brudt',False):
                    self.server.brudt=True
                    self.connection.close()          # som en Ollama-runner der dør midt i
                    return
                self.send_response(200)
                self.send_header('Content-Type','application/x-ndjson')
                self.end_headers()
                for linje in ({'message':{'role':'assistant','content':'Hej fra andet forsøg'},'done':False},
                              {'message':{'role':'assistant','content':''},'done':True}):
                    self.wfile.write((json.dumps(linje)+'\n').encode())
                self.wfile.flush()
        httpd=ThreadingHTTPServer(('127.0.0.1',0),Broek)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        old_host,old_port=server.OLLAMA_HOST,server.OLLAMA_PORT
        server.OLLAMA_HOST,server.OLLAMA_PORT='127.0.0.1',httpd.server_port
        try:
            with patch.object(server,'ROOT',Path(self._temp.name)):
                svar=server.ollama_chat({'model':'x','messages':[{'role':'user','content':'hej'}]},timeout=20)
                self.assertIn('andet forsøg',svar['message']['content'])
                # og loggen fik fanget afbrydelsen
                self.assertIn('ollama_chat forsøg 1',(Path(self._temp.name)/'fejl.log').read_text(encoding='utf-8'))
        finally:
            server.OLLAMA_HOST,server.OLLAMA_PORT=old_host,old_port
            httpd.shutdown()
            httpd.server_close()

    def test_mcp_http_server_with_session_and_sse(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        seen={'session':None}
        class Fake(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                length=int(self.headers.get('Content-Length','0'))
                msg=json.loads(self.rfile.read(length))
                method=msg.get('method');mid=msg.get('id')
                params=msg.get('params') or {}
                if mid is None:
                    self.send_response(202);self.send_header('Content-Length','0');self.end_headers();return
                if method=='initialize':
                    body=json.dumps({'jsonrpc':'2.0','id':mid,'result':{'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'fake','version':'1'}}})
                    payload=('data: %s\n\n'%body).encode()
                    self.send_response(200)
                    self.send_header('Content-Type','text/event-stream')
                    self.send_header('Mcp-Session-Id','sess-42')
                    self.send_header('Content-Length',str(len(payload)))
                    self.end_headers();self.wfile.write(payload)
                    return
                if self.headers.get('Mcp-Session-Id')!='sess-42':
                    reply={'jsonrpc':'2.0','id':mid,'error':{'code':-32000,'message':'mangler session'}}
                elif method=='tools/list':
                    reply={'jsonrpc':'2.0','id':mid,'result':{'tools':[{'name':'note','description':'Hent en note','inputSchema':{'type':'object','properties':{'navn':{'type':'string'}},'required':['navn']}}]}}
                elif method=='tools/call':
                    seen['session']=self.headers.get('Mcp-Session-Id')
                    reply={'jsonrpc':'2.0','id':mid,'result':{'content':[{'type':'text','text':'Note: '+params.get('arguments',{}).get('navn','')}],'isError':False}}
                else:
                    reply={'jsonrpc':'2.0','id':mid,'error':{'code':-32601,'message':method}}
                payload=json.dumps(reply).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers();self.wfile.write(payload)
        httpd=ThreadingHTTPServer(('127.0.0.1',0),Fake)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        try:
            server.save_settings({'mcp':[{'name':'Noter','url':'http://127.0.0.1:%d/mcp'%httpd.server_port}]})
            access=server.access_for({'mcp':True})
            names=[t['function']['name'] for t in server.tools_for(access)]
            self.assertEqual(names,['mcp__Noter__note','mcp_install'])
            self.assertEqual(server.run_tool('mcp__Noter__note',{'navn':'indkøb'},access),'Note: indkøb')
            self.assertEqual(seen['session'],'sess-42')
            self.assertIn('1 værktøjer',server.mcp_probe(server.load_settings()['mcp'][0]))
        finally:
            httpd.shutdown();httpd.server_close();thread.join()

    def test_settings_endpoints_over_http(self):
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        def req(method,path,body=None,headers=None):
            conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
            conn.request(method,path,body,headers or {'Host':'127.0.0.1:5000'})
            res=conn.getresponse();out=(res.status,res.read());conn.close();return out
        plain={'Host':'127.0.0.1:5000'}
        auth={'Host':'127.0.0.1:5000','X-Luna-Token':server.TOKEN}
        try:
            self.assertEqual(req('GET','/api/settings',None,plain)[0],403)
            self.assertEqual(req('GET','/api/models',None,plain)[0],403)
            code,raw=req('GET','/api/settings',None,auth)
            self.assertEqual(code,200);self.assertEqual(json.loads(raw)['folders'],[])
            code,raw=req('POST','/api/settings',json.dumps({'github':{'token':'ghp_secret9999'}}),auth)
            self.assertEqual(code,200);self.assertEqual(json.loads(raw)['github']['token'],'••••9999')
            code,raw=req('POST','/api/settings','{"folders": 1}',auth)
            self.assertEqual(code,400)
            code,raw=req('POST','/api/settings',json.dumps({'folders':[self._temp.name]}),auth)
            self.assertEqual(code,200);self.assertEqual(json.loads(raw)['folders'],[str(Path(self._temp.name).resolve())])
            code,raw=req('POST','/api/settings/test',json.dumps({'kind':'folder','path':self._temp.name}),auth)
            self.assertEqual(code,200);self.assertIn('Mappen findes',json.loads(raw)['message'])
            code,raw=req('POST','/api/settings/test',json.dumps({'kind':'tul'}),auth)
            self.assertEqual(code,400)
            code,raw=req('POST','/api/settings',json.dumps({'mcp':[{'name':'x','url':'ftp://x'}]}),auth)
            self.assertEqual(code,400)
            code,raw=req('GET','/api/status',None,plain)
            self.assertEqual(code,200);self.assertIn('connections',json.loads(raw))
            self.assertEqual(json.loads(raw)['connections'],{'github':True,'mcp':0,'folders':1})
        finally:httpd.shutdown();httpd.server_close();thread.join()

    def test_file_tab_reads_writes_and_needs_permission(self):
        import urllib.parse
        # Filfanens adgang: læsning kræver kun token, skrivning kræver Rediger filer
        self.assertFalse(server.file_access({})['edit'])
        self.assertTrue(server.file_access({'edit':'1'})['edit'])
        self.assertTrue(server.file_access({'full':'1'})['edit'])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'projekt'/'workspace';(root/'sub').mkdir(parents=True)
            (root/'sub'/'note.txt').write_text('hej verden',encoding='utf-8')
            (root/'skjult.py').write_text('x=1',encoding='utf-8')
            (root/'.hemmelig').write_text('ikke med',encoding='utf-8')
            (root/'billede.png').write_bytes(b'\x89PNG\r\n\x1a\n')
            (root/'stor.txt').write_bytes(b'a'*1_000_001)
            httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
            def req(method,path,body=None,headers=None):
                conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
                conn.request(method,path,body,headers or {'Host':'127.0.0.1:5000'})
                res=conn.getresponse();out=(res.status,res.read());conn.close();return out
            plain={'Host':'127.0.0.1:5000'}
            auth={'Host':'127.0.0.1:5000','X-Luna-Token':server.TOKEN}
            try:
                with patch.object(server,'WORKSPACE',root), patch.object(server,'ROOT',root.parent):
                    # Træet: mapper først, skjulte filer udeladt, workspace øverst som rod
                    code,raw=req('GET','/api/files',None,plain)
                    self.assertEqual(code,403)
                    code,raw=req('GET','/api/files?path=',None,auth)
                    self.assertEqual(code,200)
                    top=json.loads(raw)
                    self.assertEqual(top['dirs'],['sub'])
                    self.assertEqual([f['name'] for f in top['files']],['billede.png','skjult.py','stor.txt'])
                    self.assertEqual(top['roots'][0],{'name':'workspace','path':''})
                    # Projektmappen er også en rod — der ligger Lunes egne filer
                    self.assertEqual(top['roots'][1],{'name':'projekt','path':str(Path(temp)/'projekt')})
                    code,raw=req('GET','/api/files?path='+urllib.parse.quote(str(root.parent)),None,auth)
                    self.assertEqual(code,200);self.assertIn('workspace',json.loads(raw)['dirs'])
                    code,raw=req('GET','/api/files?path=sub',None,auth)
                    self.assertEqual(json.loads(raw)['files'][0]['name'],'note.txt')
                    # Filen åbnes som tekst — billeder og for store filer gives pænt afslag
                    code,raw=req('GET','/api/file?path=sub/note.txt',None,auth)
                    self.assertEqual(code,200);self.assertEqual(json.loads(raw)['content'],'hej verden')
                    code,raw=req('GET','/api/file?path=billede.png',None,auth)
                    self.assertEqual(code,400);self.assertIn('ikke tekst',json.loads(raw)['error'])
                    code,raw=req('GET','/api/file?path=stor.txt',None,auth)
                    self.assertEqual(code,400);self.assertIn('1 MB',json.loads(raw)['error'])
                    code,raw=req('GET','/api/file?path=findes-ikke.txt',None,auth)
                    self.assertEqual(code,400)
                    # Gem uden Rediger filer → afvist; med → skrevet
                    body=json.dumps({'path':'ny.txt','content':'nyt indhold'})
                    code,raw=req('POST','/api/file',body,auth)
                    self.assertEqual(code,400);self.assertIn('Rediger filer',json.loads(raw)['error'])
                    self.assertFalse((root/'ny.txt').exists())
                    code,raw=req('POST','/api/file',json.dumps({'path':'ny.txt','content':'nyt indhold','edit':'1'}),auth)
                    self.assertEqual(code,200)
                    self.assertEqual((root/'ny.txt').read_text(encoding='utf-8'),'nyt indhold')
                    # En sti uden for workspace OG projektmappe kræver Fuld adgang
                    udenfor=Path(temp)/'anden.txt';udenfor.write_text('hemmelig',encoding='utf-8')
                    code,raw=req('GET','/api/file?path='+urllib.parse.quote(str(udenfor)),None,auth)
                    self.assertEqual(code,400)
                    code,raw=req('GET','/api/file?path='+urllib.parse.quote(str(udenfor))+'&full=1',None,auth)
                    self.assertEqual(code,200);self.assertEqual(json.loads(raw)['content'],'hemmelig')
            finally:
                httpd.shutdown();httpd.server_close();thread.join()

    def test_browser_tab_iframe_allowed_by_csp(self):
        # Browser-fanen viser sider i en iframe — Lunes egen CSP må ikke spærre dem,
        # mens al anden streng beholdes
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
            conn.request('GET','/',None,{'Host':'127.0.0.1:5000'})
            res=conn.getresponse();res.read()
            csp=res.getheader('Content-Security-Policy','')
            conn.close()
            self.assertIn('frame-src',csp)
            self.assertIn('https:',csp)
            self.assertIn("script-src 'self'",csp)
            self.assertIn("frame-ancestors 'none'",csp)
        finally:
            httpd.shutdown();httpd.server_close();thread.join()

    def test_webcheck_reports_frame_policy(self):
        # En enkel server med den angivne ramme-politik
        def start(headers):
            class Roelig(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200);self.send_header('Content-Type','text/html')
                    for navn,vaerdi in headers:self.send_header(navn,vaerdi)
                    self.end_headers();self.wfile.write(b'<html><body>ok</body></html>')
                def log_message(self,*args):pass
            srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),Roelig)
            th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
            return srv,th
        # Hver politik og hvad tjekket skal svare
        tilfaelde=[
            ([],True),                                                    # ingen politik → tilladt
            ([('X-Frame-Options','DENY')],False),
            ([('X-Frame-Options','SAMEORIGIN')],False),
            ([('Content-Security-Policy',"frame-ancestors 'self'")],False),
            ([('Content-Security-Policy',"frame-ancestors 'none'")],False),
            ([('Content-Security-Policy','frame-ancestors https://eksempel.dk')],False),
            ([('Content-Security-Policy','frame-ancestors *')],True),
        ]
        for headers,forventet in tilfaelde:
            srv,th=start(headers)
            try:
                svar=server.webcheck('http://127.0.0.1:%d/'%srv.server_port)
                self.assertIs(svar['tilladt'],forventet,headers)
                if not forventet:
                    self.assertTrue(svar['besked'])                      # der står en forklaring på dansk
                    self.assertEqual(svar.get('arsag'),'spærret')        # Luna ved DETTE er en ramme-skræmme
            finally:
                srv.shutdown();srv.server_close();th.join()
        # En adresse der slet ikke findes er en anden sag — og skal ikke åbnes i Firefox
        with patch('socket.getaddrinfo',side_effect=socket.gaierror(-2,'Name or service not known')):
            svar=server.webcheck('https://dette-domaaene-findes-ikke.dk/')
            self.assertIs(svar['tilladt'],False)
            self.assertEqual(svar.get('arsag'),'ikke-fundet')
            self.assertIn('ikke fundet',svar['besked'])
        # Endepunktet browseren bruger giver det samme svar — og kræver token
        mini,mini_th=start([('X-Frame-Options','DENY')])
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=15)
            conn.request('POST','/api/webcheck',
                         json.dumps({'url':'http://127.0.0.1:%d/'%mini.server_port}).encode(),
                         {'Host':'127.0.0.1:5000','Content-Type':'application/json',
                          'X-Luna-Token':server.TOKEN})
            res=conn.getresponse();body=json.loads(res.read());conn.close()
            self.assertEqual(res.status,200)
            self.assertIs(body['tilladt'],False)
            conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
            conn.request('POST','/api/webcheck','{}',
                         {'Host':'127.0.0.1:5000','Content-Type':'application/json'})
            self.assertEqual(conn.getresponse().status,403);conn.close()
            # Ugyldige adresser afvises FØR noget hentes
            for daarlige in (None,'','ftp://eksempel.dk/','http://','x'*3000):
                with self.assertRaises(ValueError):
                    server.webcheck(daarlige)
            # Et svar der ikke kan tolkes (her HTTP 403 fra Luna's eget Host-tjek) → ukendt
            svar=server.webcheck('http://127.0.0.1:%d/'%httpd.server_port)
            self.assertIsNone(svar['tilladt'])
            self.assertIn('HTTP 403',svar['besked'])
        finally:
            mini.shutdown();mini.server_close();mini_th.join()
            httpd.shutdown();httpd.server_close();thread.join()

    def test_subagent_runs_read_only_and_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'workspace';root.mkdir();(root/'notat.txt').write_text('hemmelig 42')
            payloads=[]
            def fake(endpoint,payload=None,timeout=600):
                payloads.append(payload)
                if len(payloads)==1:
                    return {'message':{'role':'assistant','content':'','tool_calls':[
                        {'function':{'name':'read_file','arguments':{'path':'notat.txt'}}},
                        {'function':{'name':'write_file','arguments':{'path':'ny.txt','content':'x'}}},
                        {'function':{'name':'delegate','arguments':{'agent':'igen','task':'gentag'}}}]}}
                return {'message':{'role':'assistant','content':'Fandt svaret: 42'}}
            with patch.object(server,'WORKSPACE',root), patch.object(server,'ollama',side_effect=fake):
                access=server.access_for({'agents':True,'tools':True,'edit':True})
                out=server.run_agent({'agent':'efterforsker','task':'Find tallet i notat.txt'},access)
                self.assertIn('Fandt svaret: 42',out)
                self.assertIn('efterforsker',out)
                first,second=payloads[0],payloads[1]
                names=[t['function']['name'] for t in first['tools']]
                self.assertEqual(names,['list_files','read_file'])
                self.assertNotIn('delegate',names)
                self.assertNotIn('write_file',names)
                self.assertIn('SUB-AGENT',first['messages'][0]['content'])
                self.assertEqual(first['messages'][1]['content'],'Find tallet i notat.txt')
                self.assertEqual([t['function']['name'] for t in second['tools']],['list_files','read_file'])
                tooltext='\n'.join(m.get('content','') for m in second['messages'] if m['role']=='tool')
                self.assertIn('hemmelig 42',tooltext)
                self.assertEqual(tooltext.count('må en subagent ikke bruge'),2)
                # opgaven afkortes før den sendes videre
                server.run_agent({'agent':'a','task':'x'*9000},server.access_for({'agents':True}))
                self.assertEqual(len(payloads[-1]['messages'][1]['content']),server.AGENT_TASK_LIMIT)
                # budget: højst MAX_AGENTS opgaver pr. samtale
                budget=server.access_for({'agents':True});budget['_agents']=[0]
                for _ in range(server.MAX_AGENTS):
                    self.assertIn('svarede',server.run_agent({'agent':'a','task':'opgave'},budget))
                with self.assertRaises(ValueError):server.run_agent({'agent':'a','task':'opgave'},budget)
                spent=server.run_tool('delegate',{'agent':'a','task':'x'},budget)
                self.assertTrue(spent.startswith('Værktøjsfejl') and 'Højst' in spent)
                fresh=server.access_for({'agents':True})
                self.assertTrue(server.run_tool('delegate',{'agent':'a','task':' '},fresh).startswith('Værktøjsfejl'))
                self.assertTrue(server.run_tool('delegate',{'agent':'a','task':'x'},server.access_for({})).startswith('Værktøjsfejl'))

    def test_subagent_approval_flow_in_chat(self):
        calls={'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'delegate','arguments':{'agent':'koder','task':'Skriv en test til filen'}}}]}}
        sub={'message':{'role':'assistant','content':'Her er testen.'}}
        done={'message':{'content':'Færdigt.'}}
        with patch.object(server,'ollama',side_effect=[calls,sub,done]) as model:
            data={'messages':[{'role':'user','content':'Delegér noget'}],'agents':True,'tools':True,'confirm':True}
            first=server.chat(data)
            self.assertIn('pending',first)
            self.assertEqual(first['pending'][0]['name'],'delegate')
            self.assertIn('subagent koder',first['pending'][0]['title'])
            self.assertEqual(model.call_count,1)
            result=server.confirm({'id':first['pending_id'],'approve':[True]})
            self.assertEqual(result['answer'],'Færdigt.')
            self.assertEqual(model.call_count,3)
            sub_payload=model.call_args_list[1].args[1]
            self.assertEqual([t['function']['name'] for t in sub_payload['tools']],['list_files','read_file'])
            self.assertIn('SUB-AGENT',sub_payload['messages'][0]['content'])
            self.assertEqual(sub_payload['messages'][-1]['content'],'Skriv en test til filen')
            self.assertEqual(model.call_args_list[2].args[1]['messages'][-1]['role'],'tool')
            self.assertEqual(result['tools'][0]['name'],'delegate')
        # slukkes knappen, må modellen ikke delegere
        with patch.object(server,'ollama',return_value=calls):
            with self.assertRaises(RuntimeError):server.chat({'messages':[{'role':'user','content':'delegér'}]})
        # afvisning udfører intet
        with patch.object(server,'ollama',side_effect=[calls,{'message':{'content':'Okay, intet delegeret.'}}]) as model:
            first=server.chat({'messages':[{'role':'user','content':'Delegér'}],'agents':True,'confirm':True})
            result=server.confirm({'id':first['pending_id'],'approve':[False]})
            self.assertEqual(result['answer'],'Okay, intet delegeret.')
            self.assertEqual(model.call_count,2)

    def test_subagent_recovers_when_the_model_only_thinks(self):
        seen=[]
        def fake(endpoint,payload=None,timeout=600):
            seen.append(payload)
            if len(seen)<=2:
                return {'message':{'role':'assistant','content':'','thinking':'overvejelser...'}}
            return {'message':{'role':'assistant','content':'Svar: 42'}}
        with patch.object(server,'ollama',side_effect=fake):
            out=server.run_agent({'agent':'koder','task':'find tallet'},server.access_for({'agents':True}))
        self.assertIn('Svar: 42',out)
        self.assertEqual(len(seen),3)
        self.assertFalse(seen[0]['think'])
        self.assertTrue(seen[1]['messages'][-1]['content'].startswith('Skriv kun slutresultatet'))
        # tænkning slås til for subagenter, når brugeren har bedt om det
        with patch.object(server,'ollama',return_value={'message':{'role':'assistant','content':'ok'}}) as model:
            access=server.access_for({'agents':True});access['_think']=True
            server.run_agent({'agent':'a','task':'en opgave'},access)
            self.assertTrue(model.call_args.args[1]['think'])

    def test_stop_and_streamed_chat(self):
        # 1) stream-stykker samles til det svar, resten af koden forventer
        def chunk(**kw):return json.dumps({'message':kw}).encode()+b'\n'
        message=server.assemble_chat([chunk(content='Hel'),chunk(content='lo',thinking='tænker'),
                                      chunk(content='!',tool_calls=[{'function':{'name':'list_files','arguments':{}}}])])['message']
        self.assertEqual(message['content'],'Hello!')
        self.assertEqual(message['thinking'],'tænker')
        self.assertEqual(message['tool_calls'][0]['function']['name'],'list_files')
        empty=server.assemble_chat([b''])['message']
        self.assertEqual(empty['content'],'')
        self.assertNotIn('thinking',empty)
        self.assertNotIn('tool_calls',empty)
        with self.assertRaises(RuntimeError):server.assemble_chat([b'{"error":"model x not found"}'])
        with self.assertRaises(RuntimeError):server.assemble_chat([b'ikke json'])
        with self.assertRaises(RuntimeError):server.assemble_chat([b'x'*100]*50000)
        # 2) STOP før kaldet: Stopped uden nogen netværksforbindelse
        server.STOP.set()
        try:
            with self.assertRaises(server.Stopped):server.ollama_chat({'model':'x','messages':[]})
        finally:
            server.STOP.clear()
        # 3) rigtig stream: samling virker, og et stop bryder forbindelsen med det samme
        class Slow(server.BaseHTTPRequestHandler):
            count,delay=6,0.05
            def log_message(self,*args):pass
            def do_POST(self):
                try:
                    self.send_response(200)
                    self.send_header('Content-Type','application/x-ndjson')
                    self.end_headers()
                    for i in range(self.count):
                        self.wfile.write(json.dumps({'message':{'role':'assistant','content':'ord%d '%i}}).encode()+b'\n')
                        self.wfile.flush()
                        time.sleep(self.delay)
                except (OSError,ValueError):
                    pass
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),Slow)
        threading.Thread(target=httpd.serve_forever,daemon=True).start()
        try:
            with patch.object(server,'OLLAMA_PORT',httpd.server_port):
                full=server.ollama_chat({'model':'x','messages':[]})
                self.assertEqual(full['message']['content'],'ord0 ord1 ord2 ord3 ord4 ord5 ')
                # En pause over et halvt sekund må ikke ødelægge HTTP-læsningen.
                Slow.count,Slow.delay=2,0.8
                delayed=server.ollama_chat({'model':'x','messages':[]},timeout=5)
                self.assertEqual(delayed['message']['content'],'ord0 ord1 ')
                Slow.count,Slow.delay=300,2.0
                timer=threading.Timer(0.4,server.STOP.set);timer.start()
                started=time.time()
                try:
                    with self.assertRaises(server.Stopped):server.ollama_chat({'model':'x','messages':[]})
                    self.assertLess(time.time()-started,3)
                finally:
                    timer.cancel()
        finally:
            server.STOP.clear()
            httpd.shutdown();httpd.server_close()
        # 4) /api/stop og et afbrudt svar over HTTP
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        def req(method,path,body=None,headers=None):
            conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
            conn.request(method,path,body,headers or {'Host':'127.0.0.1:5000'})
            res=conn.getresponse();out=(res.status,res.read());conn.close();return out
        headers={'Host':'127.0.0.1:5000','X-Luna-Token':server.TOKEN,'Content-Type':'application/json'}
        try:
            self.assertEqual(req('POST','/api/stop','{}',headers)[0],200)
            self.assertTrue(server.STOP.is_set())
            server.STOP.clear()
            self.assertEqual(req('POST','/api/stop','{}',{'Host':'127.0.0.1:5000'})[0],403)
            with patch.object(server,'ollama',side_effect=server.Stopped('x')):
                code,raw=req('POST','/api/chat',json.dumps({'messages':[{'role':'user','content':'hi'}]}),headers)
            self.assertEqual(code,200)
            self.assertEqual(json.loads(raw)['answer'],'Afbrudt.')
            self.assertFalse(server.STOP.is_set())
        finally:
            server.STOP.clear();httpd.shutdown();httpd.server_close();thread.join()

    def test_long_conversation_drops_the_oldest_messages(self):
        # Over CHAT_LIMIT: de ældste beskeder falder ud i stedet for at afvise brugeren
        samtale = []
        for i in range(12):
            samtale.append({'role': 'user', 'content': ('spørgsmål %d ' % i) + 'x' * 4000})
            samtale.append({'role': 'assistant', 'content': ('svar %d ' % i) + 'y' * 4000})
        samtale.append({'role': 'user', 'content': 'den sidste besked'})
        with patch.object(server, 'ollama', return_value={'message': {'content': 'OK'}}) as model:
            svar = server.chat({'messages': samtale})
            self.assertEqual(svar['answer'], 'OK')
            sendt = model.call_args.args[1]['messages']
            self.assertEqual(sendt[0]['role'], 'system')
            indhold = [m['content'] for m in sendt[1:]]
            self.assertEqual(indhold[-1], 'den sidste besked')          # den nye besked kom med
            self.assertNotIn('spørgsmål 0', indhold)                   # den ældste faldt ud
            self.assertLess(len(sendt), len(samtale) + 1)
            self.assertLessEqual(sum(len(c) for c in indhold), server.CHAT_LIMIT)
            options = model.call_args.args[1]['options']
            self.assertEqual(options['num_ctx'], 20480)
            self.assertEqual(options['num_predict'], 10240)             # ~40.000 tegn (3,9 tegn/token)
            # En enkelt besked, der alene er for lang, afvises stadig
            with self.assertRaises(ValueError):
                server.validate([{'role': 'user', 'content': 'x' * (server.CHAT_LIMIT + 1)}])

if __name__=='__main__':unittest.main()
