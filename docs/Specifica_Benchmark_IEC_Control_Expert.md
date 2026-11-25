# Benchmark IEC 61131-3 per Control Expert MCP

**Specifica di implementazione per Codex · v0.1 · 25 novembre 2026**

Estendere `control-expert-mcp` con cinque casi eseguibili su Control Expert 16.4 e PLC Simulator M580. Per ogni caso, l’LLM riceve il requisito e l’interfaccia, implementa la logica nel linguaggio richiesto e consegna il progetto. Il grader compila l’artefatto e verifica le uscite reali del simulatore usando ingressi e risultati attesi fissati in questa specifica.

| Caso | Linguaggio richiesto | Logica verificata |
|---|---|---|
| `iec_st_clamp` | ST · Structured Text | Differenza intera con saturazione e gestione degli estremi |
| `iec_ld_latch` | LD · Ladder Diagram | Autoritenuta con arresto e perdita del consenso prioritari |
| `iec_fbd_hysteresis` | FBD · Function Block Diagram | Isteresi con soglie inclusive e azzeramento alla disabilitazione |
| `iec_sfc_sequence` | SFC · Sequential Function Chart | Sequenza a tre passi con handshake e ritorno al passo iniziale |
| `iec_il_select` | IL · Instruction List | Selezione booleana con abilitazione, esclusività e forzatura logica |

