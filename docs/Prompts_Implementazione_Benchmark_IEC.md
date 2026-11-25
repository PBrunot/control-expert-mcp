# Prompt di implementazione del benchmark IEC e del grader

Questi prompt sono destinati all'agente che sviluppa il repository, non al modello sottoposto a benchmark. Eseguirli in ordine, nella stessa conversazione oppure fornendo a ogni nuova sessione il contratto comune, la specifica e i risultati delle fasi precedenti. Il prompt 0 è utilizzabile anche come incarico completo; i prompt 1–7 suddividono il lavoro in consegne verificabili.

Fonte funzionale di progetto: [Specifica_Benchmark_IEC_Control_Expert.md](Specifica_Benchmark_IEC_Control_Expert.md), v0.1, con gli aggiornamenti concordati sotto. Il comando `ce-bench iec` è implementato; questi prompt descrivono le fasi di sviluppo e verifica.

Aggiornamenti concordati durante l'implementazione: lo starter è una copia del
demo M580 STU esistente, con hardware preservato; questa scelta sostituisce la
creazione di un progetto minimale. Usare namespace `IEC_<linguaggio>_` per
sezioni/variabili e mantenere la mappatura verso i nomi logici della specifica.
Il grader deve restituire anche la percentuale di celle di output corrette nelle
tracce valide e produrre un overview PNG/SVG con copertura e verdetti. Ogni
problema osservato deve essere valutato come possibile miglioramento condiviso
del server MCP, delle istruzioni o della diagnostica, oltre alla correzione del
benchmark. L'implementazione attuale è descritta in
[Benchmark_IEC_Implementation.md](Benchmark_IEC_Implementation.md).

## Contratto comune da anteporre a ogni prompt

```text
Lavora nel checkout corrente di control-expert-mcp. Leggi AGENTS.md e
docs/Specifica_Benchmark_IEC_Control_Expert.md. Implementa la fase richiesta:
non limitarti a proporre un piano. Prima di modificare, controlla git status;
preserva modifiche e file non tracciati dell'utente, compresa la specifica.

Riusa le convenzioni del checkout, senza presumere che documentazione storica,
esempi XML o firme COM dimostrino il supporto sul sistema installato.
Mantieni COM sul worker STA, write token, lock/taint e protezioni live.
Non avviare chiamate API a pagamento o operazioni live per il solo fatto che
stai sviluppando. Le prove offline devono restare senza provider, COM e OPC.
Le prove live richiedono i consensi espliciti previsti dal repository e un
target verificato PLC Simulator M580; non sostituirlo con un PLC fisico.
Riusa i consensi già acquisiti nella sessione senza richiederli nuovamente.
Non terminare processi né sostituire progetti aperti senza autorizzazione.

L'agente implementatore può leggere specifica, fixture e riferimenti. Il modello
valutato deve ricevere soltanto il contratto pubblico del caso e gli strumenti
ammessi: nessuna traccia, atteso, soluzione, progetto di riferimento o runner
strumentato. La separazione deve essere applicata alle capacità effettive dei
tool, non soltanto alle istruzioni del prompt.

Non inventare esiti live. Distingui implementato, testato offline, verificato
su CE 16.4/M580/OFS e bloccato. Un riferimento importato non dimostra authoring
LLM end-to-end. Se manca un prerequisito, completa il lavoro indipendente e
registra il blocco preciso senza aggirare il requisito.

Non eseguire il full DeepSeek suite come effetto collaterale: è una campagna
distinta, con regole proprie in AGENTS.md. Durante qualsiasi campagna mantieni
immutabili i fingerprint di sorgenti, configurazione, prompt e fixture.

A fine fase riporta file cambiati, verifiche effettivamente eseguite, risultati,
limiti e contratto consegnato alla fase successiva. Non creare commit o release
se non richiesti.
```

## Prompt 0 — Incarico completo

