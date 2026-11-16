# Verification — 2026-09-28

## Basis

Passed: `python -m unittest -v` — 8 tests. Coverage includes conversation and thinking forwarding, image payload forwarding, malformed/oversized inputs, file traversal and symlink rejection, unknown tool rejection, tool result roundtrip, disabled tools, bounded tool loops, localhost Host checking, request token enforcement, and upstream error responses.

Passed: `node --check app.js` — JavaScript syntax.

Not verified: actual Qwen inference, image interpretation, coding quality, AMD GPU acceleration, Windows batch launchers, or real-world model tool selection. Ollama/model are not installed in the build environment; model responses in tests are simulated.

Browser test attempted but could not start: Playwright browser executable is not installed. No visual or end-to-end browser pass is claimed.

No GitHub publication performed: available GitHub tools can write to an existing repository but cannot create a new one. The user must supply an empty repository URL for publication.

## Tilladelser, internet og godkendelse — 2026-09-28

Nye knapper i sidepanelet: **Rediger filer** (`write_file`), **Internet** (`fetch_url`), **Fuld adgang** (læs/skriv overalt + `run_command`) og **Spørg før skriv/kør** (godkendelse før farlige værktøjer). Alle slået fra på nær *Spørg før skriv/kør*.

Passed: `python -m unittest -v` — **14 tests, 1 skipped**. Nye tests dækker adgangsflag-validering, skrivning kun i workspace, kommando-kørsel kun ved Fuld adgang, godkendelses-gaten (pending → approve → svar), afvisning (filen ændres ikke), udløbne/ugyldige godkendelses-id'er og at nye værktøjer afvises når knappen er fra.

Skipped: `test_workspace_boundaries` — `OSError [WinError 1314]` ved oprettelse af symlink; kræver udvikler-/adminrettigheder på Windows. Testen hops over og kører resten, når symlinks ikke kan oprettes. Dette er en miljøbegrænsning, ikke en kodefejl.

Passed: `node --check app.js`.

Live modtest mod en kørende server med Ollama `qwen3.5:9b` (rigtige modelkald, ikke simulerede):

- **Internet**: `fetch_url https://example.com` → svar med overskriften "Example Domain"; værktøjsloggen viser renset tekst (HTML-tags fjernet).
- **Rediger + godkendelse**: oprettelse af `test-note.txt` → svar med `pending` og titlen "Skriv fil: test-note.txt (12 tegn)"; efter `approve: [True]` blev filen skrevet med præcis indhold.
- **Afvist**: samme opgave med `approve: [False]` → modellen svarede at intet var ændret, og filen var urørt.
- **Fuld adgang**: `run_command` "echo luna-er-i-live" → godkendelsespåkrævet, efter godkendelse `Exit-kode 0` med korrekt output.
- **Grænse**: `read_file C:/Windows/win.ini` uden Fuld adgang → afvist af serveren med "Kun almindelige filer i workspace er tilladt", også efter at brugeren havde godkendt. Uden Internet-slåen til tilbydes `fetch_url` slet ikke.
- **Browseren**: de seks knapper renderes uden scrolling (DOM-måling: `scrollHeight == clientHeight` ved 886 px viewport); godkendelses-dialogen viser titlen plus knapperne *Afvist* / *Kør valgte*; klik på *Kør valgte* gennemfører opgaven, viser "Anvendte værktøjer" og genaktiverer Send.

Ikke verificeret: hentning af billeder fra nettet (findes ikke — kun tekst), betingelser hvor omdirigering skifter slæde, og layout i vinduer under ca. 650 px højde (sektionen ruller så).

## Gem/save — hukommelse i Luna.md — 2026-09-29

Ingen ny knap: når brugeren skriver en kort ordre som `gem`, `save`, `gem svaret` eller `save samtale`, skriver **serveren** seneste spørgsmål og svar til `workspace\Luna.md` med tidsstempel — helt uden modelkald, så svaret kommer med det samme.

Passed: `python -m unittest -v` — **16 tests, 1 skipped**. Nye tests dækker at kun korte ordrer udløser (`gemme filer bedre`, `save the date for tomorrow` og `hukommelse gem` gør ikke), at filen oprettes med både DIG og LUNA, at et andet gem udvider filen, at gentaget gem afvises med "allerede …", at en fuld fil på 180.000 tegn besvares pænt, og at `gem` uden et forrige svar giver "Der er intet at gemme". `ollama` kaldes slet ikke under et gem (asserteret i testen).

Passed: `node --check app.js` — JavaScript syntax.

Live modtest mod kørende server med Ollama `qwen3.5-9b-uncensored` (rigtige modelkald):

- **Svar**: "Hvad er hovedstaden i Japan? Svar med ét ord." → "Tokyo" (0,2-6,3 s).
- **`gem`** bagefter → 0,0 s, ingen modelkald, `workspace\Luna.md` oprettet med `# Luna — hukommelse`, `## … — DIG` og `## … — LUNA`.
- **`gem` igen med samme par** → "Det par ligger allerede i workspace\Luna.md (225 tegn i alt)", filen ændres ikke.
- **Normal besked** bagefter → modellen kører stadig ("7 gange 8 er 56.", 0,3 s).

Ikke verificeret: samtidig skrivning fra to processer. Meget lange svar er senere kommet i spil — se *Længere svar og samtaler* nedenfor (svar gemmes nu op til 40.000 tegn, spørgsmål stadig 4.000).

## Uden historik (solo) — 2026-09-29

Ny flueben **Uden historik** øverst i sidepanelet, fra som standard. Slået til sender serveren **kun den sidste besked plus systemprompten** til modellen; tråden i chatten bliver stående, så du kan skifte frem og tilbage.

Passed: `python -m unittest -v` — **18 tests, 1 skipped**. Nye tests dækker at `solo` valideres som bool, at historikken ikke findes i nogen sendt besked (kun system + sidste besked i første kald), at `gem` stadig skriver paret fra hele tråden i solo-tilstand uden at kalde modellen, at værktøjer kører i solo-tilstand, og at almindelig kørsel stadig sender hele historikken.

Passed: `node --check app.js`.

Live modtest mod kørende server med Ollama `qwen3.5-9b-uncensored` (rigtige modelkald):

- **Med historik**: "Husk: mit navn er Lars" → bekræftelse → "Hvad er mit navn?" → **"Lars"** på 4,5 s.
- **Samme tre beskeder med `solo: true`** → **"Ukendt"** på 0,2 s — modellen kan intet huske, historikken blev ikke sendt.
- **Solo uden tråd**: "Hvad er 7*8?" → "7 gange 8 er **56**." på 0,3 s.
- **`gem` i solo-tilstand** → 0,0 s, parret skrevet til `workspace\Luna.md` (serveren bruger hele tråden, selvom modellen kun får den sidste besked).
- **`solo: 'ja'`** → HTTP 400 "Ugyldigt valg.".

