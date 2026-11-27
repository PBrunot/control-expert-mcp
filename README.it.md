# Control Expert MCP Server

[![CI](https://github.com/PBrunot/control-expert-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/PBrunot/control-expert-mcp/actions/workflows/ci.yml)
![Piattaforma: Windows](https://img.shields.io/badge/piattaforma-Windows-blue)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

[English](README.md) · Italiano

Un server MCP per un'installazione locale di **EcoStruxure Control Expert** (Unity Pro). Permette a un client MCP di esaminare, creare, modificare e compilare progetti PLC tramite l'API COM **Unity Developer Edition (UDE)** di Control Expert. Sperimentale, per la programmazione di PLC assistita da modelli linguistici.

[PyPI](https://pypi.org/project/control-expert-mcp/) · [Guida dettagliata (inglese)](docs/guide.md) · [Benchmark (inglese)](benchmarks/README.md)

> [!WARNING]
> Gli strumenti online possono trasferire applicazioni al PLC, avviare o arrestare i controllori e scrivere valori di processo. Sono disabilitati per impostazione predefinita. Usare un simulatore o un banco prova supervisionato; gli impianti di produzione richiedono personale qualificato. Una compilazione con un target connesso è una modifica online e viene rifiutata, a meno che `build_project` non sia chiamato con `allow_online_change=true` dopo l'approvazione dell'anello chiuso.

## Funzionalità

- **Progetti:** creazione, apertura, salvataggio, importazione ed esportazione.
- **Logica:** lettura e modifica di ST, LD, FBD, SFC e IL; gestione di variabili, DFB e DDT.
- **Hardware:** configurazione di CPU, rack, moduli, DTM, servizi Ethernet e richieste di scansione Modbus.
- **Validazione:** verifica dell'XML di scambio, analisi e compilazione, lettura della diagnostica.
- **Manuali:** ricerca nei manuali del produttore convertiti localmente, con citazioni.
- **Accesso live (facoltativo):** OFS OPC DA per i valori simbolici, Modbus TCP per i valori con indirizzo `%M`/`%MW`, messa in servizio con PLC Simulator.

Le funzionalità disponibili dipendono da installazione, licenza e cataloghi. Vedere il [riferimento degli strumenti](docs/guide.md#tool-reference) e i [flussi guidati](docs/guide.md#guided-workflows), in inglese.

## Requisiti

- Windows, Python **3.11+**.
- **Control Expert o Unity Pro** installato localmente con licenza, con il broker COM UDE (`PSBroker.PServerBroker.1`) registrato. Testato con Control Expert 14.0 e 16.4.
- Un client MCP con supporto **stdio** (Claude Desktop, Claude Code, VS Code con GitHub Copilot, Codex, DeepSeek Harness).

Eseguire il server sulla macchina di Control Expert.

## Installazione e configurazione

```powershell
py -3.11 -m pip install --upgrade control-expert-mcp
```

Configurare il client per avviare `control-expert-mcp` (ad esempio in Claude Desktop):

```json
{
  "mcpServers": {
    "control-expert": {
      "command": "control-expert-mcp",
      "args": [],
      "env": { "CE_MCP_ENABLE_ONLINE": "0" }
    }
  }
}
```

### Claude Code e Codex: server + skill di workflow

La [skill `control-expert`](plugin/skills/control-expert/SKILL.md) è una breve checklist operativa: ispezionare prima di modificare, ciclo di build, candidati per i simboli, verifica dei costrutti Modicon nei manuali e consenso per l'accesso live. Usa il formato standard `SKILL.md` e funziona con entrambi gli agenti.

**Claude Code:** un unico plugin installa il server (tramite `uvx`, richiede [uv](https://docs.astral.sh/uv/)) e la skill:

```text
/plugin install control-expert --marketplace PBrunot/control-expert-mcp
```

Gli strumenti online restano disattivati finché non si abilita l'opzione del plugin "Expose online tools". Solo la skill, con una configurazione del server propria: copiare `plugin/skills/control-expert` in `~/.claude/skills/control-expert`.

**Codex:** aggiungere il server, poi la skill:

```text
codex mcp add control-expert --env CE_MCP_ENABLE_ONLINE=0 -- control-expert-mcp
```

In Codex, chiedere: `$skill-installer install https://github.com/PBrunot/control-expert-mcp/tree/main/plugin/skills/control-expert`. In alternativa copiare `plugin/skills/control-expert` in `~/.agents/skills/control-expert` (tutti i progetti) o in `.agents/skills/control-expert` (un solo repository). Riavviare Codex se la skill non compare.

ChatGPT web/desktop si collega solo a server MCP remoti HTTPS, quindi non può avviare questo server locale Windows; usare Codex.

Se il comando non viene trovato, usare il percorso assoluto oppure l'interprete Python dell'installazione con gli argomenti `["-m", "control_expert_mcp"]`. Altri client: [configurazione dei client](docs/guide.md#mcp-client-configuration), in inglese, e [samples/](samples/).

Variabili d'ambiente:

| Variabile | Scopo |
| --- | --- |
| `CE_MCP_ENABLE_ONLINE` | `1` espone gli strumenti online (serve un riavvio). Serve comunque il consenso per la sessione. |
| `CE_MCP_OPC_PYTHON` | Python con la stessa architettura della DLL OPC Automation e `pywin32` (spesso a 32 bit per OFS). |
| `CE_MCP_SCHEMA_DIR` | Sostituisce la directory `SrcXmlSchema` rilevata automaticamente. |
| `CE_MCP_MANUALS_DIR` | Percorso assoluto dei manuali convertiti e indicizzati. |
| `CE_MCP_SIMULATOR_EXE` | Percorso facoltativo dell'eseguibile del simulatore. |

## Utilizzo

Lavorare su un progetto di prova o una copia. Esempi di richieste:

- «Apri questo progetto e riepiloga CPU, task, sezioni e variabili globali.»
- «Crea una sezione ST per un interblocco motore, dichiara le variabili e compila il progetto.»
- «Cerca `READ_VAR` nei manuali locali e cita l'argomento pertinente.»

Compilare dopo le modifiche e salvare esplicitamente: `close_project` scarta le modifiche se non si specifica `save=true`, e un archivio `.sta` aperto va salvato in un percorso `.stu`. Una compilazione riuscita non dimostra il corretto comportamento in esecuzione. Vedere [utilizzo](docs/guide.md#usage), in inglese.

**Accesso live:** abilitare gli strumenti online non autorizza l'accesso a un controllore. Chiamare `get_live_access_setup` e `configure_live_access` a ogni sessione; le scritture in anello chiuso e i comandi al PLC richiedono un'approvazione separata. Preferire OFS OPC DA. Vedere [accesso al PLC e al simulatore](docs/guide.md#plc-and-simulator-access), in inglese.

**Manuali:** convertire e indicizzare prima la guida installata; vedere [manuali locali consultabili](docs/guide.md#searchable-local-manuals), in inglese.

Problemi: [risoluzione dei problemi](docs/guide.md#troubleshooting), in inglese, e [GitHub Issues](https://github.com/PBrunot/control-expert-mcp/issues).

## Benchmark

`ce-bench` esegue una suite offline di sette attività (con e senza ricerca nei manuali), una suite sui linguaggi IEC e un test sul simulatore M580. I risultati sono esplorativi e non dimostrano la correttezza del PLC in esecuzione. Vedere la [guida ai benchmark](benchmarks/README.md) e i [risultati archiviati](benchmarks/archive/README.md), in inglese.

![Panoramica dei benchmark: accettazione, correttezza mappatura I/O, tempi e token](benchmarks/archive/overview.png)

## Sviluppo

```powershell
git clone https://github.com/PBrunot/control-expert-mcp.git
cd control-expert-mcp
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[benchmark,test]"
.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py"
```

Vedere [AGENTS.md](AGENTS.md), [sviluppo e validazione](docs/guide.md#development-and-validation) e [pacchetti e rilasci](docs/guide.md#packaging-and-releases), in inglese.

## Licenza e riconoscimenti

Questo repository è un fork di [apexsotjo-blip/control-expert-mcp](https://github.com/apexsotjo-blip/control-expert-mcp), con contributi aggiuntivi di Pascal Brunot. Il repository originale non includeva un file di licenza; la licenza MIT di questo fork si applica ai contributi di Pascal Brunot e non modifica la licenza dei contributi upstream o dei materiali di terze parti. Consultare [LICENSE](LICENSE) e la cronologia del repository upstream per la provenienza. Il progetto è inoltre ispirato a [tiaportal-mcp](https://github.com/heilingbrunner/tiaportal-mcp).

Il progetto non è affiliato né approvato da Schneider Electric. Software, licenze e documentazione di Control Expert e Unity Pro sono forniti separatamente.