```text
Implementa il benchmark IEC della specifica e il relativo grader indipendente,
con tutti i cinque casi ST, LD, FBD, SFC e IL. Usa come percorso operativo le
fasi 1–7 di docs/Prompts_Implementazione_Benchmark_IEC.md, applicando il contratto
comune. Completa progressivamente codice, test e documentazione; esegui le
verifiche live soltanto quando prerequisiti e autorizzazioni sono disponibili.

Il risultato deve consentire selezione singola/all, preparazione delle copie,
authoring tramite MCP, acquisizione immutabile del candidato, verifica della
struttura, build, strumentazione affidabile, cattura nella MAST, confronto
tipizzato e report riproducibile. Il grader non dipende dalle dichiarazioni del
modello né dai suoi readback. Conserva gli esiti esatti della specifica.

Non dichiarare completata l'accettazione finché cinque riferimenti nativi,
seconda esecuzione pulita, cinque mutanti, lingua errata, timeout e isolamento
delle fixture non hanno le evidenze richieste. Se l'ambiente impedisce una parte,
consegna il codice verificabile e una matrice dei requisiti ancora non verificati.
```

## Prompt 1 — Ricognizione e contratti di integrazione

```text
Ricostruisci l'architettura reale del benchmark prima di fissare gli adattatori.
Leggi almeno benchmark/{cli,core,runner,tasks,transport,provider,opc,simulator,
report,archive,plot}.py sotto src/control_expert_mcp, i relativi test in tools,
benchmarks/README.md, server.py, prompts.py, i percorsi pertinenti di bridge.py,
schema.py e tools/lang_refs. Non aprire CE o connetterti a OFS in questa fase.

Produci docs/Benchmark_IEC_Implementation.md con:
- mappa dei requisiti della specifica verso componenti esistenti e nuovi;
- differenza tra ce-bench opc (fixture live/scalari) e simulator (authoring ST
  e contatore osservato dal client): nessuno dei due prova già il ciclo esatto;
- comando dedicato proposto ce-bench iec, operazioni prepare/validate/run,
  selettore --case all o uno dei cinque ID, modalità dry-run senza effetti live;
- contratti versionati di caso pubblico, fixture privata, manifest candidato,
  cattura PLC e risultato del grader; distingui status operativo e verdict;
- politica di authoring per linguaggio e dipendenze SFC consentite;
- confine di fiducia, allowlist di tool/percorsi/oggetti e fasi del lifecycle;
- controlli mancanti per CE 16.4, CPU M580, ordine MAST, reset, formato di
  scambio reale (anche ZEF), OFS e accesso simbolico ai buffer.

Riferimenti del checkout: core.load_config rifiuta chiavi sconosciute;
SimulatorMCP e LiveMCP hanno policy diverse; report/archive possono assumere
task e campi già noti. Proponi estensioni compatibili invece di duplicare tutto.
Un create_section o un esempio XML non equivale a un round trip verificato.
Definisci una matrice di capacità con stato unknown/verified/blocked e prova
necessaria; non assegnare verified sulla sola lettura del codice.
```

## Prompt 2 — Casi, fixture private e prompt pubblici

```text
Implementa i contratti della fase 1, per esempio in benchmark/iec_cases.py,
con separazione esplicita tra descrizione pubblica e fixture di valutazione.
Non rendere privati i dati soltanto attraverso il nome del file: il modello
non deve poterli leggere tramite strumenti, risorse o progetti aperti.

Trascrivi esattamente dalla specifica i cinque scenari ordinati: ST 10 vettori,
LD 11, FBD 12, SFC 13, IL 16. Ogni scenario conserva lo stato tra vettori.
Definisci lingua nativa, interfaccia con direzione e tipo, stato iniziale,
cicli per vettore (1, salvo SFC=4) e uscite valutate. Valida ID, nomi univoci,
dominio INT, BOOL, campi mancanti, numero/ordine dei vettori e tipi degli attesi.
Le rappresentazioni 0/1 delle tabelle BOOL devono diventare valori BOOL tramite
una conversione esplicita, senza equivalenza implicita bool/int di Python.

Genera il prompt del candidato soltanto da ID, lingua, interfaccia, requisito,
stato iniziale, contratto temporale e configurazione di strumenti prevista.
Non includere conteggi delle fixture private, mutanti, indici di fallimento o
estratti della specifica completa. Il progetto pubblico contiene variabili
precreate e sezione vuota, senza soluzioni o dati di valutazione.

Mantieni il prefisso Bench_ riservato al runner. Definisci gli eventuali helper
del candidato con nomi distinti e un manifest verificabile. Per SFC preserva il
requisito del chart nativo e i limiti degli helper ammessi.

Aggiungi test offline della trascrizione e della proiezione pubblica, inclusi
valori estremi ST e assenza dei dati privati nei payload inviati al provider.
Non limitarti a cercare numeri o parole: verifica l'origine dei campi esposti.
```