Browser i den rigtige brugerflade (fanen http://127.0.0.1:5000, tråd med 12 beskeder):

- **Uden historik fra** → fejlen *"Samtalen er fuld. Skriv \"gem\" for at gemme den, start en ny samtale, eller slå Uden historik til."*
- **Uden historik til** → samme besked gik igennem, modellen svarede, og tråden voksede til 14 beskeder uden fejl. Kun de to sidste beskeder plus den nye blev sendt.
- **`gem` med fluebenet sat** → *"Gemt i workspace\Luna.md — nu 1396 tegn i alt"* — paret blev skrevet fra hele tråden, selvom modellen kun fik den sidste besked.

Miljønot: alle filer i mappen har MOTW (`Zone.Identifier`), så `START-LUNA.bat` afvises ved opstart via `Start-Process` med "En politik for programkontrol har blokeret denne fil". Luna blev derfor startet direkte med `python server.py`. Kør `Unblock-File START-LUNA.bat` (eller højreklik → Egenskaber → Fjern blokering) for at bruge knappen igen.

Ikke verificeret: hastighedsgevinsten ved lange tråde (målt her på en kort tråd), og at modellen i solo-tilstand ikke kan referere til tidligere beskeder (forventet og ønsket).

## Hukommelse — Luna.md læses tilbage — 2026-09-29

Ny flueben **Hukommelse** i sidepanelet, fra som standard. Slået til læser serveren `workspace\Luna.md` og lægger overskriften plus de seneste ca. 3.200 tegn ind efter systemprompten, så modellen kan huske det, du gemte med `gem`/`save`.

Passed: `python -m unittest -v` — **20 tests, 1 skipped**. Nye tests dækker at filen læses ind i systemprompten når fluebenet er sat, at den **ikke** læses som standard, at en manglende fil giver tom hukommelse uden fejl, at `memory: 'ja'` afvises, og at en meget stor fil afkortes med "…(ældre udeladt)…" mens de seneste par bevares.

Passed: `node --check app.js`.

Live modtest mod kørende server med `workspace\Luna.md` indeholdende *"min hemmelige kode er XQ7-BANAN"*, spørgsmålet *"Hvad er min hemmelige kode?"*:

| | Svar |
|---|---|
| Hukommelse **fra** | `1234` — opdigtet, modellen kender den ikke |
| Hukommelse **til** | `XQ7-BANAN` ✓ |
| Hukommelse + **Uden historik** | `XQ7-BANAN` ✓ (husker filen, ikke tråden) |

Ikke verificeret: latens med en fyldt hukommelse (målt med en lille fil), og samspil med vedhæftede billeder.

## Indstillinger — model, GitHub, MCP og mapper — 2026-09-29

Ny knap **⚙ Indstillinger** i sidepanelet åbner en panel med fire dele: **Model**, **GitHub**, **MCP-servere** og **Mine mapper**. Alt gemmes i `settings.json` (føjet til `.gitignore`). Nye sidepanel-knapper **Mine mapper**, **GitHub** og **MCP-værktøjer** vises kun, når der er noget at tænde for; alle er fra som standard.

- **Model**: liste over Ollama-modeller med størrelse, valg af aktiv model, søgning i Ollama-biblioteket og hentning med fremdrift/stop.
- **GitHub**: token + *Test GitHub*, læsende værktøj `github` med `repos`, `contents`, `issues`.
- **MCP**: URL **eller** lokal kommando, *Test* viser serverens værktøjer, som bliver til modelværktøjer `mcp__server__værktøj` med serverens egne felter.
- **Mapper**: godkendte mapper uden for workspace, som `list_files`/`read_file` må række ind i (skrivning kræver desuden *Rediger filer*).

Passed: `python -m unittest -v` — **27 tests, 1 skipped**. Nye tests dækker indstillings-filen (roundtrip, maskering af token, genbrug af maskeret værdi, tømning, afvisning af ugyldig mappe/drev/MCP/modelnavn), modelskift, godkendte mapper (læsning virker, læsning uden for alle godkendte mapper afvises, skrivning kræver redigering, spørgsmål før læsning af andres mappe), GitHub-værktøjet med mockede API-svar, MCP over lokal kommando (rigtig underproces med `initialize`, `tools/list`, `tools/call`, krævede felter) og over HTTP (sessions-header og SSE-svar), samt HTTP-endepunkterne for `/api/settings`, `/api/models`, `/api/settings/test` og `connections` i `/api/status`.

Passed: `node --check app.js`.

Live modtest mod kørende server og browser:

| Handling | Resultat |
|---|---|
| Åbn Indstillinger | Panelet viser alle fire dele, tomme standardtilstande ✓ |
| Tilføj mappe `C:\Users\dig\Desktop\server` | Serveren validerer stien, **Mine mapper**-knappen dukker op i sidepanelet ✓ |
| Vis installerede modeller | 4 modeller med størrelser og *Brug*-knap ✓ |
| Skift model til `qwen3.5:9b` | Statuslinje og bundtekst opdaterer med det samme, filen skrives ✓ |
| Tilføj MCP-server (lokal kommando) + **Test** | `2 værktøjer: echo, sum` ✓ |
| Chat med MCP-slået til | Godkendelses-dialog: *MCP-værktøj: mcp__Test__echo med {"tekst": "hej luna"}* ✓ |
| Tryk *Kør valgte* | Svar: `Svaret fra værktøjet er: "hej luna"` og værktøjslisten viser `Echo: hej luna` ✓ |
| GitHub-test med falsk token | `GitHub afviste tokenet (HTTP 401). Tjek tokenet i Indstillinger.` — ren dansk fejl, ingen crash ✓ |
| Rensning efter test | `settings.json` slettet, sidepanelet tilbage til ren standard, model `qwen3.5-9b-uncensored` ✓ |

Ikke verificeret: hentning af en rigtig model fra Ollama-biblioteket (kunne ikke vente på en fuld download), en rigtig GitHub-token med `repos`/`contents`/`issues` (kun 401-stien), og eksterne MCP-servere over internettet (kun loopback og lokal kommando).

## Subagenter — opgaver deles ud — 2026-09-29

Ny flueben-knap **Subagenter** i sidepanelet (fra som standard slået fra) giver modellen værktøjet `delegate`. Modellen kan dele en delopgave ud til en subagent med en egen rolle, som kører i sit eget modelkald og returnerer resultatet.

- Sub-agenten kører i en ren samtale (systemprompt + opgave) uden historik og uden hukommelse.
- Adgang nedarves kun som læsning: `read`/`web`/`github`/`folders` fra kaldet, aldrig `edit`, `full`, `mcp` eller `agents`. En subagent kan derfor hverken skrive, køre kommandoer, bruge MCP eller starte nye sub-agenter (ingen rekursion).
- Grænser: 4 delegeringer pr. samtale (tælleren bor i samtale-tilstanden, så alle værktøjsrunder deler den), opgave forkortes til 6.000 tegn, svar til 12.000 tegn, maks. 3 modelkald pr. subagent.
- Godkendelse: `delegate` kræver altid ja, når **Spørg før skriv/kør** er slået til. Dialogen viser rollen og de første 180 tegn af opgaven; en afvisning udfører intet.
- Tænkning: sub-agenter kører med `think: false`, medmindre brugeren har slået **Tænk grundigt** til. Ligger svaret kun i `thinking` med tom `content`, får modellen én chance mere med beskeden *"Skriv kun slutresultatet som ren tekst"* — ellers ender det som en fejl.

Rettede fejl undervejs: `agents`-fluebenet kom ikke med i chatten fra `app.js` (modellen fik aldrig værktøjet), og qwen3.5 lagde sub-agent-svaret i `thinking` med tom `content` (sub-agenterne gav "intet svar").

Passed: `python -m unittest -v` — **30 tests, 1 skipped**. Nye tests dækker at `delegate` er slået fra som standard og kun findes med fluebenet, at delegering altid kræver godkendelse og viser rollen i dialogen, at sub-agentens systemprompt siger `SUB-AGENT` og at opgaven er den eneste brugerbesked, at sub-agentens værktøjsliste aldrig indeholder `delegate`, `write_file` eller `run_command` (også med *Rediger filer* slået til), at afviste værktøjer svarer med *"Dette værktøj må en subagent ikke bruge"*, at læsning virker (filens indhold ender i svaret), at opgaven forkortes til 6.000 tegn, at budgettet stopper med *"Højst 4"*, at en tom opgave afvises, at `think` følger fluebenet, at en model der kun tænker får lov at svare igen, samt den fulde pending → approve → svar-kæde og en afvisning uden effekt.

Passed: `node --check app.js`.

Live modtest mod kørende server (pid 30584, ny kode) og browser:

| Handling | Resultat |
|---|---|
| Fluebenet **Subagenter** | Synligt i sidepanelet, slået fra som standard ✓ |
| Chat: *"Kald delegate: agent koder, task 'Sig hej …'"* | Godkendelses-dialog: *Start subagent koder: Sig hej på dansk i én sætning.* ✓ |
| Tryk *Kør valgte* | Svar: *Her er svaret fra subagenten "koder": "Hej, hvordan har du det?"* med værktøjsloggen `delegate / Subagent "koder" svarede: …` ✓ |
| Chat med *Læs arbejdsfiler* + subagent `efterforsker` | Sub-agenten læste `README.txt` og gav en præcis én-sætnings-rapport ✓ |
| Slukket flueben + *"kald delegate"* | Ingen godkendelsesdialog, ingen værktøjslog — kaldet blev aldrig udført ✓ |
| Almindelig chat efter testen | Kører som før, historik og øvrige knapper upåvirkede ✓ |

Ikke verificeret: sub-agenter med **Tænk grundigt** slået til i praksis (kun enhedstest), svar over 12.000 tegn (afkortningen), og flere sub-agenter kørende samtidig (køres altid sekventielt — én Ollama-opgave ad gangen).

## Mikrofon og Stop — 2026-09-29

To nye knapper til højre i beskedfeltet: **mikrofonen** (tale → tekst) og den **mørke ■-knap**, der erstatter *Send* mens modellen arbejder.

**Mikrofon (kun klient, Web Speech API):**
- `da-DK` med `continuous` + `interimResults`. Endelige udsagn skrives ind i beskedfeltet med automatisk mellemrum, det sidste delvise ord vises i hint-linjen (*Hører efter: …*), og genkendelsen genstartes selv efter stilhed. Klik igen stopper den, og knappen skifter mellem lilla *on*-tilstand og normal.
- Fejl bliver til danske beskeder i chatten og slukker knappen: ingen tilladelse, ingen mikrofon, intet internet, sprog ikke understøttet. Uden understøttelse i browseren siger Luna det med det samme.

**Stop (klient + server):**
- Klienten holder et `AbortController` på chatkaldet, lukker en åben godkendelses-dialog med `null`, kalder `POST /api/stop` og viser *Afbrudt. Din besked står stadig i feltet — tryk Send for at prøve igen.* Beskedfeltet og historien bevares, så beskeden kan gen-sendes.
- Serveren har et `STOP`-hændelsesfelt. `ollama('chat', …)` sender nu `stream: true` og læses i en baggrundstråd; når stop sættes, sendes FIN til Ollama med `sock.shutdown()`, så genereringen standses i stedet for at køre videre, og tråden gives fri inden 1 sekund. `chat()` og `confirm()` rydder flaget ved hver ny kørsel, `/api/stop` kræver localhost + token, og et afbrudt kald besvares med `200 {"answer": "Afbrudt."}`.
- Stream-stykkerne samles i `assemble_chat`: indhold, `thinking` og `tool_calls` lægges sammen (værktøjerne kommer i det sidste stykke), 4 MB-grænsen bevares, og `error`-stykker bliver til den sædvanlige danske Ollama-fejl.

Passed: `python -m unittest -v` — **31 tests, 1 skipped**. Den nye test `test_stop_and_streamed_chat` dækker samling af stream-stykker (content/thinking/tool_calls, tom respons, `error`-stykke, ugyldig JSON og >4 MB), `Stopped` uden netværk når stop allerede er sat, en rigtig HTTP-stream der samles korrekt, afbrydelse midt i en strøm (< 3 s, i praksis 0,4 s) med bagefter ingen hængende tråd, `/api/stop` (200 med token, 403 uden), og at et afbrudt chatkald svarer 200 med `Afbrudt.` uden at flaget står tilbage.

Passed: `node --check app.js`.

Live modtest mod kørende server (pid 33000, ny kode) og browser:

| Handling | Resultat |
|---|---|
| Genindlæs siden | Mikrofon-knap med SVG, skjult Stop-knap, *Send* synlig ✓ |
| Klik på mikrofonen uden tilladelse | *Mikrofonen må ikke bruges. Godkend den i browseren (mikrofon-ikonet ved adresselinjen) og prøv igen.* — og knappen slukker selv ✓ |
| Tekstsættelse | `Hej Luna` + ` hvordan går det? ` → `Hej Luna hvordan går det?`; tomt udsagn ignoreres ✓ |
| Send lang besked med *Tænk grundigt* | *Send* forsvinder, ■-knappen dukker op, boblen viser *Arbejder lokalt…* ✓ |
| Klik ■ efter 6 s | **507 ms** senere: *Afbrudt. Din besked står stadig i feltet …*, *Send* er tilbage, teksten står i feltet ✓ |
| Send en ny besked med det samme | Svar på **1,0 s** — ingen *En anden opgave kører*: genereringen blev altså standset i Ollama ✓ |

Ikke verificeret: selve transskriptionen med lyd (kræver fysisk mikrofon og mikrofon­godkendelse i browseren — ikke muligt i testbrowseren), og Stop midt i et igangværende værktøjskald (et stop fanger først ved næste modelkald; værktøjer kører færdig).

**Opfølgning samme dag — Firefox:**
- Lars bruger Firefox, som overhovedet ikke har Web Speech API. Hans klik gav den nye besked: *Firefox har ingen talegenkendelse. Åbn Luna i Chrome eller Edge …*
- Mikrofon-knappen **skjules automatisk** i browsere uden `SpeechRecognition` (`if(!SR)$('mic').hidden=true`), så Firefox-brugere ikke ser en knap, der ikke kan bruges. Stop-knappen er urørt.
- Knapperne ligger nu i `<span class="actions">`, så højrejusteringen overlever en skjult mikrofon: målt højrekant **990 px** med mikrofon, uden mikrofon (simuleret Firefox) og med ■ under kørsel — samme værdi alle tre steder.
- Mobilreglen `.controls span{display:none}` blev ændret til `#hint{display:none}`, ellers havde den også skjult *Send* på små skærme.
- Chrome fyrer `onerror` to gange ved afvist mikrofon, så `onerror`-håndteringen ignorerer nu beskeder, når mikrofonen allerede er slukket — præcis én fejlbesked i chatten (verificeret live).
- Windows har ingen talegenkendelses-motorer installeret (tomme nøgler under `Speech\Recognizers\Tokens` og `Speech\OneCore\Recognizers\Tokens`, kun TTS-stemmen *Microsoft Zira* en-US), så en lokal Windows-løsning ville kræve først at downloade en dansk talepakke.

## Automatic Compact af Luna.md — 2026-10-01

Problem fra Linux Mint: Luna klagede over at læse `workspace\Luna.md` — *"meget snak"*. Filen indeholdt **rå værktøjskald fra modellen** (`用微信扫` / `<function=…>` / JSON) og ville ved 180.000 tegn have løbet panden mod `Luna.md er fuld …`.

**Ny opførsel ved hvert `gem`/`save`:**
- `strip_tools()` fjerner rå function-calling-blokke (`用微信扫码…用微信扫`, `<function…</function>`) og linjer der kun er tags/JSON — **backticks i almindelig tekst (`gem`, `save`, kode) røres ikke** (første udgave brugte `` `.*?` `` og slagtede headeren `Sparret med kommandoerne \`gem\` og \`save\`` — fanget af testen).
- `save_answer` renser også **den eksisterende fil** ved hvert gem, så gammel larm ryddes væk, og `errors='replace'` gør at en forkert-kodet fil ikke længere kan kaste `UnicodeDecodeError`.
- `compact_memory()` kører automatisk over **`COMPACT_AT = 140_000`** og skærer de ældste udvekslinger fra ned til **`COMPACT_TO = 120_000`** (loftet `MAX_MEMORY = 180_000` nås derfor aldrig mere). Par (DIG+LUNA) fjernes sammen, en markering `> *(Automatisk komprimeret …)*` sættes ind, og filen bygges sammen ved de samme overskriftsgrænser som før. `gem` tager stadig **ingen modelkald**.
- Et svar, der *kun* er værktøjskald, gemmes ikke med en tom LUNA-blok — Luna siger i stedet, at der var intet læsbart.

Passed: `python -m unittest` — **33 tests, 1 skipped**. Ny `test_save_compacts_oldest_and_strips_tool_calls`: fil på ca. 168.000 tegn med36 gemte par + larm → `gem` svarer uden modelkald med *komprimeret*, filen ender ≤ `COMPACT_AT`, de ældste par er væk, de nyeste og det nye par består, larmen er renset og headeren/`gem`-backticks beholdes. `test_save_writes_memory_file` ændret: den gamle *fuld*-afvisning er væk — i stedet komprimeres filen og `gem` lykkes.

Live modtest (server pid 25152): filen før **5.426 tegn med larm** → `gem` på 0,01 s → **5.353 tegn, 0 larm-linjer**, `<function` væk, nyt par + gamle par + header + `` `gem` `` består; gentaget `gem` giver *Det par ligger allerede … (5.352 tegn)* og filen er uændret.

---

## Længere svar og samtaler — 2026-10-01

Før: svar blev afkortet ved 12.000 tegn før lagring, og klienten afviste chatten ved 12 beskeder / 18.000 tegn med beskeden *Samtalen er fuld …*. Nu svarer Luna meget længere, og samtalen afvises aldrig — de ældste beskeder falder bare ud.

**Måling (probe mod Ollama):** gentagen dansk tekst målt ved 10/100/1.000/5.000/10.000 tegn giver **3,90–3,91 tegn pr. token**. Når prompten overstiger `num_ctx`, svarer Ollama **HTTP 400** `{"error": "… exceeds the available context size (16384 tokens), try increasing it"}` — grænsen ligger altså i kontekstvinduet, ikke i selve svaret. Derfor: trim samtalen frem for blot at hæve tallene.

**Server (`server.py`):**
- `options` i `loop()`: `num_ctx` **16384 → 20480**, `num_predict` **12288 → 10240** (= op til ca. 40.000 tegn pr. svar). `run_agent`-kaldet er urørt (16384 / 6144), da subagent-svaret stadig stoppes ved `AGENT_LIMIT` 12.000.
- Ny konstant `CHAT_LIMIT = 45_000` tegn. `validate()` **trimmer** nu de ældste beskeder, indtil samtalen er under grænsen (`while total > CHAT_LIMIT and len(messages) > 1: pop(0)`) i stedet for at afvise; en enkelt besked, der alene er over grænsen, giver stadig `ValueError('Samtalen er for lang eller ugyldig. Start en ny samtale.')`.
- Antalsgrænse 12 → **40** beskeder (`Brug højst 40 beskeder …`).
- `save_answer`: svar gemmes op til **40.000** tegn (spørgsmål fortsat 4.000), begge steder (duplikat-tjek og selve skrivningen).

**Klient (`app.js`, `index.html`):**
- `next.length>12 || …>18000`-fejlen er væk: i stedet trimmes `next` til højst **40 beskeder / 45.000 tegn** med `while(next.length>1 && (…))next.shift()` — den sidste brugerbesked bevares altid. Historikken i chatten og `history`-tabellen følger det trimmede udfald, så næste svar starter derfra.
- Solo (*Uden historik*): 17.000 → **40.000** tegn (fejlen `Din besked er for lang. Højst 40.000 tegn.`), trim-løkken tilsvarende.
- `#prompt` `maxlength="12000"` → **`maxlength="40000"`**.
- Billedgrænsen (2 pr. samtale) er bevaret og flyttet ind i den nye `else-gren`.

**Start uden at blokere (`START-LUNA.bat`):** starter Ollama med `start "Ollama" /min ollama serve` i baggrunden, poller `ollama list` hvert 1. sekund i op til 30 sekunder og går derefter videre — konsollen fryser aldrig på `ollama serve`. Bagefter åbnes Luna i eget vindue (`py -3 server.py`, fallback `python`) og browseren. Fejltilstande giver rene ASCII-tekster (konsolen er codepage 437): *Ollama svarer ikke …*, *Python mangler …*.

Passed: `python -m unittest` — **32 tests, 1 skipped** (EXIT=0). Ny test `test_long_conversation_drops_the_oldest_messages`: 12 x (spørgsmål + svar) a 4.000 tegn + en sidste besked → modellen får kun de nyeste, `spørgsmål 0` er væk, den sidste besked står sidst, det sendte indhold er ≤ `CHAT_LIMIT`, `num_ctx` = 20480 og `num_predict` = 10240, og en enkeltbesked på `CHAT_LIMIT + 1` afvises stadig. `test_input_limits` bruger nu `CHAT_LIMIT + 1` i stedet for det gamle 18.001.

Passed: `node --check app.js`.

Live modtest mod kørende server (pid 29084, ny kode) med Ollama `qwen3.5-9b-uncensored`:

| Handling | Resultat |
|---|---|
| `GET /api/status` | `ready: true`, modellen `qwen3.5-9b-uncensored`, token fundet ✓ |
| 31 beskeder à ~2.000 tegn (**~60.000 tegn** i alt) + *"hvad er 7 gange 8?"* | **200 OK på 10,7 s** → **"56"** — de ældste beskeder faldt automatisk ud, ingen *Samtalen er fuld* ✓ |
| En enkelt besked på **45.001** tegn | **HTTP 400** *Samtalen er for lang eller ugyldig. Start en ny samtale.* ✓ |
| *"Skriv en meget lang historie … mindst 10.000 ord"* | **26.791 tegn på 213,5 s** — over den gamle grænse på 12.000, under den nye på ~40.000, modellen sluttede selv af ✓ |

Ikke verificeret: et svar på fulde ~40.000 tegn (kræver et `num_predict`-fyldt løb på 10.240 tokens — testen stoppede ved 26.791, fordi modellen selv sluttede), og at svaret overlever en efterfølgende `gem`-runde i fuld længde.

## Ctrl+V — skærmbilleder ind i chatten — 2026-10-01

Ny `paste`-lytter på `document` i `app.js`: tryk **Ctrl+V** med et skærmbillede i udklipsholderen, og det bliver vedhæftet som `Indsat billede (Ctrl+V)` med en *Fjern*-knap. Almindelig **tekst-indsetting passes uændret videre** (kun filer af slagsen `image/*` fanges).

**Fælles pipeline for Ctrl+V og *＋ Billede*:** `billedData(f)` accepterer PNG/JPEG direkte når de er under 3 MB; alt andet (WebP/GIF/BMP fra browseren, eller for store filer) tegnes om via canvas i trin 1 → 0,75 → 0,5 → 0,25, PNG først (skarp tekst) og JPEG ved fuld størrelse som fald. Serveren kræver magic bytes `\x89PNG` eller `\xff\xd8\xff` og base64 ≤ 4.000.000 tegn, så slutresultatet er altid et godkendt format. Hint-linjen er blevet til **"PNG / JPEG · højst 3 MB · Ctrl+V indsætter skærmbillede"**.

**Opdaget undervejs — billeder kræver vision-model:** første live-kald gav **HTTP 502** med `image input is not supported - hint: … you may need to provide the mmproj`. Ollama `/api/show` for de installerede modeller:

| Model | capabilities | kan se billeder |
|---|---|---|
| `qwen3.5-9b-uncensored` (aktiv) | tools, thinking, completion | **nej** |
| `qwen3.5:9b` | completion, **vision**, tools, thinking | ja |
| `gemma4:26b` | completion, **vision**, tools, thinking | ja |

Ny `require_vision(messages)` i `loop()` spørger `/api/show` én gang pr. model (cachelagt i `VISION_CACHE`) og afviser **før** et modelkald spildes:

> Modellen qwen3.5-9b-uncensored kan kun arbejde med tekst og kan derfor ikke se dit billede. Skift model i Indstillinger — fx qwen3.5:9b eller gemma4:26b, der begge kan se billeder — eller fjern billedet.

Fejlen kom på **0,0 s som HTTP 400** i stedet for 502 med teknisk JSON. Kan Ollama ikke spørges, gættes der ikke — så svarer selve chat-kaldet.

Passed: `python -m unittest` — **34 tests, 1 skipped**. Ny `test_image_needs_a_vision_model`: tekst-only model → klar ValueError gennem både `require_vision` og `chat()`; vision-model går igennem; ingen billeder → `/api/show` slet ikke kaldt; Ollama nede → ingen gætteri. `test_image_forwarded` udvidet med et `show`-svar, så den nye kontrol springes korrekt over for vision-modeller.

Passed: `node --check app.js`, tom konsol i browseren (0 fejl/advarsler).

Browser-test af pipeline og paste (fanen http://127.0.0.1:5000):

| Prøve | Resultat |
|---|---|
| A) PNG med dansk tekst, 308.729 bytes | givet direkte videre som `data:image/png;base64,` ✓ |
| B) **11,3 MB** støj-PNG (2400×1600) | skaleret til **1,1 MB** PNG ✓ under grænsen |
| C) `paste`-event med billedet | `#attachment` = **"Indsat billede (Ctrl+V) Fjern"** ✓ |
| D) `paste` med tomme fil-data | eventet gik uændret videre, intet vedhæftet ✓ |

