# Demand Lab · Previsione della domanda e pianificazione delle scorte

Mini-dashboard Python per un project work accademico: quattro articoli generici, tre metodi previsionali e confronto tra scenari di domanda e approvvigionamento. Interfaccia e documentazione sono in italiano; codice, identificatori e commenti sono in inglese.

Il caso prende come riferimento **Decathlon**, ma il magazzino, i dati di domanda e i parametri logistici sono **simulati**. Non vengono utilizzati dati interni dell'impresa e non si descrivono le sue effettive politiche di gestione. Il progetto non è affiliato all'azienda.

## Anteprima nel browser senza installazioni

**[PREVIEW: Apri la dashboard pubblica nel tuo browser](https://giovannimartusciello.github.io/demand-lab/)**

La preview utilizza **Stlite**, che esegue Streamlit e Python direttamente nel browser tramite Pyodide e WebAssembly. GitHub Pages pubblica i file statici; i calcoli avvengono sul dispositivo del visitatore.

**Il primo caricamento può richiedere da alcune decine di secondi ad alcuni minuti**, in funzione della connessione, del dispositivo e della disponibilità dei servizi esterni: vengono scaricati l'ambiente Python e le librerie necessarie. È una scelta fatta per semplificare il test e l'anteprima dell'applicazione nel browser **senza dover installare nulla**. Gli accessi successivi possono beneficiare della cache, senza garanzia di avvio immediato. È necessaria una connessione Internet; non è una versione offline.

Attendere il completamento del caricamento prima di usare i controlli. Se l'avvio non termina, ricaricare la pagina e verificare che la rete consenta l'accesso a jsDelivr e agli archivi dei pacchetti Python. Utilizzare un browser aggiornato con WebAssembly abilitato.

La versione di Stlite è fissata a **1.12.2**, che distribuisce Streamlit **1.65.0**. I pacchetti scientifici del browser sono risolti nell'ambiente Pyodide: il loro insieme non coincide necessariamente con quello di un'installazione desktop. Per aggiornare Stlite modificare insieme i due riferimenti di versione in `index.html` e verificare nuovamente l'applicazione.

## Utilizzo

- Scegliere uno dei quattro articoli nella barra laterale.
- Selezionare un esperimento guidato o modificare liberamente i parametri.
- Consultare **Domanda e previsioni**, **Accuratezza dei metodi**, **Scorte e scenari**, **Metodo e dati**.
- Ripristinare lo scenario iniziale per tornare ai valori di riferimento.
- Esportare domanda e previsioni in CSV, oppure parametri e risultati completi in JSON.

Gli esperimenti guidati sono: variabilità raddoppiata; lead time da due a cinque mesi; aumento della stagionalità con capacità limitata. Il terzo modifica due parametri ed è uno scenario congiunto, non una misura isolata dell'effetto causale della stagionalità.

## Dati e riproducibilità

`data/demand.csv` contiene **240 osservazioni**: 60 mesi, da gennaio 2021 a dicembre 2025, per ciascuno dei quattro articoli. `data/catalog.json` contiene i parametri del generatore e i semi casuali.

| Articolo generico | Profilo iniziale | Base mensile | Trend unità/mese | Ampiezza stagionale | Deviazione rumore |
|---|---|---:|---:|---:|---:|
| Calze sportive | Stazionario | 500 | 0 | 0 | 35 |
| Elastico per il fitness | Crescente | 120 | 5 | 0 | 20 |
| Tenda da campeggio | Stagionale | 200 | 0 | 0,80 | 12 |
| Accessorio sportivo di nicchia | Irregolare | 65 | 0 | 0 | 65 |

Il picco stagionale è a luglio. Il rumore additivo è normale, con seme fisso per articolo; la domanda finale è arrotondata all'intero e troncata a zero. Nell'articolo irregolare il troncamento altera media e distribuzione del rumore: la base di 65 non coincide necessariamente con la media effettiva. È domanda irregolare sintetica, non un modello specialistico di domanda intermittente.

I controlli della domanda modificano **l'intera serie storica simulata**, mantenendo gli stessi numeri casuali. Sono scenari controfattuali, non shock soltanto futuri. Il trend aggiuntivo è espresso in percentuale della base mensile per mese; la stagionalità aggiuntiva aumenta l'ampiezza fino a un massimo totale del 95%. Lead time, lotto, servizio e capacità non modificano direttamente la domanda.

Per rigenerare i dati e verificare i calcoli, con Python 3.12 o successivo dalla radice della repository:

```bash
python scripts/generate_data.py
python -m unittest discover -s tests -v
```

Questi comandi usano solo la libreria standard e permettono di rigenerare le 240 osservazioni iniziali e verificare i calcoli del modello.

## Metodi e valutazione

Sono implementati tre metodi, ciascuno con un ruolo distinto:

- **Media mobile semplice a tre mesi:** utilizza la media delle ultime tre osservazioni e mantiene una previsione costante nei mesi successivi.
- **Regressione lineare:** stima una retta in funzione del tempo e la prolunga per rappresentare una domanda crescente o decrescente.
- **Naïve stagionale:** ripete la domanda del mese corrispondente dell'ultimo anno osservato, rappresentando una stagionalità annuale stabile.

Le eventuali previsioni negative della regressione sono troncate a zero. I metodi vengono confrontati con lo stesso protocollo temporale; nessuno viene assegnato in anticipo a un articolo.

- **2021–2023:** storia iniziale disponibile.
- **2024:** dodici previsioni a un mese con origine mobile e finestra crescente; scelta del metodo con MAE minimo, spareggio su RMSE e ordine fisso.
- **2025:** dodici successive previsioni a un mese. Il metodo resta quello scelto sul 2024; la stima viene aggiornata con i mesi precedenti già osservati.
- **2026:** previsione illustrativa a dodici mesi ristimando il metodo scelto su tutta la storia disponibile. Non esistono osservazioni future con cui misurarne l'errore.

MAE e RMSE sono in unità di prodotto. Il bias è la media di domanda meno previsione: valori positivi indicano sottostima. Non si usa MAPE perché la domanda può essere nulla. La valutazione a un mese non certifica la qualità a dodici mesi; la selezione su dodici osservazioni può essere instabile. L'interfaccia mostra i risultati di tutti i candidati, ma non usa il test 2025 per riselezionare il metodo.

## Scorte e ipotesi

| Tipo | Criterio | Limite principale |
|---|---|---|
| Ciclica media | Q / 2 | Benchmark con consumo regolare e reintegro a lotto; approssimazione con stagionalità |
| Sicurezza | z × deviazione standard degli errori cumulati sul lead time | Approssimazione normale, campione piccolo e finestre sovrapposte |
| Anticipata | Bilancio retrogrado su dodici mesi con capacità costante | Piano deterministico autonomo; buffer finale nullo e possibile scorta iniziale necessaria |
| Pipeline | Somma delle previsioni dei prossimi L mesi | Stima di fabbisogno in transito a inizio piano, non misura degli ordini effettivi |

Gli errori sul lead time sono calcolati con origini e mesi obiettivo confinati al 2024: per L da uno a sei si hanno da dodici a sette finestre. Non si applica automaticamente la regola della radice del tempo; si considera l'errore cumulato prodotto dal metodo. Le finestre sovrapposte non sono indipendenti. La scelta del metodo e la calibrazione della sicurezza condividono il 2024: resta possibile ottimismo da selezione. Il bias viene mostrato e non corretto automaticamente. Il servizio obiettivo è una probabilità teorica per ciclo, non un fill rate misurato.

La capacità è un multiplo della previsione media iniziale: aumenta o diminuisce con il controllo dedicato, senza adeguarsi automaticamente alla domanda modificata. Per le scorte anticipate si applica `B[t] = max(0, B[t+1] + forecast[t] - capacity)`, con `B[12] = 0`. Gli arrivi avvengono prima della domanda del mese. Se `B[0] > 0`, tale scorta deve esistere già prima dell'inizio del piano. Il lead time richiede ordini anticipati, ma non cambia questo vincolo di ricezione. La media riportata è la media delle semisomme dei buffer a inizio e fine mese, un'approssimazione temporale.

**Le quattro quantità non vengono sommate in una giacenza totale.** Pipeline è esterna al magazzino e le altre stime provengono da criteri non integrati in un unico simulatore. Il punto di riordino illustrativo è domanda prevista durante L più sicurezza: il riferimento è la revisione continua. Un sistema a revisione mensile richiederebbe anche il periodo di revisione.

## Struttura

```text
index.html                  Avvio Stlite e caricamento dei file
app.py                      Dashboard e interazione
models.py                   Generazione, previsioni, errori e scorte
locale_it.py                Etichette e formattazione italiana
data/                       Catalogo e domanda riproducibile
scripts/                    Generazione dei dati
tests/                      Verifiche matematiche e temporali
.github/workflows/pages.yml Verifica e pubblicazione
```

Per l'anteprima locale nella stessa modalità statica di Pages:

```bash
python -m http.server 8765
```

Aprire `http://localhost:8765/`. Il server serve i file: i calcoli Python continuano ad avvenire nel browser. L'installazione locale delle dipendenze elencate in `requirements.txt` è facoltativa, destinata allo sviluppo con `streamlit run app.py`, e non è richiesta ai visitatori della preview.

## Fonti

Fonti consultate il 18 novembre 2026. I collegamenti sostengono il contesto o i metodi generali; i parametri e i risultati numerici del caso sono costruzioni didattiche del progetto.

- [Decathlon, risultati del gruppo 2025](https://www.decathlon-united.media/pressfiles/2025results): riferimento aziendale e settore.
- [Hyndman e Athanasopoulos, Forecasting: Principles and Practice, strumenti e valutazione](https://otexts.com/fpp3/toolbox.html): errori, benchmark e valutazione temporale.
- [Hyndman e Athanasopoulos, Forecasting: Principles and Practice, scomposizione delle serie](https://otexts.com/fpp3/decomposition.html): componenti di trend e stagionalità delle serie.
- [Prak, Teunter e Syntetos, 2017, On the calculation of safety stocks when demand is forecasted](https://doi.org/10.1016/j.ejor.2016.06.035): cautela nell'aggregazione degli errori su lead time multiperiodali.
- [SAP, Safety Stock Planning](https://help.sap.com/docs/SAP_SUPPLY_CHAIN_MANAGEMENT/0bad972d62de4005822fdcbce98f8748/9e40c95360267614e10000000a174cb4.html): ruolo dell'incertezza nella sicurezza.
- [Stlite](https://github.com/whitphx/stlite): esecuzione nel browser e limitazioni.
- [Streamlit](https://docs.streamlit.io/): componenti dell'interfaccia.
- [GitHub Pages](https://docs.github.com/en/pages): pubblicazione statica.

## Limiti e sviluppi

Il laboratorio non ottimizza costi, non simula stockout stocastici o livelli di servizio effettivi, non gestisce ordini reali e non risolve vincoli comuni a più articoli. Non consente quindi di affermare risparmi economici o miglioramenti percentuali del servizio. Estensioni possibili: test su più orizzonti e semi, dati reali, lead time variabile, metodi per domanda intermittente e simulazione integrata delle politiche di riordino.