## Prompt 3 — Grader deterministico offline

```text
Implementa il grader puro, per esempio benchmark/iec_grade.py, senza dipendenze
da COM/OFS/provider. Riceve fixture privata, evidenze strutturali/build e una
cattura indipendente. Non esegue né interpreta il sorgente candidato per
dedurre le uscite; confronta i valori osservati dal simulatore.

Calcola correctness_percent = 100 * output corretti / output valutati, soltanto
per catture complete e attendibili. Mantieni il verdetto rigoroso separato dal
punteggio parziale; errori di infrastruttura, build o struttura hanno percentuale
null, non 0. Riporta denominatori e risultati per vettore.

Applica questa sequenza di decisioni documentata:
1. Percorso di authoring assente e verificato come tale: unsupported_authoring.
   Una consegna sbagliata su un percorso supportato non è questo esito.
2. Candidato con lingua, interfaccia o struttura errata: artifact_invalid.
3. Build effettivamente fallita per il candidato: build_failed. Un crash,
   timeout o contesto CE inaffidabile è infrastructure_error.
4. Cattura non affidabile/completa: infrastructure_error prima del confronto.
5. Traccia valida ma uscita errata: output_mismatch; altrimenti pass.

Non dedurre artifact_invalid dalla sola mancanza di evidenze causata da un
errore di trasporto. Definisci quali prove sono richieste per ogni decisione.
Valida identità di run/caso/artefatto strumentato, completamento, qualità OPC,
numero e ordine delle snapshot, indici di vettore/ciclo, ingressi applicati,
tipi e campi richiesti. Rifiuta duplicati, dati vecchi, buffer troncati e valori
non rappresentabili. Distingui dato OPC malformato da uscita funzionalmente
errata; un valore valido di tipo sbagliato non deve passare per coercizione.

Per ST/LD/FBD/IL confronta il ciclo 1 di ogni vettore; per SFC il ciclo 4.
Se i cicli intermedi SFC sono disponibili, conservali come diagnostica senza
imporre uscite intermedie non previste. La snapshot valutata al quarto ciclo
resta obbligatoria anche se la diagnostica intermedia non è disponibile.
Confronto esatto dopo decodifica esplicita dei tipi IEC, senza tolleranze.
Riporta tutte le discordanze disponibili e almeno la prima ordinata per
vettore/ciclo/uscita: indici da 1, ingressi, uscita, atteso e osservato.

Scrivi unittest che verifichino i sei verdict, incompletezza anche se i valori
presenti coincidono, run ID errato, ordine/duplicati, bool/int, qualità cattiva,
campionamento SFC e controlli sul linguaggio. Usa catture sintetiche etichettate
come tali: i test offline non certificano la semantica del simulatore.

Copri i cinque mutanti della specifica con prima divergenza attesa:
ST 6 (limite 999), LD 4 (Start prioritario), FBD 6 (rilascio >70),
SFC 3 (Start accettato con Done alto), IL 13 (OR invece di XOR).
Per SFC la divergenza valutata è al ciclo 4 del vettore 3.
Questi test verificano il grader; la compilabilità dei mutanti richiederà CE.
```

## Prompt 4 — Progetti nativi, authoring e acquisizione del candidato