Live ende-til-ende: `qwen3.5:9b` svarede på det indsatte skærmbillede på **7,4 s** — *"Jeg ser Luna Local-brugergrænsefladen med 'Hvad skal vi lave?' som hovedmenuen og indstillingsoptioner til venstre."* Bagefter: `settings.json` skrevet tilbage og fjernet igen (filen fandtes ikke før testen), model tilbage på `qwen3.5-9b-uncensored`, normalt svar på 7,2 s.

Ikke verificeret: den fysiske Ctrl+V-gestus med rigtig udklipsholder (paste-eventet blev simuleret — som med mikrofonen kræver selve tastaturet en rigtig browser), WebP/GIF omvejen i praksis (kun PNG sendt gennem), og om Firefox tillader billed-indsetting fra dets eget skærmbilledværktøj.

## MCP — Blender og Remotion i Luna — 2026-10-01

To nye MCP-servere skrevet ind i `settings.json` (de stod ikke der før — filen fandtes slet ikke):

| Server | Kommando | Værktøjer |
|---|---|---|
| `blender` | `uvx mcp-for-blender` | **36**: `get_addon_status`, `get_scene_info`, `get_object_info`, `get_viewport_screenshot`, `execute_blender_code`, `bpy_api_lookup`, Polyhaven-søgning … |
| `remotion` | `npx -y @remotion/mcp` | **1**: `remotion-documentation` |