L’edizione IEC 61131-3:2025 elenca ST, LD e FBD come linguaggi e descrive SFC come insieme di elementi per strutturare l’esecuzione. La suite prova anche SFC come sezione nativa e IL per la compatibilità con Control Expert. LL984 è fuori da questo perimetro IEC. Verificare la disponibilità di ogni tipo di sezione nel progetto M580 di prova con la versione installata. [IEC 61131-3:2025](https://webstore.iec.ch/en/publication/68533) · [Manuale Schneider sui linguaggi e sulla struttura del programma](https://www.se.com/mk/en/download/document/35006144K01000/)

## 1. Contratto comune

- Ogni caso contiene una sezione candidata, interfaccia tipizzata, stato iniziale, modalità di campionamento e una traccia di riferimento. Le righe della traccia sono ordinate e appartengono allo stesso scenario. Lo stato persiste da una riga alla successiva. Ripartire da uno stato iniziale pulito a ogni nuova esecuzione, usando il meccanismo verificato sul simulatore.
- Usare i nomi pubblici delle variabili riportati nelle tabelle. Precreare tali variabili nel progetto di partenza e riservare al runner il prefisso `Bench_`. Le variabili di output sono scritte dalla logica candidata. Le sole uscite valutate sono quelle indicate in ogni caso.
- Nelle tabelle `0` e `1` rappresentano rispettivamente `FALSE` e `TRUE` nelle colonne `BOOL`. Il confronto è tipizzato ed esatto. Tutti gli ingressi di una riga vengono applicati insieme prima di eseguire la logica.
- Per ST, LD, FBD e IL, una riga corrisponde a un ciclo MAST utile. Registrare le uscite al termine dello stesso ciclo. Per SFC, mantenere l’intero vettore per **quattro cicli MAST consecutivi** e valutare la snapshot al quarto ciclo. Anche per SFC salvare, se disponibile, la traccia dei quattro cicli per la diagnostica.
- All’LLM fornire soltanto ID, linguaggio, interfaccia, requisito funzionale, stato iniziale, contratto temporale e strumenti previsti dalla configurazione. Le tabelle di questo documento sono fixture del grader. Escluderle dal prompt e dai file accessibili durante la generazione. Acquisire l’artefatto prima di costruire o caricare il progetto strumentato con le fixture.
- Verificare nel progetto o nell’export che la sezione presente abbia il linguaggio richiesto. Per SFC verificare la presenza del chart nativo e che sia questo a governare la sequenza. Un helper ST può pubblicare lo stato dei passi o calcolare una condizione locale, senza sostituire il chart. Il codice del runner è infrastruttura condivisa e resta indipendente dalla sezione candidata.

## 2. Casi e risultati attesi

Le colonne **prima di →** descrivono gli ingressi. Le colonne **dopo →** descrivono le uscite attese.

### ST · Differenza con saturazione

**Interfaccia.** Ingressi `Raw: INT`, `Offset: INT`. Uscita `Result: INT`.

**Requisito per l’LLM.** A ogni ciclo calcolare la differenza matematica `Raw - Offset` e limitarla all’intervallo chiuso `[0, 1000]`. Accettare l’intero dominio dei due ingressi INT, compresi i casi in cui la differenza supera la rappresentabilità di un INT. Il valore precedente di `Result` è irrilevante. Stato iniziale `Result = 0`.

| Ciclo | Raw | Offset | → | Result |
|---:|---:|---:|:---:|---:|
| 1 | 110 | 10 | → | 100 |
| 2 | 500 | 500 | → | 0 |
| 3 | 99 | 100 | → | 0 |
| 4 | 100 | 99 | → | 1 |
| 5 | 1099 | 100 | → | 999 |
| 6 | 1100 | 100 | → | 1000 |
| 7 | 1101 | 100 | → | 1000 |
| 8 | -50 | -100 | → | 50 |
| 9 | 32767 | -32768 | → | 1000 |
| 10 | -32768 | 32767 | → | 0 |

### LD · Autoritenuta con arresto prioritario

**Interfaccia.** Ingressi `StartCmd: BOOL`, `StopCmd: BOOL`, `Permit: BOOL`. Uscita `Running: BOOL`.

**Requisito per l’LLM.** `Running` parte da FALSE. A ogni ciclo, `StopCmd = TRUE` oppure `Permit = FALSE` impongono `Running = FALSE`, anche con `StartCmd = TRUE`. Con consenso e senza arresto, `StartCmd = TRUE` avvia la marcia. La marcia resta attiva dopo il rilascio di Start finché consenso e assenza di arresto persistono. Start è valutato a livello, incluso il caso in cui resti alto mentre torna il consenso.

| Ciclo | StartCmd | StopCmd | Permit | → | Running |
|---:|---:|---:|---:|:---:|---:|
| 1 | 0 | 0 | 1 | → | 0 |
| 2 | 1 | 0 | 1 | → | 1 |
| 3 | 0 | 0 | 1 | → | 1 |
| 4 | 1 | 1 | 1 | → | 0 |
| 5 | 0 | 0 | 1 | → | 0 |
| 6 | 1 | 0 | 1 | → | 1 |
| 7 | 0 | 0 | 0 | → | 0 |
| 8 | 0 | 0 | 1 | → | 0 |
| 9 | 1 | 0 | 0 | → | 0 |
| 10 | 1 | 0 | 1 | → | 1 |
| 11 | 0 | 1 | 1 | → | 0 |

### FBD · Isteresi abilitata

**Interfaccia.** Ingressi `LevelValue: INT`, `EnableCmd: BOOL`. Uscita `Demand: BOOL`.

**Requisito per l’LLM.** `Demand` parte da FALSE. Quando `EnableCmd = FALSE`, azzerare `Demand` nello stesso ciclo. Quando l’abilitazione è attiva, un livello minore o uguale a 30 imposta `Demand = TRUE`, un livello maggiore o uguale a 70 imposta `Demand = FALSE` e i livelli tra 30 e 70 conservano il valore precedente. Il livello e l’abilitazione sono valutati a ogni ciclo.

| Ciclo | LevelValue | EnableCmd | → | Demand |
|---:|---:|---:|:---:|---:|
| 1 | 50 | 1 | → | 0 |
| 2 | 31 | 1 | → | 0 |
| 3 | 30 | 1 | → | 1 |
| 4 | 50 | 1 | → | 1 |
| 5 | 69 | 1 | → | 1 |
| 6 | 70 | 1 | → | 0 |
| 7 | 69 | 1 | → | 0 |
| 8 | 29 | 1 | → | 1 |
| 9 | 29 | 0 | → | 0 |
| 10 | 50 | 1 | → | 0 |
| 11 | 30 | 1 | → | 1 |
| 12 | 71 | 1 | → | 0 |

### SFC · Sequenza con handshake a tre passi

**Interfaccia.** Ingressi `StartCmd: BOOL`, `DoneCmd: BOOL`, `AckCmd: BOOL`. Uscite `Busy: BOOL`, `Complete: BOOL`.

**Requisito per l’LLM.** Implementare tre passi sequenziali in un chart nativo. Il passo iniziale è `Idle`; i successivi sono `Active` e `Completed`. `Idle` passa ad `Active` esattamente con Start da solo. `Active` passa a `Completed` esattamente con Done da solo. `Completed` torna a `Idle` esattamente con Ack da solo. In ogni altra combinazione il passo attivo resta quello corrente, anche con due o tre comandi contemporanei. Le uscite rappresentano il passo attivo. `Idle` vale `Busy=0, Complete=0`, `Active` vale `1,0`, `Completed` vale `0,1`. I comandi sono valutati a livello. Le uscite devono valere quanto specificato al termine della finestra di quattro cicli.

| Vettore | StartCmd | DoneCmd | AckCmd | → | Busy | Complete |
|---:|---:|---:|---:|:---:|---:|---:|
| 1 | 0 | 0 | 0 | → | 0 | 0 |
| 2 | 0 | 1 | 0 | → | 0 | 0 |
| 3 | 1 | 1 | 0 | → | 0 | 0 |
| 4 | 1 | 0 | 0 | → | 1 | 0 |
| 5 | 0 | 0 | 0 | → | 1 | 0 |
| 6 | 0 | 0 | 1 | → | 1 | 0 |
| 7 | 0 | 1 | 1 | → | 1 | 0 |
| 8 | 0 | 1 | 0 | → | 0 | 1 |
| 9 | 0 | 0 | 0 | → | 0 | 1 |
| 10 | 1 | 0 | 0 | → | 0 | 1 |
| 11 | 1 | 1 | 1 | → | 0 | 1 |
| 12 | 0 | 0 | 1 | → | 0 | 0 |
| 13 | 1 | 0 | 0 | → | 1 | 0 |

Il runner deve acquisire la snapshot dopo il chart e dopo l’eventuale sezione che pubblica le due uscite. La finestra fissa evita di imporre alla soluzione una particolare fase di aggiornamento interna all’SFC e consente comunque un verdetto entro un numero determinato di cicli. Il test resta indipendente dai timer.

### IL · Selezione booleana abilitata

**Interfaccia.** Ingressi `SignalA: BOOL`, `SignalB: BOOL`, `OverrideCmd: BOOL`, `EnableCmd: BOOL`. Uscita `Selected: BOOL`.

**Requisito per l’LLM.** Aggiornare `Selected` a ogni ciclo. Con abilitazione attiva, l’uscita è TRUE quando `OverrideCmd` è TRUE oppure quando esattamente uno fra `SignalA` e `SignalB` è TRUE. Con abilitazione disattiva l’uscita è sempre FALSE. Stato iniziale `Selected = FALSE`.

| Ciclo | SignalA | SignalB | OverrideCmd | EnableCmd | → | Selected |
|---:|---:|---:|---:|---:|:---:|---:|
| 1 | 0 | 0 | 0 | 0 | → | 0 |
| 2 | 0 | 0 | 0 | 1 | → | 0 |
| 3 | 0 | 0 | 1 | 1 | → | 1 |
| 4 | 0 | 0 | 1 | 0 | → | 0 |
| 5 | 0 | 1 | 0 | 1 | → | 1 |
| 6 | 0 | 1 | 0 | 0 | → | 0 |
| 7 | 0 | 1 | 1 | 0 | → | 0 |
| 8 | 0 | 1 | 1 | 1 | → | 1 |
| 9 | 1 | 0 | 0 | 1 | → | 1 |
| 10 | 1 | 0 | 0 | 0 | → | 0 |
| 11 | 1 | 0 | 1 | 0 | → | 0 |
| 12 | 1 | 0 | 1 | 1 | → | 1 |
| 13 | 1 | 1 | 0 | 1 | → | 0 |
| 14 | 1 | 1 | 0 | 0 | → | 0 |
| 15 | 1 | 1 | 1 | 1 | → | 1 |
| 16 | 1 | 1 | 1 | 0 | → | 0 |

## 3. Integrazione nel repository

1. **Ricognizione.** Leggere il codice e le istruzioni correnti di [`control-expert-mcp`](https://github.com/PBrunot/control-expert-mcp). Riutilizzare il runner, la raccolta delle metriche e la configurazione M580/OFS di `ce-bench opc` dove applicabili. La documentazione di v0.9.2 descrive il benchmark OPC, gli strumenti di progetto e le operazioni sul simulatore. Verificare il comportamento del checkout reale prima di definire gli adattatori. [Documentazione del pacchetto](https://pypi.org/project/control-expert-mcp/0.9.2/)
2. **Fixture e comando.** Aggiungere al benchmark esistente un set selezionabile con tutti i cinque casi o un singolo ID. Estendere lo schema di fixture del repository con linguaggio, interfaccia pubblica e cicli per vettore. Tenere separati i dati del prompt dalle tracce del grader. Riutilizzare il formato di report e le convenzioni CLI esistenti.
3. **Progetto di partenza.** Preparare un progetto M580 minimale per il simulatore, con sezione candidata vuota e variabili tipizzate. Usare una copia per ogni esecuzione. Verificare su Control Expert 16.4 il round trip nativo di ciascun linguaggio e l’ordine delle sezioni. Per LD, FBD, SFC e IL, se manca uno strumento di modifica diretto, verificare import/export con un piccolo esempio salvato dall’editor nativo e riusare il percorso di scambio supportato. Inventariare il formato effettivo da quel round trip, compresa l’eventuale variante ZEF per M580. Per SFC, acquisire insieme al chart le azioni, le transizioni e gli eventuali helper ammessi. Se il checkout non dispone ancora di un percorso di authoring end-to-end per un linguaggio, riportare il blocco specifico. L’importazione riuscita di una sezione precostruita dimostra il percorso del grader, la consegna generata dall’LLM dimostra il benchmark end-to-end.
4. **Consegna e build.** Acquisire il progetto candidato e verificare interfaccia e linguaggio effettivo. Trasferire soltanto la sezione candidata e gli helper ammessi nella copia strumentata del progetto di test. Controllare esito e diagnostica della build. Eseguire il progetto nel PLC Simulator M580. Il runner controlla il progetto di test e i dati di valutazione.
5. **Acquisizione deterministica.** Eseguire nella stessa MAST, nell’ordine, applicazione degli ingressi, logica candidata e registrazione delle uscite. Precaricare i vettori in variabili PLC prima di dare il via allo scenario. Un indice di vettore e un contatore di ciclo avanzano nel simulatore. Prima dell’avvio mantenere neutri i comandi BOOL e verificare lo stato iniziale. Conservare il buffer completo fino alla lettura del runner. Il runner attende via OFS un flag di completamento e legge il buffer stabilizzato. Usare l’accesso simbolico verificato nel progetto. Se OFS espone soltanto scalari per una determinata forma di buffer, usare tag scalari indicizzati dal runner o un mirror scalare con handshake, mantenendo invariata l’acquisizione dentro la task. A ogni esecuzione verificare l’identificativo della run e il numero delle snapshot prima di valutare la traccia.
6. **Riavvio.** Verificare con un riferimento noto che il simulatore riparta ogni volta con interfaccia, memoria della logica, passo iniziale e buffer nelle condizioni previste. Riutilizzare l’eventuale procedura di prima inizializzazione del simulatore già documentata nel progetto. Eseguire nuovamente lo stesso scenario per verificare che il risultato non dipenda dalla run precedente.

## 4. Verdetti, report e criteri di accettazione

**PASS** richiede struttura valida, build riuscita, acquisizione completa e corrispondenza esatta di tutte le uscite previste. Per SFC confrontare il quarto ciclo di ogni vettore. Per gli altri casi confrontare ogni ciclo. Usare i seguenti esiti nel report.

| Esito | Quando assegnarlo |
|---|---|
| `pass` | Tutti i controlli previsti sono riusciti |
| `artifact_invalid` | Linguaggio, struttura o interfaccia errati |
| `build_failed` | Il progetto candidato non compila |
| `output_mismatch` | Traccia valida con almeno un valore diverso dall’atteso |
| `infrastructure_error` | Simulator/OFS indisponibile, timeout, traccia incompleta o contesto di acquisizione incoerente |
| `unsupported_authoring` | Nel checkout manca un percorso verificato per consegnare la logica nel linguaggio richiesto |

Registrare ID caso, linguaggio, modello, configurazione, tempi e token disponibili. Per ogni discordanza riportare almeno il primo vettore errato con indice da 1, ciclo del vettore, ingressi applicati, nome dell’uscita, atteso e osservato. Conservare il log di build e la traccia. Tenere separati gli errori di infrastruttura dalle prestazioni del modello. Per confrontare MCP con e senza documentazione, usare gli stessi casi, modello, budget e criterio di correzione nelle due configurazioni.

Per accettare la prima implementazione valgono i seguenti criteri.

- I **cinque** riferimenti nel rispettivo linguaggio nativo passano su Control Expert 16.4 e PLC Simulator M580, anche dopo una seconda esecuzione.
- Una variante compilabile ma errata per ciascun caso ottiene `output_mismatch` al vettore previsto. Per la prima divergenza attesa usare ST 6 con saturazione a 999, LD 4 con priorità di Start sopra Stop, FBD 6 con soglia di rilascio stretta, SFC 3 accettando Start anche con Done alto, IL 13 con OR al posto di XOR.
- Una soluzione con linguaggio errato viene respinta anche se produce le uscite corrette. Un timeout del simulatore non viene contato come errore funzionale della soluzione.
- Il comando può eseguire un singolo caso o tutti e cinque, produce il report e distingue esplicitamente eventuali blocchi rimasti nell’authoring nativo.
- Il prompt e gli strumenti accessibili durante la generazione non espongono fixture, tracce attese o progetti di riferimento.

**Stato del documento.** I casi e gli attesi sono nuove fixture di progetto. La metodologia di acquisizione per ciclo riprende CycleBench. I progetti di riferimento, gli adattatori di import e il comportamento sul simulatore sono da verificare durante l’implementazione. [CycleBench, §3.2](https://arxiv.org/html/2610.28675v1#S3.SS2)