```text
Implementa gli adattatori di progetto usando i contratti precedenti. Prepara
una copia del demo M580 STU per ciascun linguaggio, con interfaccia precreata e
sezione candidata vuota nel namespace IEC_<linguaggio>_. Preserva hardware e
logica originale; non creare CPU o configurazioni hardware. Non includere logica
di riferimento nella copia LLM.

Verifica, quando autorizzato e disponibile, create/import/export/analyze/build
su CE 16.4 per ST, LD, FBD, SFC e IL. Parti dagli esempi di tools/lang_refs e
dal riferimento linguistico MCP, ma inventaria il formato esportato realmente
dall'editor, dipendenze e variante XEF/ZEF. Le verifiche live sono sequenziali
sulla sessione CE protetta dal lock. Registra CPU, versione, comandi e risultati.

Se necessario estendi il percorso di authoring MCP, schema e workflow prompt
preservando worker STA e write token. Valida import e build; non creare un
fallback ST per un caso richiesto in lingua grafica o IL. Se manca un percorso
end-to-end, registra unsupported_authoring con il blocco specifico.

Acquisisci il candidato prima di costruire/caricare il progetto strumentato:
salva artefatto, export e manifest con hash, interfaccia, lingua, task/sezione e
helper ammessi. Verifica il linguaggio dal progetto/export, non dal nome o dai
commenti. SFC richiede chart nativo con passi, transizioni, azioni e dipendenze;
un chart ornamentale con una macchina a stati ST non soddisfa il requisito.
Definisci controlli concreti e conserva eventuali limiti della verifica.

Trasferisci solo la sezione e la chiusura delle dipendenze esplicitamente
ammesse nella copia privata di test. Rifiuta modifiche a Bench_, task, hardware,
configurazione e altre sezioni. Verifica anche alias, indirizzi sovrapposti e
scritture alle variabili del runner che possano falsificare la cattura.
Controlla la struttura dopo l'import; non fidarti del solo manifest candidato.
Conserva log di build e hash del progetto strumentato collegati al candidato.
Non committare archivi generati o binari vendor; usa directory locali ignorate.
```

## Prompt 5 — Cattura deterministica MAST e adattatore OFS

```text
Implementa l'acquisizione nel PLC, indipendente dalla soluzione candidata.
L'ordine effettivo nella stessa MAST deve essere:
applicazione dell'intero vettore -> candidato e helper ammessi -> snapshot.
Verifica l'ordine dal progetto/export. Per SFC la snapshot segue anche la
pubblicazione delle uscite e il vettore resta invariato per quattro cicli.

Precarica tutti gli ingressi privati prima dell'avvio; gli attesi rimangono
nel grader host e non sono necessari al PLC. Il runner usa Bench_ per run ID,
stato, indici, contatori, buffer e flag di completamento. Definisci protocollo
di preload/ready/start/done e commit finale che impedisca letture parziali.
Gli ingressi devono essere stabili prima della sezione candidata; nessuna
sequenza di scritture OPC host sostituisce l'applicazione atomica nella MAST.

Congela il buffer a fine scenario fino alla lettura. Il client OFS attende
done con timeout, legge i dati e riconferma identità/completamento/coerenza.
Se OFS non espone gli array richiesti usa scalari o mirror con handshake,
preservando il campionamento nel PLC e tutte le snapshot obbligatorie.
Registra la diagnostica dei 4 cicli SFC quando disponibile.

Prima dello start mantieni neutri i BOOL e verifica stato iniziale di uscite,
memoria interna e passo Idle. Verifica una procedura reale di reset pulito,
non soltanto scritture delle uscite. Non lasciare che i cicli di attesa o il
preload alterino lo stato iniziale; verifica gating/ordine e reset SFC.
Esegui lo stesso scenario due volte da stato pulito con run ID diversi per
dimostrare indipendenza dalla run precedente. Gestisci fine prova e cleanup
anche dopo errore, preservando evidenze e regole taint dopo timeout COM.

Non riutilizzare la tolleranza temporale del counter benchmark come prova di
precisione per ciclo. Aggiungi test offline del protocollo, freeze, handshake,
timeout, stale buffer, ordine sezioni e finestre SFC; le prove reali restano
separate e richiedono target simulator verificato e consenso live.
```

## Prompt 6 — CLI, policy di generazione e report