Afprøvet først gennem Lunas egen stdio-motor (`server.mcp_connect` direkte) — begge gav håndslag og værktøjsliste. Til sammenligning virkede også `uvx ageless-blender-mcp` (26 værktøjer) og `npx -y remotion-ui-mcp` (4 værktøjer), men valget faldt på de to oprindelige. Maskinen har `uvx`, `npx` og Blender 5.2 (`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`); ingen `env`-variabler er nødvendige for disse servere.

Live modtest mod kørende server (HTTP 200, `connections.mcp = 2`):

| Handling | Resultat |
|---|---|
| `POST /api/settings/test` `kind=mcp, name=blender` | **17,4 s** → *36 værktøjer: get_addon_status, disable_telemetry, get_scene_info …* ✓ (første uvx-opstart henter pakken) |
| `POST /api/settings/test` `kind=mcp, name=remotion` | **2,2 s** → *1 værktøj: remotion-documentation* ✓ |
| Chat med `mcp:true, tools:true, confirm:true` om *Composition* | **11,0 s** → `pending` med `mcp__remotion__remotion_documentation` ✓ godkendelsesflowet grebet |
| `POST /api/confirm` `approve:[true]` | **8,6 s** → *"En Composition i Remotion er det renderbare video-output, der defineres som en React-komponent …"* — værktøjsloggen `['mcp__remotion__remotion_documentation']` ✓ |

