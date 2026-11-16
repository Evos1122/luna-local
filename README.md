# Luna Local

En selvstændig lokal AI-chat med Ollama og Qwen3.5:9b. Standardmodellen er `qwen3.5-9b-uncensored`, oprettet fra en lokal GGUF-fil (se [Egen GGUF-model](#egen-gguf-model)), og kan skiftes med miljøvariablen `LUNA_MODEL`. Ikke en Astra-klon, ikke et OpenAI-produkt og ingen OpenAI-modelvægte. Projektet omfatter server og brugerflade; model og Ollama installeres separat.

## Start på Windows

1. Installer Python 3.10+ fra https://www.python.org/downloads/ og Ollama fra https://ollama.com/download/windows, hvis de mangler.
2. Pak hele mappen ud, eksempelvis som `Desktop\server\luna-local`. Behold din gamle server separat. Luk den gamle server, hvis den bruger port 5000.
3. Dobbeltklik **HENT-MODEL.bat** én gang. Downloaden er omkring 6,6 GB og henter basismodellen `qwen3.5:9b`. Internet kræves til installation og download. Vil du bruge din egen GGUF-fil, se [Egen GGUF-model](#egen-gguf-model).
4. Dobbeltklik **START-LUNA.bat**. Skriptet tænder selv Ollama i baggrunden (et lille vindue — det må ikke lukkes, så går Ollama ned igen), venter til modellen er klar og åbner derefter chatten på http://127.0.0.1:5000. Lad servervinduet og Ollama-vinduet stå åbne.

Ingen pip-installation, API-nøgle eller betalt AI-tjeneste er nødvendig. Lokal drift bruger din computers strøm og ressourcer. Koden sender modelkald til Ollama på 127.0.0.1:11434 og indeholder ingen analyse/telemetri. Internettet røres kun, når du selv slår Internet-knappen til; alt er fra som standard.

## Start på Linux (Linux Mint)

1. Installer Python 3 og Ollama: `sudo apt install python3` og `curl -fsSL https://ollama.com/install.sh | sh` (se https://ollama.com/download/linux).
2. Pak mappen ud, fx `~/luna-local`, og gør scripterne kørbare én gang: `chmod +x *.sh`.
3. Hent basismodellen med **`./hent-model.sh`** (omkring 6,6 GB, kræver internet).
4. Kør **`./start-luna.sh`**. Skriptet tænder Ollama i baggrunden, hvis den ikke allerede kører — på Mint kører `ollama` ofte som systemd-tjeneste, og så springes den del over — venter højst 30 sekunder, til den svarer, åbner chatten i browseren og starter serveren i samme terminalvindue. Stop med **Ctrl+C**.

`server.py` er platformneutral og bruges uændret begge steder; kun `START-LUNA.bat`/`HENT-MODEL.bat` er Windows-specifikke. Tælles eller placeres scripterne anderledes end `python3`, står der besked i stedet for et felt.

## Funktioner

- Dansk brugerflade, kodehjælp, kopiering og eksport til Markdown.
- Historik i den aktuelle fane: højst 40 beskeder / 45.000 teksttegn ved almindelig samtale (se *Uden historik* nedenfor). Rammes grænsen, falder de ældste beskeder automatisk ud — samtalen afvises aldrig. Ingen automatisk disk-lagring; eksportér før lukning.
- Skriv **`gem`** eller **`save`** som en kort besked (fx `gem`, `gem svaret`, `save samtale`) efter et svar, så skriver Luna spørgsmål og svar til `workspace\Luna.md` med tidsstempel — chatten bliver en hukommelse, der hober sig op. Kommandoen svarer med det samme uden modelkald, parret lægges kun ind én gang, og **automatic compact** holder filen læselig: rå værktøjskald fra modellen ryddes altid væk, og overstiger filen 140.000 tegn, skæres de ældste udvekslinger fra ved næste `gem` (med en markering i filen), så der altid er plads. Ingen knap; alt andet går til modellen som før.
- **Billeder og skærmbilleder:** tryk **Ctrl+V** for at indsætte et skærmbillede direkte fra udklipsholderen (eller brug *＋ Billede*). Højst to billeder på hver 3 MB pr. samtale. Alt andet end PNG/JPEG — og alt for stort — bliver automatisk tegnet om via canvas og skaleret, så det ender som PNG/JPEG under 3 MB, også for WebP/GIF fra browseren og kæmpe 4K-screenshots. Tekst-indsetting røres ikke. **Billeder kræver en model med vision:** `qwen3.5-9b-uncensored` er tekst-only og afviser billeder med en klar fejl — `qwen3.5:9b` og `gemma4:26b` kan begge se billeder (skift i *Indstillinger*).
- Valgfri tænkning med foldbar modeloutput-visning.
- Valgfrie modelstyrede værktøjer i slå-til-trin: læsning i workspace (`list_files`, `read_file`), redigering (`write_file`), internet (`fetch_url`) og Fuld adgang (læsning og skrivning overalt på maskinen plus `run_command`). Når der er tilslutninger i *Indstillinger* kommer også `github` og MCP-værktøjerne med, og `list_files`/`read_file` rækker ind i de godkendte mapper. Maksimum 16 værktøjsrunder pr. besked med fire kald i hver. Godkendelser nulstiller ikke grænsen. Når runderne er brugt, vises status og de seneste resultater, så du kan bede Luna fortsætte uden at sende hele installationsopgaven igen. Alle knapper er fra som standard.
- **Uden historik** er fra som standard: slå fluebenet til, og **kun den aktuelle besked** sendes til modellen — svaret kommer med det samme, modellen husker ikke de forrige beskeder, og tråden bliver stående i chatten. Slå det fra igen for en almindelig samtale. `gem`/`save` virker stadig, og værktøjer kører også. Grænsen på 40 beskeder / 45.000 tegn gælder kun, når fluebenet er fra — med **Uden historik** kan du fortsætte en fyldt samtale uden at starte forfra.
- **Hukommelse** er fra som standard: slå fluebenet til, og Luna læser `workspace\Luna.md` før hvert svar og lægger de seneste gemte udvekslinger ind i modellens kontekst. Kun de seneste ca. 3.200 tegn bruges, så konteksten aldrig fyldes. Filen fyldes med `gem`/`save` og renses for rå værktøjskald ved hvert gem, så Luna aldrig ser teknisk larm, når den læser sin egen hukommelse. Kan kombineres med *Uden historik* — så husker Luna filen, men ikke tråden.
- **Mikrofon** er knappen med mikrofon-mærket til højre i beskedfeltet. Tryk på den, og tal på dansk — ordene skrives ind i feltet, mens du taler (mellemrum sættes automatisk). Tryk igen for at stoppe. Kræver Chrome eller Edge, mikrofon og mikrofon­godkendelse i browseren; talegenkendelsen ligger i browseren og **kræver internet**, fordi den sender lyden til browserens udbyder. Mens den lytter, lyser knappen lilla, og feltet viser det ord, der netop blev hørt. Fejl (ingen tilladelse, ingen mikrofon, intet internet) bliver til én kort besked i chatten, og alt du har skrevet bliver stående. **Browseren bestemmer:** Firefox har slet ikke talegenkendelse, så der bliver knappen helt fjernet — åbn Luna i Chrome eller Edge (på Linux Mint: `chromium-browser`), hvis du vil diktere. I Chrome og Edge virker den på dansk uden at Windows behøver nogen talepakke installeret.
- **Stop** er den mørke firkant med ■, der erstatter *Send*, mens modellen arbejder. Tryk på den, og Luna bryder forbindelsen til Ollama med det samme — genereringen stopper i stedet for at køre i baggrunden — svarboblen bliver til *Afbrudt. Din besked står stadig i feltet*, og du kan sende en ny besked med det samme uden at vente. Også under en ventende godkendelse stopper knappen forløbet. Det halvfærdige svar forsvinder; skriv `gem` først, hvis du vil beholde noget.
- **Filer** er panelet-ikonet øverst til højre ved *Gem samtale* (og **Ctrl+O**). Det åbner et **panel i højre side, mens chatten stadig står synlig til venstre** (som i OpenCode) — ikke en rude der dækker skærmen. Panelet har **flere faner**: i en fil-fane ligger **filtræde øverst og editor nederst** (på brede skærme ved siden af hinanden), og **+** åbner en ny fane af samme slags, mens **✕** i fanden lukker den enkelte (sidste fane lukker hele panelet). **📁-knappen** i fane-rækken viser **de mapper der er rødder i træet**: *＋ Tilføj mappe …* spørger efter en fuld sti, tjekker den og lægger mappen som ny rod med det samme — og hver rad kan fjernes med ✕. Listen gemmes i `settings.json` som de samme *godkendte mapper* fra Indstillinger (så modellen også kan læse dem, når *Mine mapper* er slået til), og workspace + projektmappen står altid som rødder i forvejen. Som rødder ligger altså **workspace** og **projektmappen** (Lunes egne filer som `server.py`, `app.js` og `index.html`) plus dine egne. Klik en mappe for at folde den ud, og en fil for at åbne den — den får sin egen fane, hvis den ikke allerede står åben et sted, ellers skiftes der bare hen til den. Sti-feltet øverst åbner en vilkårlig fil direkte, og *Ny fil* opretter en i workspace. **Hver fane har sin egen tekst**, så du kan have to filer åbne side om side og hoppe mellem dem uden at miste noget. Læsning virker altid; **Gem kræver fluebenet Rediger filer** (eller Fuld adgang, som også slipper løs uden for projektmappe og workspace). Billeder og andre ikke-tekstfiler vises ikke, filer over 1 MB bliver afvist, og ud over de tre rødder kræver selv læsning Fuld adgang. Panelet lukkes med **Esc**, med ✕ yderst til højre eller ved at trykke samme genvej igen; træet hentes friskt, hver gang panelet åbnes. Chatten får altid mindst 400 px — på smalle skærme flytter panelet sig ud over chatten, og under 760 px fylder det hele. Ændringer i filpanelet er dine egne — modellen får ikke at vide, at filen findes, før den selv læser den.
- **Browser** er den anden slags fane i panelet — og den er **altid ét klik væk**: 🌐-knappen i Lunes header (ved siden af panelet-ikonet) åbner panelet direkte på en browser-fane, **🌐 Browser**-knappen i fane-rækken gør det samme fra panelet, og **Ctrl+Shift+B** er genvejen. Det ikon der lyser i headeren viser, om panelet står på fil (panelet-ikonet) eller browser (🌐). Skriv en adresse i bjælken (også uden `https://` — det lægges til af sig selv), tryk **Åbn** eller Enter, og siden vises i rammen nedenunder, mens chatten står ved siden af. **Bjælben kan også søge**: skriver du flere ord, fx *vejret i Danmark*, tolkes det som en søgning og sendes til **Bing** — en af de meget få store søgemaskiner, der overhovedet må vises i en ramme (det er målt: Google, DuckDuckGo, Startpage og Ecosia spærer det alle sammen). Skriver du derimod en adresse som `google.dk`, åbnes den som side. **Fane-navnet bliver søgeordet**, så du kan have flere søgninger åbne samtidig og kende forskel på dem. Nogle sider nægter at blive vist i en anden side (Google, YouTube og lignende) — så søg i stedet gennem Bing eller åbn adressen i din egen browser; det står også som en lille note under rammen. **Før en side lægges i rammen, tjekker serveren om den overhovedet må være der** (`POST /api/webcheck` læser sidens `X-Frame-Options` og `frame-ancestors`). Er svaret nej, **åbner Luna siden automatisk i en rigtig fane i din browser** — det er den eneste måde at vise den på — og boksen i panelet kvitterer: *"Siden er åbnet i din browser i stedet — den nægter at blive vist herinde."* Er din browser sat til at blokere automatisk åbning, falder boksen tilbage til sine to knapper: **[Søg i stedet]** lægger markøren i søgebjælken (skriv dit søgeord, så søger den på Bing — Bing's *søgeside* må godt, mens forsiden også spærrer) **og [↗ Åbn i egen fane]** der åbner siden i en rigtig fane i din browser. En adresse der slet ikke findes (en stavefejl som `gooole.dk`) åbnes derimod **ikke** i browseren — der kommer boksen med "Adressen blev ikke fundet" og de samme to knapper. Et langsomt tjek hænger aldrig panelet: svarer tjekket ikke inden for 4,5 sekunder, prøves rammen alligevel præcis som før webchecken fandtes. Siden i rammen er fuldstændig adskilt fra Luna: den kan ikke se din samtale eller Lunes filer. **Genveje som i OpenCode:** **Ctrl+O** åbner (og lukker) fil-faner, **Ctrl+Shift+B** åbner browser-faner — skifter til den rette type, hvis panelet allerede står åbent. **Esc** lukker først en åben 📁-menu, ellers hele panelet.
- **Spørg før skriv/kør** er slået til som standard: skrivning af filer, kørsel af kommandoer og læsning uden for workspace stopper op og viser præcis handlingen i chatten. Du kan godkende de enkelte handlinger, afvise dem alle eller — uden fluebenet — lade alt køre uden spørgsmål. En godkendelse udløber efter 15 minutter.
- **Subagenter** er fra som standard slået fra (fluebenet *Subagenter* under **Tilstande** i Indstillinger). Slår du det til, får modellen værktøjet `delegate`: den kan dele en delopgave ud til en subagent med en egen rolle (fx `efterforsker`, `koder`, `kritiker`). Sub-agenterne kører hver for sig i en ren samtale — kun den opgave, ingen historik — og sender resultatet tilbage til hovedmodellen, der samler tråden. En subagent må kun **læse** (`list_files`, `read_file`, `fetch_url` og `github`, når de øvrige flueben er til): aldrig skrivning, kommandoer, MCP eller nye sub-agenter, så den aldrig får mere magt end dig. Højst 4 delegeringer pr. samtale, opgaven forkortes til 6.000 tegn, svaret til 12.000 tegn og højst 3 modelkald pr. subagent. Delegering spørger altid først via den sædvanlige godkendelsesdialog, og sub-agenter tænker kun, når *Tænk grundigt* er slået til.
- Én modelopgave ad gangen. 20.480 konteksttokens og højst 10.240 outputtokens pr. modelkald — op til ca. 40.000 tegn pr. svar. Rammes grænsen for samtalen, falder de ældste beskeder automatisk ud, så modellen aldrig får for meget tekst; begge dele kan styres i `server.py` (`CHAT_LIMIT` og `options`).
- Status for Ollama og den installerede model, med modelnavnet skrevet i bunden af sidepanelet.

Anbefalet udgangspunkt for maskinen med RX 9070 XT 16 GB og 32 GB RAM. Faktisk GPU-brug og hastighed afhænger af Ollama-version, driver, billedstørrelse og kontekst. Ikke testet på denne Windows-maskine.

## Indstillinger

Knappen **⚙ Indstillinger** i sidepanelet åbner en faneblade-panel med fem dele: **Tilstande** (alle Lunes flueben — Uden historik, Hukommelse, Tænk grundigt, Subagenter, Læs arbejdsfiler, Rediger filer, Internet, Fuld adgang og Spørg før skriv/kør, som før stod direkte i sidepanelet, plus Mine mapper/GitHub/MCP når de er tilsluttet — ændringen gælder med det samme), **Model**, **GitHub**, **MCP-servere** og **Mine mapper**. Alt gemmes i `settings.json` ved siden af `server.py`; filen er føjet til `.gitignore`, så token aldrig ryger med i et Git-repo.

- **Model** — vælg blandt de modeller, Ollama har installeret, søg i Ollama-biblioteket på nettet og hent ny model med fremdrift og stop-knap. Tomt felt = standardmodellen (`qwen3.5-9b-uncensored`, eller `LUNA_MODEL`). Skiftet slår igennem med det samme.
- **GitHub** — læg et personligt adgangstoken (PAT) ind og tryk **Test GitHub**, som forbinder og gemmer dit brugernavn. Giver modellen værktøjet `github` med de læsende handlinger `repos`, `contents` og `issues`. Luna skriver aldrig til GitHub.
- **MCP-servere** — tilføj en adresse (URL) **eller** en lokal kommando, aldrig begge dele. **Test** viser navnene på de værktøjer, serveren tilbyder. Hver server omdannes til modelværktøjer med navnet `mcp__server__værktøj` og bevarer serverens egen beskrivelse og felter. Til lokale kommandoer kan du desuden udfylde **Miljø** med `NØGLE=værdi; NØGLE2=værdi` (højst 12) — de variabler bliver sat i det miljø serveren startes med, fx `COMFY_BIN=C:/sti/comfy.cmd`, så en server altid finder sin hjælpekommando, uanset hvad PATH siger.
- **Luna kan selv installere en MCP-server.** Når du skriver noget som *"installer et værktøj der kan …"*, bruger modellen selv værktøjet `mcp_install`: den kører evt. installationskommando først (`python -m pip install …` eller bare `uvx`/`npx`, som henter selv), skriver serveren ind i **Indstillinger → MCP-servere**, forbinder og fortæller, hvilke værktøjer der kom. **Én godkendelse dækker hele installationen**, og svarer serveren ikke, rulles alt tilbage — så du aldrig står med en død server på listen. Du ser altid den præcise kommando, der skal køres, før du godkender.
- **Mine mapper** — tilføj mapper uden for workspace (fuld sti, ikke hele drevet). Når en mappe er godkendt, kan Luna læse filer i den med `Læs arbejdsfiler` slået til; skrivning kræver også `Rediger filer`.

Sidepanelet viser kun knapperne **Mine mapper**, **GitHub** og **MCP-værktøjer**, når der faktisk er noget at tænde for. Alle tre er fra som standard.

Sådan er forbindelserne beskyttet:

- Tokenet sendes aldrig retur til browseren i klartekst. Panelet viser kun de sidste fire tegn, og serveren bevarer det gemte token, når du sender den maskerede værdi tilbage.
- GitHub-værktøjet er udelukkende læsende. Hvert MCP-kald stopper altid op og spørger dig, når **Spørg før skriv/kør** er slået til.
- Forbindelsen til en MCP-server genoprettes ved behov og huskes i fem minutter. Svarer serveren ikke, udstilles dens værktøjer slet ikke, og chatten fortsætter som før.
- En lokal MCP-kommando startes ny for hvert kald, så `npx`-servere kan tage et sekunder eller to. Adresse- og kommandoservere bruger samme JSON-RPC-protokol.
- **Fire servere er sat op i denne installation:**
  - `blender` → `uvx mcp-for-blender` (36 værktøjer, bl.a. `get_scene_info`, `get_object_info`, `get_viewport_screenshot`, `execute_blender_code`). Addon'en *MCP for Blender* v1.8 (`blender_mcp.py`) står installeret **og aktiveret** i Blender 5.2, og dens server auto-starter på port 9876, så snart Blender åbnes — der skal ikke trykkes noget. Blender skal bare køre; svarer det ikke, siger værktøjet *Could not connect to Blender*.
  - `remotion` → `npx -y @remotion/mcp` (Remotions dokumentation, værktøjet `remotion-documentation`). Virker med det samme.
  - `comfy` → `…\Python\shims\comfy-mcp.cmd` med miljø `COMFY_BIN=…\Python\shims\comfy.cmd` (39 værktøjer, bl.a. `server_info`, `run_workflow`, `generate_image`, `system_stats`). Kommandoerne kører gennem små `.cmd`-wrappere, fordi **Smart App Control** på maskinen afviser pip's usignede `.exe`-launchere. `comfy set-default` peger på ComfyUI Desktop-installationen. **ComfyUI Desktop skal køre**, før workflow-værktøjerne kan noget (`system_stats` fejler pænt ellers).
  - `fetch` → `uvx mcp-server-fetch` (1 værktøj, `fetch` — henter en webadresse som markdown). **Denne server installerede Luna selv** med `mcp_install`, da der blev bedt om den i chatten.

  Begge/tre tændes med fluebenet **MCP-værktøjer** under **Tilstande** i Indstillinger, og hvert kald kræver din godkendelse under *Spørg før skriv/kør*.
- Ved **Fuld adgang** kan modellen læse `settings.json` — som alt andet på maskinen. Lad *Spørg før skriv/kør* være slået til, så du ser hver handling først.

## Egen GGUF-model

Luna kalder Ollama ved **modelnavn**, ikke filsti. Derfor virker `MODEL = 'Model.gguf'` ikke — Ollama skal kende modellen først.

1. Lav en `Modelfile` med stien til din GGUF (brug din egen sti):

   ```
   FROM C:/Users/dig/Downloads/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf
   ```

2. Opret modellen (kopiér filen ind i Ollamas lager, ca. 9 GB):

   ```
   ollama create qwen3.5-9b-uncensored -f Modelfile
   ```

3. Start Luna. Statuslinjen i sidepanelet viser præcis det modelnavn, serveren leder efter.

Vælg altid en **kvantiseret** udgave (Q8_0, Q4_K_M …) til et grafikkort. En BF16-fil på 16,7 GB fylder hele et 16 GB-kort og tvinger lag ud i RAM, hvor Q8_0 på 8,9 GB bliver i VRAM og kører omkring 48 tokens/sekund på en RX 9070 XT.

Skift model uden at redigere koden: `LUNA_MODEL=qwen3.5:9b python server.py`. Filnavne som `Model.gguf` udelades af `.gitignore`, så de ikke ryger med i en GitHub-publicering.

## Begrænsninger

Modellen kan skrive forslag til kode. Med **Rediger filer** eller **Fuld adgang** kan den også oprette filer og køre kommandoer — men kun når den knap er slået til, og som standard først efter din godkendelse i chatten. Internet henter én tekstside ad gangen, højst 64 KB, uden billeder. Ingen garanti for Astra-niveau. Ingen cloud-fallback. Et modelkald har 10 minutters timeout; en værktøjsopgave kan kræve flere kald. **Stop-knappen annullerer et igangværende Ollama-kald med det samme**; lukning af fanen gør det ikke.

Serveren binder kun til localhost, kontrollerer Host og kræver et tilfældigt token ved chatkald. Den er til én lokal bruger og må ikke blot eksponeres på nettet. Workspace bør kun indeholde bevidst udvalgte filer; lokale programmer med samme brugerrettigheder er ikke isoleret fra hinanden. `settings.json` indeholder de tokens, du selv lægger ind, og bør aldrig deles — filen er føjet til `.gitignore`, så den ikke kan ende i et repo ved en fejl, men alle programmer med dine retigheder kan læse den.

**Fuld adgang giver modellen dine egne retigheder.** Den kan læse, overskrive og slette filer og køre kommandoer på hele maskinen. Slå den kun til til opgaver du selv stoler på, og lad *Spørg før skriv/kør* være slået til, så du ser hver handling før den køres. Internet-værktøjet henter kun http/https-sider og spærer cloud-metadata-adresser.

## Udvikling og test

`python -m unittest -v` kører 40 tests: HTTP-adgangskontrol, validering, filgrænser, Ollama-værktøjsforløb med simulerede modelsvar, `gem`/`save`, *Uden historik*, *Hukommelse*, indstillings-filen med maskerede tokens, godkendte mapper, GitHub-værktøjet, MCP over både lokal kommando og HTTP (inklusive sessions-header og SSE-svar), sub-agenter, Stop og stream-samling af modelsvar, dansk fejl ved for stor kontekst med automatisk genforbindelse ved afbrudte Ollama-svar, filfanens endpoints (læsning, skrivning og Rediger-kravet over HTTP) samt `webcheck` (sidens frame-tilladelser, DNS-fejl og token-tjek). Lang samtale trimmer automatisk (testen `test_long_conversation_drops_the_oldest_messages`). Start manuelt med `python server.py` eller `python3 server.py`.

## GitHub

Publicér kun denne projektmappe. .gitignore udelader brugerfiler under workspace. Gennemgå indholdet før upload; tag aldrig dine gamle servermapper, chats, modelfiler eller nøgler med. Denne levering er gjort klar til offentlig GitHub-publicering, men er ikke publiceret af assistenten.

Koden udgives under MIT. Qwen-modellen og Ollama har egne licenser; modelvægte følger ikke med.

## Referencer

- https://ollama.com/library/qwen3.5:9b
- https://docs.ollama.com/api/chat
- https://docs.ollama.com/capabilities/tool-calling



## Træk og slip filer

Tryk **＋ Vedhæft**, træk filer ind i Luna-vinduet, eller indsæt et kopieret screenshot med **Ctrl+V** i beskedfeltet. Vedhæftninger vises før afsendelse og kan fjernes enkeltvis. Tryk **Send** for at sende dem, eventuelt sammen med en besked.

- Billeder: PNG/JPEG, højst 3 MB pr. billede og to billeder pr. samtale. Modellen skal understøtte billeder.
- Tekst-/kodefiler: UTF-8, højst 12.000 tegn tilsammen og otte vedhæftninger pr. besked. Filernes tekst tæller med i samtalens eksisterende længdegrænse.
- PDF med tekst og Word (.docx): højst 3 MB pr. fil. Dokumenternes tekst tæller med i grænsen på 12.000 tegn samlet. Scannede PDF’er, gamle .doc-filer og ZIP understøttes ikke. Fejl fjerner ikke gyldige vedhæftninger.
- PDF-læsning kræver Popplers `pdftotext` på PATH (på Ubuntu: `sudo apt install poppler-utils`; på Windows skal Poppler installeres og dens bin-mappe føjes til PATH). Word kræver ingen ekstra pakker.
- Billeder og tekstfiler læses i browseren. PDF og Word sendes til Lunas lokale server, som udtrækker teksten; midlertidige PDF-filer slettes efter læsningen. Indholdet sendes som tekst eller billeder til den lokale chat; filerne kopieres ikke til workspace. Ved fejl bevares de til et nyt forsøg.

Browserkontrol: `python3 -m unittest test_attachments -v` (kræver Chrome eller Chromium, bruger simulerede modelsvar).


## Husk tilstande

Afkrydsningerne under **Indstillinger → Tilstande** gemmes automatisk i den aktuelle browser. De bevares ved **Ny samtale**, genindlæsning og næste besøg på samme Luna-adresse. Det gælder også **Fuld adgang** og **Spørg før skriv/kør**. Du kan ændre dem igen når som helst; første besøg bruger de hidtidige standardvalg. Valgene følger ikke med til en anden browser eller computer. Utilgængelige forbindelser er inaktive, men deres valg huskes, hvis forbindelsen bliver tilgængelig igen.