```text
Integra ce-bench iec con prepare, validate, run, selettore --case all/ID,
condizioni A/B e ripetizioni. Documenta le firme definitive. Riusa provider,
metriche, evidence, timeout, lock/taint, configurazione e snapshot esistenti.
Genera un overview PNG/SVG con percentuali per caso/configurazione, conteggi
verificati e verdetti rigorosi. Distingui anche slot pianificati non eseguiti;
mantieni separati riferimenti scripted, mutanti e prestazioni dei modelli.
Estendi gli schemi senza rompere le configurazioni offline/OPC/simulator.
Solo run chiama il provider a pagamento; validate usa riferimenti scripted
e non conta come prestazione LLM. Dry-run non chiama provider, COM o OPC e
non modifica CE/simulatore; valida configurazione e piano locale.

Separa la sessione di generazione dalla sessione privata di valutazione.
Il modello apre/salva soltanto la copia pubblica e può editare soltanto oggetti
ammessi. Applica la policy agli argomenti effettivi dei tool: import XML inline
o da file, export, risorse, documentazione, percorsi, dichiarazioni e letture
di progetto. Non esporre shell/filesystem arbitrario, fixture, riferimenti,
workspace privati, OPC della valutazione o server con progetto strumentato.
Dopo l'acquisizione immutabile del candidato non consentire correzioni basate
sugli esiti privati; il budget di riparazione durante la generazione usa solo
diagnostica pubblica, identico tra condizioni.

Aggiungi test della policy con tentativi di leakage tramite path alternativi,
file_path di import, progetto intero, read_section, list_variables, risorse,
helper e Bench_. Verifica i payload completi inviati al provider, non soltanto
il prompt principale. La specifica e questo documento sono anch'essi privati
rispetto al modello del benchmark.

Il report contiene i sei verdict esatti, case ID, lingua, modello/configurazione,
tempi, token disponibili (null se ignoti), hash e versione del grader, log di
build, cattura, prima discordanza e motivi dei blocchi. Conserva compatibilità
con summary/plan/evidence e valuta gli adattamenti necessari a compare/archive/
visualize. Separa errori di infrastruttura, authoring non supportato, validazione
scripted e prestazioni LLM; esplicita i denominatori e non omettere tentativi.
Confronta A/B soltanto con casi, modello, budget e politica di correzione uguali;
mantieni distinti fingerprint diversi e non sovrascrivere prove precedenti.
```

## Prompt 7 — Accettazione, regressioni e documentazione

```text
Completa l'accettazione della specifica, con evidenze separate offline/live/LLM.
Prima di eseguire script di integrazione leggili e controlla consensi, stato
sessione e target; un incarico di implementazione non autorizza da solo la
sostituzione dell'applicazione del simulatore né chiamate API a pagamento.

Matrice live obbligatoria su CE 16.4 + M580 Simulator + OFS:
- cinque riferimenti nella lingua nativa: pass in due esecuzioni pulite;
- cinque mutanti compilabili: output_mismatch esattamente ai vettori
  ST=6, LD=4, FBD=6, SFC=3/ciclo 4, IL=13;
- soluzione funzionalmente corretta nella lingua sbagliata: artifact_invalid;
- timeout/traccia incompleta/identità incoerente: infrastructure_error;
- selezione singola/all, report e blocchi authoring espliciti;
- nessuna esposizione di fixture/riferimenti durante la generazione.

Una prova scripted di importazione verifica il grader e il percorso di progetto;
per dichiarare authoring LLM end-to-end servono consegne effettivamente generate
dal modello per ogni lingua. Esegui queste ultime solo con autorizzazione alle
API e riporta modello, condizioni e budget. Non sommare tali prove alle campagne
offline storiche o al simulator counter benchmark.

Esegui i test IEC mirati, poi:
python -m unittest discover -s tools -p "test_*.py" -v
python -m compileall -q src
Usa l'interprete dell'ambiente di progetto. Se cambia il contenuto distribuito,
verifica wheel/sdist in una directory fresca come prescritto da AGENTS.md.
Non estendere test ripetitivi dopo l'esito positivo senza una ragione nuova.

Aggiorna README.md, benchmarks/README.md, la nota di implementazione e prompts.py
se cambiano capacità/workflow MCP. Documenta config di esempio senza segreti,
comandi realmente implementati, reset, ordine MAST, limiti OFS, bootstrap del
simulatore e dove trovare le evidenze locali. Non riscrivere gli attesi della
specifica per far passare l'implementazione.

Consegna tabella requisito -> test/evidenza -> risultato, file modificati,
comandi eseguiti e blocchi residui. Segna non eseguito ciò che manca; nessun
pass offline può sostituire l'accettazione live prevista dalla specifica.
```