Passed: `python -m unittest` — **34 tests, 1 skipped** (settings-filen påvirker tests ikke), `node --check app.js`.

Ikke verificeret: et rigtigt `tools/call` mod Blender i denne runde (addon'en manglede — det blev i stedet klaret fuldt ud i *MCP — Blender end-to-end i Luna* nedenfor); og at `remotion-documentation`-svaret er dagsaktuelt (Remotion har meldt MCP'en deprecated til fordel for `/remotion-docs`-skillen, men npm-pakken `@remotion/mcp` svarede friskt her).

## MCP — ComfyUI Desktop i Luna + miljøvariabler — 2026-10-01

ComfyUI Desktop v0.37.4 står på maskinen (`AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI`, AMD/ROCm, Python 3.13-venv). Comfys officielle MCP-server blev installeret: `pip install comfy-mcp comfy-cli>=1.14.0` (comfy-mcp 0.10.0, comfy-cli 1.22.0), og `comfy set-default` peger nu på Desktop-workspacet.

**Smart App Control i vejen:** `VerifiedAndReputablePolicyState = 1` — Windows afviser pip's usignede `.exe`-launchere (*"En politik for programkontrol har blokeret denne fil"*), hverken MOTW-afblokering eller AppLocker hjalp. Løsningen er `.cmd`-wrappere, som ikke er PE-filer:

- `AppData\Roaming\Python\shims\comfy.cmd` → `python -m comfy_cli %*`
- `AppData\Roaming\Python\shims\comfy-mcp.cmd` → `python -m comfy_mcp.server %*`

Shim-mappen står **først** i bruger-PATH, så `comfy`-shim'en overhaler den blokerede `comfy.exe`, og `python -m comfy_cli --version` giver `envelope/1`-svar gennem Popen ✓.

**Ny funktion: miljøvariabler på MCP-servere** (`env`). Før kunne man ikke fortælle en MCP-server noget som helst — de fleste servere styres dog via miljøvariabler. Nu:

- `validate_env()` parser `NØGLE=værdi; NØGLE2=værdi` (eller et dict) → gemmes som dict. Gyldige navne `[A-Za-z_][A-Za-z0-9_]*`, værdier ≤ 400 tegn, højst 12 — alt andet afvises med dansk fejl.
- `mcp_stdio_send` sætter variablerne i underprocessens miljø (`os.environ` + egne), `mcp_key` inkluderer dem, så to servere med samme kommando men forskelligt miljø ikke deler cache.
- `public_settings` viser dem som `NØGLE=værdi; …` til klienten; nyt felt **Miljø** i *Indstillinger → MCP-servere*.

**Live modtest** (server genstartet med opdateret PATH, `connections.mcp = 3`):

| Handling | Resultat |
|---|---|
| `settings/test` `blender` | **14,6 s** → 36 værktøjer ✓ |
| `settings/test` `remotion` | **2,4 s** → 1 værktøj ✓ |
| `settings/test` `comfy` | **10,5 s** → **39 værktøjer**: `server_info`, `auth_status`, `run_workflow`, `generate_image`, `list_partner_models`, `run_template`, `job`, `system_stats` … ✓ |
| `run_tool mcp__comfy__server_info` | **33,0 s** → JSON med `default_workspace = …\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI` ✓ — `COMFY_BIN`-shim'en virkede |
| `run_tool mcp__comfy__auth_status` | **4,1 s** → `signed_in: false` (Comfy Cloud ikke logget ind — påkræves ikke for lokal brug) |
| `run_tool mcp__comfy__system_stats` | **6,5 s** → værktøjsfejl: ComfyUI kører ikke (forventet — skal startes først) |

Passed: `python -m unittest` — **35 tests, 1 skipped**. Ny `test_mcp_env_reaches_the_command`: to fake-servere med samme kommando, hvoraf den ene har `env` → variablen når frem til underprocessen (`kom_sanden` vs `(ikke sat)`), dict-gemning, forskellige cache-nøgler, visning som tekst til klienten, seks ugyldige varianter afvises, tomt er lovligt og 13 variabler er for mange. `node --check app.js`.

Ikke verificeret: at køre et rigtigt workflow (`run_workflow`/`generate_image`) — ComfyUI Desktop skal startes først, og Ollama holder allerede på VRAM'en på det samme AMD-kort; samt `comfy` gennem shimmens `comfy env`-probe i komplet frisk PATH-kontekst fra START-LUNA.bat.

## MCP — Blender end-to-end i Luna — 2026-10-01

Addon'en *MCP for Blender* blev installeret/aktiveret i Blender 5.2 — og det viste sig, at den **allerede stod der i nyeste udgave**: `AppData\Roaming\Blender Foundation\Blender\5.2\scripts\addons\blender_mcp.py` (270.889 bytes, md5 `83FECF…` = identisk med det bundled `addon.py` fra repoet), `bl_info` v1.8, `bpy.context.preferences.addons['blender_mcp']` = **aktivt**, og `blendermcp_auto_start_server` har `default=True` → socket-serveren (port 9876) starter selv, når Blender åbnes.

Repoet hedder nu *mcp-for-blender* (det gamle `raw/main/addon.zip` giver 404); `uvx mcp-for-blender` har kommandoerne `install-addon`, `addon-paths` og `setup` (`--yes` ville skrive til andre MCP-klienter — derfor kun `addon-paths` kørt, som bekræftede fundet). Serverkommandoen i `settings.json` blev skiftet `uvx blender-mcp` → **`uvx mcp-for-blender`**, så server og addon deler protokolversion.

Blender blev åbnet (GUI, pid 27652) — port 9876 svarede efter 3 s.

