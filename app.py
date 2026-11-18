"""Italian browser dashboard for reproducible demand and inventory experiments."""
from dataclasses import asdict
from datetime import date
from html import escape
import json
from pathlib import Path
from statistics import mean

import altair as alt
import pandas as pd
import streamlit as st

from models import Scenario, forecast, generate_demand, run_analysis
from locale_it import METHOD_NAMES, format_number, month_label

ROOT = Path(__file__).parent
CATALOG = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
COLORS = ["#006d77", "#df7c38", "#6d82a6", "#8e6ca8", "#4c947a"]
DEFAULTS = {"noise":1.0,"trend":0.0,"seasonality":0,"lead_time":2,"order_quantity":300,
            "service_level":95,"capacity_factor":1.15}
PRESETS = ("Configurazione libera", "Variabilità raddoppiata", "Lead time più lungo", "Picco stagionale e capacità limitata")

st.set_page_config(page_title="Domanda e scorte · Demand Lab", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
.block-container{padding-top:4.5rem;padding-bottom:2rem;max-width:1440px}
h1{letter-spacing:-.04em;font-weight:750!important}h2,h3{letter-spacing:-.02em}
[data-testid="stMetric"]{background:#fff;border:1px solid #dbe5ec;border-radius:12px;padding:16px}
[data-testid="stMetricLabel"]{color:#526778}
[data-testid="stElementToolbar"]{display:none!important}
.lab-kicker{font-size:.76rem;letter-spacing:.14em;font-weight:700;color:#006d77;margin-bottom:.6rem}
.lab-table{width:100%;border-collapse:collapse;font-size:.88rem;margin:12px 0 20px}
.lab-table th{text-align:left;background:#eaf1f5;color:#17324d}
.lab-table th,.lab-table td{padding:10px 12px;border-bottom:1px solid #dbe5ec}
.lab-table tr.selected{background:#e6f4f1;font-weight:650}
.lab-note{color:#526778;font-size:.88rem;line-height:1.65}
@media(max-width:640px){.block-container{padding-top:4.5rem}.lab-table{font-size:.75rem}.lab-table th,.lab-table td{padding:7px 4px}}
</style>""",unsafe_allow_html=True)


def reset_controls():
    for key,value in DEFAULTS.items():
        st.session_state[key] = value
    st.session_state["preset"] = PRESETS[0]


def apply_preset():
    selected_preset = st.session_state["preset"]
    for key,value in DEFAULTS.items():
        st.session_state[key] = value
    if selected_preset == PRESETS[1]:
        st.session_state["noise"] = 2.0
    elif selected_preset == PRESETS[2]:
        st.session_state["lead_time"] = 5
    elif selected_preset == PRESETS[3]:
        st.session_state["seasonality"] = 60
        st.session_state["capacity_factor"] = 1.0


for key,value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def display_table(headers, rows, selected=None):
    head = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    body = "".join('<tr'+(' class="selected"' if i == selected else '')+'>'+"".join(f"<td>{escape(str(cell))}</td>" for cell in row)+"</tr>" for i,row in enumerate(rows))
    st.markdown(f'<table class="lab-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>',unsafe_allow_html=True)


def display_delta(value, digits=0):
    if abs(value) < 0.5 * 10**(-digits):
        return None
    return format_number(value, digits)


def style_chart(chart, height=330):
    return chart.properties(height=height).configure_view(stroke=None).configure_axis(
        labelColor="#526778",titleColor="#526778",gridColor="#e4ebf0",labelFontSize=11,titleFontSize=12,
    ).configure_legend(title=None,orient="bottom",labelLimit=350)


def demand_chart(rows, color_order, height=330):
    frame = pd.DataFrame(rows)
    chart = alt.Chart(frame).mark_line(strokeWidth=2.4).encode(
        x=alt.X("index:Q",title="Mese",scale=alt.Scale(domain=[int(frame["index"].min()),int(frame["index"].max())],nice=False),axis=alt.Axis(values=list(range(int(frame["index"].min()),int(frame["index"].max())+1,6)),labelExpr="['gen','feb','mar','apr','mag','giu','lug','ago','set','ott','nov','dic'][datum.value % 12] + ' ' + (2021 + floor(datum.value / 12))",labelAngle=0)),
        y=alt.Y("value:Q",title="Unità di prodotto",scale=alt.Scale(zero=True),axis=alt.Axis(format=".0f")),
        color=alt.Color("series:N",scale=alt.Scale(domain=color_order,range=COLORS[:len(color_order)])),
        tooltip=[alt.Tooltip("month:N",title="Mese"),alt.Tooltip("series:N",title="Serie"),alt.Tooltip("display:N",title="Unità")],
    )
    st.altair_chart(style_chart(chart,height),use_container_width=True)


def line_rows(values,start,series):
    return [{"index":start+i,"month":month_label(start+i),"series":series,"value":v,"display":format_number(v,1)} for i,v in enumerate(values)]


@st.cache_data(show_spinner=False)
def analyze(item,parameters,capacity=None):
    return run_analysis(item,Scenario(**parameters),capacity)


with st.sidebar:
    st.markdown("### Configura il laboratorio")
    item_id = st.selectbox("Articolo",[item["id"] for item in CATALOG],format_func=lambda key:next(i["name"] for i in CATALOG if i["id"]==key),key="item_id",on_change=reset_controls)
    item = next(item for item in CATALOG if item["id"]==item_id)
    st.caption(item["pattern"]+" · unità/mese")
    st.selectbox("Esperimento guidato",PRESETS,key="preset",on_change=apply_preset)
    st.markdown("#### Domanda")
    st.select_slider("Variabilità ×",options=[i/10 for i in range(31)],format_func=lambda v:format_number(v,1),key="noise",help="Moltiplica lo stesso rumore casuale dello scenario iniziale. Il seme resta invariato.")
    st.select_slider("Trend aggiuntivo (% della base/mese)",options=[i/10 for i in range(-10,21)],format_func=lambda v:format_number(v,1),key="trend",help="Aggiunge una pendenza al trend originale, applicata a tutta la serie simulata.")
    st.slider("Stagionalità aggiuntiva (punti %)",0,80,step=5,key="seasonality",help="Aumenta l'ampiezza del ciclo annuale, con picco a luglio. L'ampiezza totale è limitata al 95%.")
    st.markdown("#### Approvvigionamento")
    st.slider("Lead time (mesi)",1,6,key="lead_time")
    st.slider("Lotto di riordino (unità)",50,1000,step=50,key="order_quantity")
    st.slider("Livello di servizio obiettivo (%)",80,99,key="service_level",help="Probabilità teorica di non esaurire la scorta nel lead time; non è il tasso di domanda soddisfatta.")
    st.select_slider("Capacità / domanda media iniziale",options=[1+i/20 for i in range(21)],format_func=lambda v:format_number(v,2),key="capacity_factor",help="Capacità mensile costante di ricezione, riferita alla previsione media dello scenario iniziale.")
    st.button("Ripristina lo scenario iniziale",on_click=reset_controls,use_container_width=True)
    st.caption("Gli esperimenti modificano l'intera storia simulata: sono confronti controfattuali, non shock applicati solo al futuro.")

parameters = {key:st.session_state[key] for key in DEFAULTS}
parameters["service_level"] /= 100
baseline = analyze(item,asdict(Scenario()))
reference_mean = mean(baseline["inventory"]["forecast"])
current = analyze(item,parameters,reference_mean*parameters["capacity_factor"])
selected = current["evaluation"]["selected"]
inv = current["inventory"]
base_inv = baseline["inventory"]
selected_row = next(r for r in current["evaluation"]["results"] if r["method"]==selected)

st.markdown('<div class="lab-kicker">DEMAND LAB / CASO DIDATTICO DECATHLON</div>',unsafe_allow_html=True)
st.title("Prevedere la domanda. Pianificare le scorte.")
st.markdown("Esplora come **variabilità, trend, stagionalità e tempi di fornitura** cambiano le decisioni di magazzino.")
st.caption("Impresa reale · magazzino ipotetico · 240 osservazioni simulate, gennaio 2021 – dicembre 2025 · nessun dato interno aziendale")

c1,c2,c3,c4 = st.columns(4)
c1.metric("Previsione annuale",format_number(sum(inv["forecast"])),delta=display_delta(sum(inv["forecast"])-sum(base_inv["forecast"])),delta_color="off")
c2.metric("MAE · test 2025",format_number(selected_row["test"]["mae"],1)+" unità")
c3.metric("Scorta di sicurezza",format_number(inv["safety"],1),delta=display_delta(inv["safety"]-base_inv["safety"],1),delta_color="off")
c4.metric("Pipeline stimata",format_number(inv["pipeline"],1),delta=display_delta(inv["pipeline"]-base_inv["pipeline"],1),delta_color="off")
st.caption("Le variazioni indicano lo scostamento dallo scenario iniziale. Le quantità previste sono valori attesi: possono essere frazionarie.")

history_tab, accuracy_tab, inventory_tab, methodology_tab = st.tabs(["Domanda e previsioni","Accuratezza dei metodi","Scorte e scenari","Metodo e dati"])
with history_tab:
    st.subheader(item["name"])
    st.markdown("**Metodo selezionato sul 2024:** "+METHOD_NAMES[selected])
    start_index = 24
    rows = line_rows(baseline["demand"][start_index:],start_index,"Storico iniziale")
    rows += line_rows(current["demand"][start_index:],start_index,"Storico modificato")
    rows += line_rows(base_inv["forecast"],60,"Previsione iniziale")
    rows += line_rows(inv["forecast"],60,"Previsione modificata")
    demand_chart(rows,["Storico iniziale","Storico modificato","Previsione iniziale","Previsione modificata"])
    st.caption("Grafico dal 2023 per leggibilità; il modello usa tutti i 60 mesi disponibili. Le previsioni 2026 sono stime, senza valori futuri osservati.")
    st.info("Per isolare un effetto modifica una sola caratteristica, mantenendo gli stessi numeri casuali. Se i due scenari coincidono, le linee si sovrappongono.")
    with st.expander("Confronta le previsioni di tutti i metodi"):
        all_rows=[]
        for method in METHOD_NAMES:
            all_rows += line_rows(forecast(current["demand"],method,12),60,METHOD_NAMES[method])
        demand_chart(all_rows,list(METHOD_NAMES.values()),300)

with accuracy_tab:
    st.subheader("Scegliere prima, verificare dopo")
    st.markdown("**2021–2023:** storia iniziale · **2024:** selezione con MAE minimo · **2025:** test successivo. Ogni previsione usa soltanto i mesi precedenti.")
    results=current["evaluation"]["results"]
    table=[]
    for row in results:
        table.append([METHOD_NAMES[row["method"]],*[format_number(row[part][metric],1) for part,metric in [("validation","mae"),("test","mae"),("test","rmse"),("test","bias")]]])
    display_table(["Metodo","MAE selezione 2024","MAE test 2025","RMSE test 2025","Bias test 2025"],table,next(i for i,r in enumerate(results) if r["method"]==selected))
    st.caption("Riga evidenziata: metodo scelto sul 2024. MAE e RMSE minori indicano errori inferiori; bias positivo indica sottostima. Unità: pezzi/mese. I parametri dei metodi sono fissi.")
    bars=pd.DataFrame([{"method":METHOD_NAMES[r["method"]],"error":r[part]["mae"],"period":label,"display":format_number(r[part]["mae"],1)} for r in results for part,label in [("validation","Selezione 2024"),("test","Test 2025")]])
    chart=alt.Chart(bars).mark_bar(cornerRadiusEnd=3).encode(y=alt.Y("method:N",title=None,sort=list(METHOD_NAMES.values()),axis=alt.Axis(labelLimit=310)),x=alt.X("error:Q",title="Errore medio assoluto (unità)",axis=alt.Axis(format=".0f")),color=alt.Color("period:N",scale=alt.Scale(domain=["Selezione 2024","Test 2025"],range=COLORS[:2])),yOffset="period:N",tooltip=[alt.Tooltip("method:N",title="Metodo"),alt.Tooltip("period:N",title="Periodo"),alt.Tooltip("display:N",title="MAE")])
    st.altair_chart(style_chart(chart,340),use_container_width=True)
    st.markdown("**Controllo sul periodo di test**")
    test_rows=line_rows(current["demand"][48:60],48,"Domanda osservata")+line_rows(selected_row["test_predictions"],48,"Previsione a un mese")
    demand_chart(test_rows,["Domanda osservata","Previsione a un mese"],260)
    st.caption("Nel test il modello viene ristimato ogni mese con i dati allora disponibili; l'identità del metodo resta quella scelta nel 2024. Gli errori a un mese non misurano direttamente la qualità delle previsioni a dodici mesi.")

with inventory_tab:
    st.subheader("Dalla previsione alla pianificazione")
    display_table(["Indicatore stimato","Scenario iniziale","Scenario modificato","Differenza"],[[label,format_number(base_inv[key],1),format_number(inv[key],1),format_number(inv[key]-base_inv[key],1)] for key,label in [("cycle","Scorta ciclica media · Q/2"),("safety","Scorta di sicurezza"),("pipeline","Pipeline al momento della pianificazione"),("reorder_point","Punto di riordino indicativo")]]+[["Scorta anticipata media",format_number(base_inv["anticipation"]["average"],1),format_number(inv["anticipation"]["average"],1),format_number(inv["anticipation"]["average"]-base_inv["anticipation"]["average"],1)]])
    stock_rows=[]
    for label,result in [("Iniziale",base_inv),("Modificato",inv)]:
        for kind,value in [("Ciclica",result["cycle"]),("Sicurezza",result["safety"]),("Anticipata",result["anticipation"]["average"]),("Pipeline",result["pipeline"])]:
            stock_rows.append({"scenario":label,"kind":kind,"value":value,"display":format_number(value,1)})
    chart=alt.Chart(pd.DataFrame(stock_rows)).mark_bar(cornerRadiusEnd=3).encode(x=alt.X("kind:N",title=None,sort=["Ciclica","Sicurezza","Anticipata","Pipeline"]),y=alt.Y("value:Q",title="Unità stimate",axis=alt.Axis(format=".0f")),xOffset="scenario:N",color=alt.Color("scenario:N",scale=alt.Scale(domain=["Iniziale","Modificato"],range=COLORS[:2])),tooltip=[alt.Tooltip("kind:N",title="Tipologia"),alt.Tooltip("scenario:N",title="Scenario"),alt.Tooltip("display:N",title="Unità")])
    st.altair_chart(style_chart(chart,300),use_container_width=True)
    st.caption("Confronto delle quattro tipologie, senza sommarle: pipeline è merce in transito, ciclica e anticipata sono medie teoriche con criteri diversi. Non è una simulazione integrata dell'inventario fisico.")
    st.markdown("#### Scorte anticipate: prepararsi al picco")
    plan=inv["anticipation"]
    st.markdown("Capacità mensile costante: **"+format_number(plan["capacity"],1)+" unità**. Scorta anticipata massima richiesta: **"+format_number(plan["peak"],1)+" unità**.")
    capacity_rows=line_rows(inv["forecast"],60,"Domanda prevista")+line_rows([plan["capacity"]]*12,60,"Capacità mensile")+line_rows(plan["buffers"][:-1],60,"Scorta anticipata a inizio mese")
    demand_chart(capacity_rows,["Domanda prevista","Capacità mensile","Scorta anticipata a inizio mese"],280)
    if plan["initial"]>0.01:
        st.warning("Il piano richiede "+format_number(plan["initial"],1)+" unità di scorta anticipata già disponibili il 01/01/2026. Senza questa disponibilità, o senza preparazione nei mesi precedenti, il piano non è attuabile.")
    st.caption("Piano deterministico di 12 mesi, buffer finale nullo, ricezioni prima della domanda e capacità riferita agli arrivi. Il lead time richiede ordini anticipati; il piano non ricostruisce gli ordini già emessi.")
    with st.expander("Ipotesi e limiti delle stime"):
        st.markdown("La **scorta ciclica Q/2** assume consumo regolare e reintegro a lotto. È un riferimento teorico, meno rappresentativo per domanda molto stagionale. La **pipeline** è la somma delle previsioni nei prossimi L mesi, non una misura di ordini realmente in viaggio.")
        st.markdown("La **sicurezza** è z × deviazione standard degli errori cumulati sul lead time. Gli errori sono stimati solo sul 2024, con "+str(inv["calibration_windows"])+" finestre sovrapposte. L'approssimazione normale e il campione ridotto non garantiscono il servizio obiettivo.")
        st.markdown("Errore cumulato medio sul lead time: **"+format_number(inv["bias_lead"],1)+" unità**. Il bias è segnalato ma non corretto automaticamente. Il punto di riordino è indicativo per revisione continua con lead time costante; una revisione mensile richiederebbe anche il periodo di revisione.")
        st.markdown("Le scorte anticipate derivano da un bilancio autonomo con capacità limitata. Non sono sommate a ciclica e sicurezza per evitare una falsa precisione sulla giacenza totale.")

with methodology_tab:
    st.subheader("Un caso reale, ipotesi trasparenti")
    st.markdown("**Decathlon** è il riferimento aziendale per il settore degli articoli sportivi. Il magazzino, gli articoli generici, la domanda e tutti i parametri logistici del laboratorio sono ipotetici. Il progetto non descrive le politiche effettive dell'impresa e non è affiliato all'azienda.")
    display_table(["Articolo generico","Andamento simulato"],[[i["name"],i["pattern"]] for i in CATALOG])
    st.markdown("**Riproducibilità.** Ogni articolo ha un seme fisso. Il CSV iniziale è letto e verificato contro il generatore; gli scenari modificati vengono rigenerati con lo stesso rumore di partenza.")
    published=pd.read_csv(ROOT/"data/demand.csv")
    published_values=published.loc[published.item_id==item_id,"demand"].tolist()
    if published_values != baseline["demand"]:
        st.error("Il CSV iniziale non coincide con il generatore: rigenerare i dati prima di interpretare i risultati.")
    else:
        st.success("Coerenza verificata tra CSV pubblicato e serie iniziale dell'articolo selezionato.")
    st.markdown("**Metodi.** Media mobile a tre mesi con previsione piatta; regressione lineare per il trend; naïve stagionale, che ripete la domanda dello stesso mese dell'anno precedente.")
    st.markdown("**Limiti.** Nessun prezzo, costo, vincolo multiarticolo, promozione, reso o variabilità del lead time. Domanda irregolare ottenuta da rumore normale troncato a zero, senza modello specifico per domanda intermittente. Nessuna validazione su dati aziendali reali.")
    st.markdown("**Fonti di approfondimento**")
    st.markdown("- [Decathlon · risultati del gruppo 2025](https://www.decathlon-united.media/pressfiles/2025results)\n- [Hyndman e Athanasopoulos · valutazione delle previsioni](https://otexts.com/fpp3/toolbox.html)\n- [SAP · pianificazione delle scorte di sicurezza](https://help.sap.com/docs/SAP_SUPPLY_CHAIN_MANAGEMENT/0bad972d62de4005822fdcbce98f8748/9e40c95360267614e10000000a174cb4.html)\n- [Stlite · documentazione](https://github.com/whitphx/stlite)")
    st.markdown("#### Esporta l'esperimento")
    export_frame=pd.DataFrame({"date":[date(2021+i//12,i%12+1,1).isoformat() for i in range(72)],"baseline_demand":baseline["demand"]+[None]*12,"scenario_demand":current["demand"]+[None]*12,"baseline_forecast":[None]*60+base_inv["forecast"],"scenario_forecast":[None]*60+inv["forecast"]})
    st.download_button("Scarica domanda e previsioni (CSV)",export_frame.to_csv(index=False,sep=";",decimal=","),file_name=f"{item_id}_experiment.csv",mime="text/csv",use_container_width=True)
    export_payload={"item_id":item_id,"parameters":parameters,"baseline_parameters":asdict(Scenario()),"results":current,"baseline_results":baseline,"data_status":"synthetic","seed":item["seed"]}
    st.download_button("Scarica parametri e risultati (JSON)",json.dumps(export_payload,ensure_ascii=False,indent=2),file_name=f"{item_id}_experiment.json",mime="application/json",use_container_width=True)
    st.caption("CSV: separatore punto e virgola, virgola decimale; intestazioni in inglese per coerenza con il codice. JSON: valori numerici nel formato standard.")

st.markdown('<p class="lab-note">Project work 24 - Giovanni Martusciello · risultati illustrativi, da interpretare entro le ipotesi del modello.</p>',unsafe_allow_html=True)