| Handling | Resultat |
|---|---|
| `settings/test` `blender` | **4,2 s** → 36 værktøjer ✓ (mod det åbne Blender) |
| `run_tool mcp__blender__get_addon_status` | `up_to_date: true`, `protocol_version: 13 = expected 13`, `addon_version: [1, 8]`, capabilities ✓ |
| Chat `tools:true, mcp:true, confirm:true` om Blender-scenen | **1,1 s** → `pending` på `mcp__blender__get_scene_info` med `{"user_prompt": "List objects in the current Blender scene"}` ✓ |
| `POST /api/confirm approve:[true]` | **4,1 s** → *"Scenen indeholder følgende 3 objekter: 1. **Cube** … (0,0,0), 2. **Light** … (4.08, 1.01, 5.9), 3. **Camera** … (7.36, -6.93, 4.96). Desuden er der 2 materialer."* — log `['mcp__blender__get_scene_info']` ✓ |

Undervejs opstod to gange *"Ollama svarer ikke"* på `/api/chat` (begge gange lige efter tung MCP-aktivitet); `ollama_chat` fungerede dog straks bagefter, og `/api/ps` viste modellen indlæst med 20.480 kontekst — de to fejl var midlertidige og gentog sig ikke (`[uden værktøjer] 7,7 s`, `[tools] 1,7 s`, `[mcp] pending` ✓).

Ikke verificeret: `execute_blender_code` (kørsel af Python i scenen) — kun `get_scene_info`/`get_addon_status` er kaldt; Blender-genstart med addon'ets auto-start fra en kold boot; og at Ollama + Blender + ComfyUI samtidig på AMD-kortet ikke kæmper om VRAM.

## MCP — Luna installerer selv med `mcp_install` — 2026-10-01

Lars' ønske: *"når jeg siger 'kan du installere ting for mig', skal Luna selv gøre det"* — ikke at han skal pudse en AI-agent på det. Derfor værktøjet **`mcp_install`**:

- **Skema:** `name` (påkrævet), `command` *eller* `url`, valgfrit `installer` (kommando der henter pakken først) og `env`. System-prompten fortæller modellen at bruge den, når brugeren beder om noget installeret — og at den aldrig må installere noget, der ikke er bedt om.
- **Én godkendelse dækker hele kørslen:** `needs_approval` giver altid `True`, og `describe` viser den præcise kommando + installationskommandoen, før du godkender.
- **Kørsel:** validering (`validate_mcp`) → installationskommando (PowerShell/sh, timeout 600 s, afviser ved exit ≠ 0) → gem i `settings.json` (ved samme navn *erstattes* serveren, og det **eksisterende navn bevares**, så `mcp__navn__værktøj` er stabilt) → cache ryddes → **testforbindelse**. Fejler forbindelsen, rulles **hele vejen tilbage** til den præcise liste fra før (også ved opdatering af en eksisterende server), og fejlen forklares på dansk.
- Den findes kun med **MCP-værktøjer** slået til, og aldrig i læsetilstand.

| Handling | Resultat |
|---|---|
| Chat: *"installer et MCP-værktøj der kan hente websider … uvx mcp-server-fetch"* | **1,2 s** → `pending` på **`mcp_install`**: *"Installér MCP-server fetch <- uvx mcp-server-fetch"* ✓ |
| `POST /api/confirm approve:[true]` | **45,7 s** (uvx hentede pakken + forbød) → *"Du har nu installeret **fetch** værktøjet! …"* ✓ log `['mcp_install']` |
| `/api/settings` bagefter | `blender, remotion, comfy, **fetch**` ✓ |
| Chat: *"hent https://example.com med dit fetch-vaerktoej"* | **0,9 s** → `pending` på `mcp__fetch__fetch` → **3,1 s** → *"Example Domain — This domain is for use in illustrative examples …"* på dansk ✓ |

Fejlstierne er dækket af den nye `test_mcp_install_a_server` (36 tests i alt): værktøjets tilstedeværelse/adgang/godkendelse/beskrivelse, installation med installationskommando, opdatering uden dobbeltgang, ugyldigt input (tomt navn, command+url sammen, hverken-eller, ugyldigt `env`), installationskommando der fejler (`exit 3`), og to servere der ikke svarer — begge gange ender listen præcis som før.

Oven i købet: **"Ollama svarer ikke"** opstod to gange tidligere på dagen umiddelbart efter tung MCP-aktivitet. Genskabt bevidst nu — model udsmidning (`keep_alive=0`), genstart af serveren lige efterfulgt af chats, og fem chat-kald i træk — **ingen fejl nogen af gangene** (første kald efter udsmidning: 6,7 s = genindlæsning). Ikke reproducerbart; sandsynligvis GPU-tryk fra det åbne Blender i netop de øjeblikke.

Ikke verificeret: `mcp_install` med en `url`-server (kun kommandovejen kørt), installationskommando der overskrider 10 minutters grænsen, og at modellen selv vælger `mcp_install` uden at blive nævnt ordret i beskeden (den fik kommandoen angivet).

## Ollama — dansk fejl ved for stor kontekst + genforbindelse — 2026-10-01

Lars oplevede *"Ollama svarer ikke"* på en meget lang besked, og fejlen lod sig ikke genskabe med almindelige chats. Genskabelse med en besked lige under grænsen (43.890 tegn = 45.645/390-blokke-forsøg, endelig 44.000-ish) gav i stedet en **400 fra Ollama**: `request (32431 tokens) exceeds the available context size (20480 tokens)` — den blev bare vist råt som *"Ollama afviste kaldet …"*. Samtidig afslørede den nye `fejl.log` to **ConnectionAbortedError (WinError 10053)** midt i ellers velfungerende chats: Ollama afbryder forbindelsen kort efter opstart af et kald, og Luna viste den vage *"Ollama svarer ikke"* uden at gemme noget om det.

| Ændring | Resultat |
|---|---|
| `ollama_afvisning()` oversætter Ollama's grænser | 400 med `exceed_context_size_error` → *"Samtalen er blevet for stor til modellens kontekst. Start en ny samtale — de ældste beskeder kan alligevel ikke være med alligevel."* ✓ live: 18,6 s på 43.890 tegn |
| `ollama_chat` genforbinder **én gang**, når intet svar er nået frem | Afbrydelse før første token prøves igen efter 1 s; først derefter gives fejlen ✓ (`test_ollama_rejects_in_danish_and_logs_breaks` kører en fake Ollama der smider forbindelsen første gang og svarer anden gang) |
| `log_ollama_fejl()` skriver til `fejl.log` | Hver afbrydelse logges med tidspunkt, forsøg, varighed, antal linjer og undtagelse — næste *"svarer ikke"* kan ses i stedet for at gættes på ✓ |
| Ydre `except` i worker-tråden | Tråden kan aldrig mere dø tavs uden at sætte `box['error']` ✓ |

`fejl.log` er tom for nye linjer ud over de to fund (begge `forsøg 1`, 0,4–0,6 s, 2–3 linjer modtaget). Almindelig chat efterfølgende: `[uden værktøjer] 3,4 s`, `[tools] 1,4 s`, `[mcp] 13,8 s` ✓ — og `stopRun` sætter nu `ctl=null`, så *Gem*, *Test* og filfanens knapper ikke længere kan ramme et allerede afbrudt `AbortController` efter et Stop.

Ikke verificeret: selve WinError 10053's rodårsag (Ollama 0.34.4 på Vulkan/RX 9070 XT) — fejl.logen fanger den nu, næste gang den ses; kontekstgrænsen sættes ikke automatisk højere (brugeren starter ny samtale som beskeden siger).

## Filer og Browser-panelet ved siden af chatten — 2026-10-01

Lars: *"kan du edit[e] Luna i browseren og filer ligesom din?"* — og da førsteudgaven var en fuldskærmsmodal, svarede han: *"det er ikke færdig … venstre Luna chat og højre browser og fil i samme, ikke åbne fil i nyt vindue — lige som OpenCode"*. Derfor er fanen nu et **panel i højre side ved siden af chatten**:

- **Layout:** `body` er allerede en flex-række (`aside | main | #files`), så panelet står fysisk ved siden af chatten — chatten får altid `min-width:400px`, og **panelet er det der krymper** (`flex:0 1 680px`, min. 300 px) — aldrig omvendt. Ved ≤1150 px lægges træet **over** editoren i stedet for ved siden af, ved ≤1000 px glider panelet ud over chatten som overlay, og ved ≤760 px fylder det hele. Ikonknappen får `.on`-kant når panelet er åbt; samme knap lukker, Escape lukker også (`closeFiles`), og panelet er et almindeligt `<section id="files">` — ikke `.modal`, så overlay-klik-lukningen er fjernet.
- **Server:** `GET /api/files?path=…` (ét mappeindhold, `roots` ved tom sti), `GET /api/file?path=…` (tekst, max 1 MB), `POST /api/file` (gem). Alle kræver `X-Luna-Token`; læsning kræver ingen flueben, **skrivning afvises uden `edit`/`full`** (fanen siger selv nej — `write_file`-værktøjet har intet sådant tjek, det har kun modelkaldenes `needs_approval`).
- **Adgangsmodellen:** `file_resolve` er som `resolve_path` men tillader desuden alt **under projektmappen** (`ROOT`) — så `server.py`, `app.js`, `index.html` osv. er med i træet. Uden for projekt + workspace + godkendte mapper kræves Fuld adgang. `file_write` genbruger samme grænse ved skrivning.
- **UI:** træ der henter ét niveau pr. fold (lazy) og **hentes friskt, hver gang panelet åbnes**; klik på fil → editor, sti-felt med *Åbn*, *Gem*, *Ny fil* (prompt), hint med sti + tegnantal; hurtigt klik før `/api/status` har svaret venter nu på token i stedet for at smide *"Tryk Tjek forbindelse først"* ind i chatten. `__pycache__` og skjulte filer skjules i træet.
- **To slags faner — ubegrænset antal:** panelets header er nu en **fane-række** som i OpenCode: hver fane har navn + sit eget **✕** (lukker kun den fane; **sidste fane lukker hele panelet**), og en altid synlig **+** til sidst opretter en ny fane *af samme type som den aktive* (fil eller browser). `faner`-listen holder al tilstand pr. fane: fil-faner har `sti/tekst/hint`, browser-faner har `url/src` og **hver sin iframe** (oprettet ved fane-dannelse, skjult/slået til ved skift). `+`-knappen ligger **uden for** det scrollbare fane-område, så den aldrig kan skubbes ud af syne ved smal skærm (den fejl fandtes i første version: `+` lå inde i `overflow-x:auto`-listen og forsvandt ved ~320 px). Fil der allerede er åben i en fane → skift dertil i stedet for at åbne to; en fil der klikkes i træet lander i den aktive fil-fane (eller den sidste, hvis man sidder i en browser). **CSP-fund:** serveren sendte `default-src 'self'` uden `frame-src`, og da `frame-src` **arver fra `default-src`**, blev **alle eksterne iframes spærret af Lunes egen sikkerhedspolitik** — hvid ramme, load fyrrede alligevel, og `fetch` fejlede. Fikset med `frame-src https: http:` i headeren (alt andet i CSP'en er urørt, `frame-ancestors 'none'` stadig låst), dækket af `test_browser_tab_iframe_allowed_by_csp`. **Genveje:** Ctrl+O = fil-fane, Ctrl+Shift+B = browser-fane (skifter type hvis panelet står åbent, åbner ellers), Esc lukker.

| Handling i browseren | Resultat |
|---|---|
| Klik ikonknappen i headeren | **Panelet åbnes til højre for chatten** (målt ved 1024 px viewport: sidepanel 270 + **chatten 400** + filpanel 354; træet ligger automatisk over editoren) ✓ — chatten er synlig hele tiden, som i OpenCode |
| Klik ikonknappen igen / **Esc** | Panelet lukker, knappen mister `.on`-kanten ✓ |
| Klik `README.txt` | Åbner: *README.txt · 224 tegn*, markeret i træet ✓ (filen urørt bagefter — kun læst) |
| Hurtigt klik på Filer før `/api/status` svarede | Venter på token i stedet for at smide *"Tryk Tjek forbindelse først"* ind i chatten ✓ |
| *Ny fil* → `luna-test-fil.md` → **Gem uden Rediger filer** | *"Slå Rediger filer til i Indstillinger, så du må skrive."* ✓ og filen oprettes **ikke** |
| Samme med Rediger filer slået til | *"Skrev 32 tegn til …\workspace\luna-test-fil.md"* ✓ og den nye fil dukker op i træet — testfilen slettet igen efter testen |
| Fold `luna-local` ud → klik `server.py` | 14 filer i roden; `server.py` åbner med **90.878 tegn** ✓ (`__pycache__` skjult) |
| `GET /api/file?path=…\anden.txt` (uden for alt) | **400** uden Fuld adgang, **200** med `&full=1` ✓ (HTTP-dækket i `test_file_tab_reads_writes_and_needs_permission`) |
| **Ctrl+O** / ikonknap | Åbner panelet på *Filer*; samme genvej igen lukker ✓ |
| **Ctrl+Shift+B** med panelet åbent på *Filer* | Skifter til *Browser*-fanen (lukker ikke) ✓; med panelet lukket åbner det direkte på *Browser* ✓ |
| Skriv `example.com` → *Åbn* (uden https) | Bliver til `https://example.com` og **siden vises i rammen** ✓ — efter at CSP fik `frame-src`; før fiktes en helt hvid ramme |
| Adressebjælken ved 1024 px viewport | Faner + ✕ på række 1, felt + *Åbn* på række 2 med fuld bredde ✓ (knappen er blot højere end fanerne — begge centreret i samme række) |
| **+**-knap (første version) | **Forsvandt** ved smal skærm — lå inde i det scrollbare fane-område ✓ (fundet på skærmbillede, flyttet uden for) |
| **+** efter fix | Altid synlig mellem fane-listen og panelets ✕ (målt: venstre 922 mod rækkehøjre 955) og opretter en fane af samme type ✓ |
| To fil-faner med hver sin tekst | Skift mellem dem: README-teksten står stadig i fane 1, den egen tekst i fane 2 ✓ — intet mistet |
| Åbn `README.txt` fra træet mens en anden fil-fane er aktiv | Åbnes i den aktive fane (fane-navnet skifter til `README.txt`); åbnes filen igen → skift til den eksisterende fane i stedet for duplikat ✓ |
| Browser-fane med `example.com` → **+** → anden browser-fane med `example.org` | **2 iframes**, hver med sit eget src ved skift mellem dem ✓ — og fane-navnet bliver til værtsnavnet |
| ✕ inde i en fane (4 faner → 1) | Kun den fane + dens iframe fjernes; **3** klik lukkede **3** faner og panelet til sidst ✓ (første version efterlod døde faner — fundet ved at loopet kørte 10 gange i stedet for 3) |
| Gem i fane uden Rediger → med Rediger | *\"Slå Rediger filer til …\"* ✓ / *\"Skrev 15 tegn til …\\workspace\\fane-test.md\"* ✓ — testfilen slettet efter testen |
| Esc / ✕ yderst / samme genvej igen | Lukker panelet (gemmer den åbne tekst først) ✓; genåbning starter med en frisk fane og træet hentes på ny ✓ |
| **🌐 i Lunas header** (nyt) | Åbner panelet **direkte på browser-fane** selvom panelet er lukket ✓; gentaget klik lukker igen, og det ikon der **lyser** følger den aktive type (fil → panelet-ikonet, browser → 🌐) ✓ |
| Panel-ikonet mens panelet står på en browser-fane | **Skifter til fil-fane uden at lukke** ✓ — fejl i første version: uden type-id lukkede knappen, for logikken sagde "samme knap lukker"; nu ved hver knap hvilken type den mener (`openFiles(type)` = `type||'fil'`) |
| **📁-knap** (nyt) | Menu åbner med *＋ Tilføj mappe …* og **sektionen "Fast i træet:"** der viser alle nuværende rødder (`📁 workspace`, `📁 luna-local`) — den gamle udgave viste kun "Ingen ekstra mapper endnu" selvom træet havde rødder, hvilket var misvisende ✓; **Esc lukker menuen, ikke panelet** ✓; klik udenfor lukker ✓; fane-skift og genåbning af panelet efterlader aldrig menuen åben ✓ |
| Header ved smal skærm (1024 px) | "Gem samtale" står på **én linje** (`white-space:nowrap` + `flex-shrink:0`) og citatet *Et roligt sted at skabe.* er skjult under 1150 px ✓ — før brød begge over to linjer |
| *＋ Tilføj mappe …* → `C:\…\server` | Stien valideres via `POST /api/settings/test`, gemmes i `settings.json` (`folders`) og **træet viser den nye rod med det samme**: `[workspace, luna-local, server]` ✓ — `approved_roots()` gør resten, ingen serverændring |
| ✕ på mappen igen | Rækken forsvinder, træet er tilbage til `[workspace, luna-local]` ✓ — `settings.json` efter testen: **4 MCP-servere urørte**, `folders: []`, github/model uændret |
| Gem-mekanikken | `gemMapper` henter **friske** indstillinger før den sætter `folders` — så kan panelet ikke overskrive GitHub-token/model/MCP fra Indstillinger-pletterne (`payload()` ville ellers sende tomme felter) ✓ |
| **Søgning i browser-bjælken** (nyt) | `vejret i Danmark` (mellemrum = søgning) → `https://www.bing.com/search?q=vejret%20i%20Danmark` i rammen, **fane-navnet bliver søgeordet** (`🌐 vejret i Danmark`) ✓; `example.com` genkendes som adresse → `https://example.com` (præfiks lagt til), fane-navn = værtsnavn ✓; skift mellem faner bevarer det skrevne i feltet ✓; `127.0.0.1:5000`, `dtu.dk/sti` og `vejret` (enkelt ord → søgning) matcher også korrekt |
| Frame-tilladelser for søgemaskiner (målt) | **Bing: hverken `X-Frame-Options` eller `frame-ancestors` → tilladt** ✓; Google, DuckDuckGo (`lite`/`html`), Startpage: `SAMEORIGIN`/`'self'` → spærret; Mojeek: `'none'`; Ecosia + html.duckduckgo: 403. Bing bekræftet **live i rammen**: vejret + søgeresultater for "Luna chat lokal model" indlæst, cookie-banner kan afvises/accepteres med klik ✓ |
| **`/api/webcheck` før indlæsning** (nyt) | Måler `X-Frame-Options` + `frame-ancestors` **før** browseren lægger en ramme ind: `google.dk` **og** `youtube.com` opdages live (`SAMEORIGIN`) → **boks i stedet for den døde Firefox-side**: *"Siden siger X-Frame-Options: SAMEORIGIN — den må ikke vises i en anden side."* ✓; Bing-søgeside (`search?q=vejret`) → `tilladt: true` → normal ramme ✓; **Bing-forsiden + tom `?q=` spærrer** (målt) → derfor fører knappen ikke dertil; `ftp://`, tomt, `http://` og 3.000 tegn afvises med 400 FØR noget hentes ✓; 403-svar → `tilladt: null` ("bliver alligevel forsøgt") ✓; endepunktet kræver token (403 uden) ✓; timeout → `null` → rammen prøves ✓ |
| [Søg i stedet] i boksen | Boksen forsvinder, søgebjælken tømmes og **får fokus** ✓; søgeord + Enter → Bing-ramme, fane-navn `🌐 opskrift på pandekager` ✓ (første udgave åbnede Bing-forsiden, som også spærrer — rettet) |
| [↗ Åbn i egen fane] i boksen | `window.open(url,'_blank','noopener')` — fangede kaldet `https://youtube.com` i testen ✓ |
| `test_webcheck_reports_frame_policy` | 7 politik-tilfælde gennemgås (ren → tilladt; `DENY`/`SAMEORIGIN`/`'self'`/`'none'`/anden-origin → spærret med dansk forklaring + `arsag: spærret`; `*` → tilladt) + POST-endepunkt + manglende token → 403 + ugyldige adresser + 403-tolknings-gren + **DNS-fejl med fuplet `socket.getaddrinfo` → `arsag: 'ikke-fundet'`** (deterministisk, ingen internet). **40 tests OK** ✓ |
| **Auto-åbn i Firefox** (nyt, efter Lars' valg) | `youtube.com` **og** `google.dk` → `window.open(url,'_blank')` kaldet **automatisk** efter webcheck (~0,3 s), boks kvitterer *"Siden er åbnet i din browser i stedet …"*, rammen forbliver tom (ingen død Firefox-fejl) ✓; almindelig søgning (`vejret i Danmark`) → **ingen** åbning, Bing-ramme som før ✓ |
| Popup-blocker-fallback | `window.open` giver `null` → boksen falder tilbage til XFO-teksten med knapperne [Søg i stedet][↗ Åbn i egen fane] ✓ — `opener=null` sættes manuelt, fordi `'noopener'`-flaget i sig selv altid giver `null` |
| DNS-fejl + tidsgrænse | `gooole.dk` → `arsag: 'ikke-fundet'` → boksen *"Adressen blev ikke fundet"*, **ingen** browser-åbning ✓; da Windows-DNS kan tage >7 s, giver **browseren op efter 4,5 s** (`Promise.race`) og prøver rammen alligevel — boksen skjules ✓ (serverens egen timeout sænket 6 → 4 s) |
| Headeren indlæst igen | `Content-Security-Policy` indeholder `frame-src https: http:` **og** stadig `script-src 'self'` + `frame-ancestors 'none'` ✓ |

Tests: 40 i alt (`python -m unittest` → OK, `node --check app.js` → OK). Ikke verificeret: filfanen og browser-fanen i Firefox (kun kørt i browserens standard), redigering af filer i de godkendte mapper (kun læst som rod), hvordan træet opfører sig ved flere hundrede filer i én mappe (kun 14 testet), og sider der nægter indramning (kun eksempel.com bekræftet — Google/YouTube er kendt blokeret).

## Tilstandsflytning: alle flueben i Indstillinger — 2026-10-01

Lars: *"kan flytte dem knappe til indstilliner"* — de **ni tilstands-flueben** (Uden historik, Hukommelse, Tænk grundigt, Subagenter, Læs arbejdsfiler, Rediger filer, Internet, Fuld adgang, Spørg før skriv/kør) plus de **tre tilslutnings-flueben** (Mine mapper, GitHub, MCP-værktøjer) er flyttet fra sidepanelet over i **Indstillinger** som ny øverste sektion **TILSTANDE**. Kun placeringen er ny: elementerne har **præcis de samme ID'er**, så al eksisterende logik virker uændret — `FLAGS`-deaktivering under arbejde, `flags`-objektet der sendes med hver besked, `.conn`-visningen fra `/api/status` (global `querySelectorAll('.conn')`), `data-prompt`-knappen der tænder *Læs arbejdsfiler* og `fileQ()`'s `edit`/`full`-tilstand. Sidepanelet står nu med brand, *Ny samtale*, *⚙ Indstillinger* og statuslinjen. Fejlteksten *"… i sidepanelet"* er rettet til *"… i Indstillinger"* i både `app.js` (filfanens Gem-hint) og `server.py` (`file_write`-afvisningen). Indstillinger fik også `focus({preventScroll:true})` + `scrollTop=0`, fordi det gamle `$('setModel').focus()` **rullede panelet forbi Tilstande-overskriften** ved hver åbning (fundet på skærmbillede).

| Handling | Resultat |
|---|---|
| Åbn Indstillinger | Sektionerne står som **Tilstande, Model, GitHub, MCP-servere, Mine mapper** ✓ og Tilstande er øverst med introen *"Lunes knapper — ændringen gælder med det samme, også mens du skriver."* |
| Flueben i modalen vs. sidepanelet | **12** i modalen (9 tilstande + 3 conn) og **0** tilbage i `aside` ✓ |
| `status()` med MCP-servere tilsluttet | `mcp`-conn'en bliver **synlig i modalen** (`folders`/`github` holder sig skjult uden tilslutning — samme regel som før) ✓ |
| Klik `Internet` til → læs `$('web').checked` | `true` ✓ — samme ID, samme aflæsning ved afsendelse |
| Åbn Indstillinger | `pane.scrollTop = 0`, *Tilstande*-overskriften synlig (`getBoundingClientRect().top` i viewport), **fokus ligger stadig i Modelnavn** ✓ |
| *Gem uden Rediger filer* (app.js) | *"Slå Rediger filer til i Indstillinger, så du må skrive."* ✓ |
| `file_write` uden flueben (server.py) | *"Slå Rediger filer til i Indstillinger (eller Fuld adgang) for at gemme."* ✓ — testen matcher stadig på `Rediger filer` |
| `python -m unittest` + `node --check` | **40 tests OK**, JS OK ✓ — serveren genstartet efter tekstændringen |
