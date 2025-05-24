import sqlite3
import random
from pathlib import Path

from flask import Flask, render_template_string

#llamado base de datos

DB_FILE = "data.db"
app = Flask(__name__)



def init_db():
    if Path(DB_FILE).exists():
        return

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            total_balance REAL,
            invested_amount REAL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE ventures (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            status TEXT  -- impactado | maduro | otro
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE global_stats (
            id INTEGER PRIMARY KEY,
            economic_growth_impact REAL,
            crime_reduction REAL
        );
        """
    )

    # Datos de clientes
    customers = [
        (1, "Cliente Ejemplo", 1_500_000, 1_000_000),
        (2, "Cliente Beta",    2_200_000, 1_500_000),
        (3, "Cliente Gamma",     800_000,   300_000),
    ]
    cur.executemany("INSERT INTO customers VALUES (?,?,?,?);", customers)

    statuses = ["impactado", "maduro", "otro"]
    vid = 1
    rows = []
    random.seed(42)
    for cust_id in [1, 2, 3]:
        for _ in range(random.randint(5, 15)):
            rows.append((vid, cust_id, random.choice(statuses)))
            vid += 1
    cur.executemany("INSERT INTO ventures VALUES (?,?,?);", rows)

    cur.execute("INSERT INTO global_stats VALUES (1, 12.5, 3.2);")

    conn.commit()
    conn.close()


def get_metrics(customer_id: int = 1):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT total_balance, invested_amount FROM customers WHERE id=?;", (customer_id,))
    tb, inv = cur.fetchone()

    cur.execute("SELECT SUM(invested_amount) FROM customers;")
    total_fund = cur.fetchone()[0] or 1
    participation_pct = (inv / total_fund) * 100


    cur.execute("SELECT status, COUNT(*) FROM ventures WHERE customer_id=? GROUP BY status;", (customer_id,))
    dist = dict(cur.fetchall())
    impacted = dist.get("impactado", 0)
    mature = dist.get("maduro", 0)

    cur.execute("SELECT economic_growth_impact, crime_reduction FROM global_stats WHERE id=1;")
    econ, crime = cur.fetchone()

    conn.close()

    labels = list(dist.keys())
    counts = list(dist.values())

    return {
        "total_balance": tb,
        "invested_amount": inv,
        "total_balance_fmt": f"{tb:,.2f}",
        "invested_amount_fmt": f"{inv:,.2f}",
        "impacted": impacted,
        "mature": mature,
        "participation_pct": participation_pct,
        "participation_pct_fmt": f"{participation_pct:.2f}",
        "econ_impact_fmt": f"{econ:.2f}",
        "crime_red_fmt": f"{crime:.2f}",
        "status_labels": labels,
        "status_counts": counts,
    }

#incrustación

@app.route("/")
def dashboard():
    m = get_metrics(1)
    html = """
    <!DOCTYPE html>
    <html lang='es'>
    <head>
        <meta charset='UTF-8'>
        <title>Dashboard del Cliente</title>
        <script src='https://cdn.plot.ly/plotly-latest.min.js'></script>
        <style>
            body{font-family:Arial;margin:0;background:#f4f6f7;color:#333;}
            .wrapper{max-width:1200px;margin:40px auto;padding:0 20px;}
            h2{text-align:center;margin-bottom:30px;}
            .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:20px;}
            .card{background:#fff;padding:20px;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,.1);text-align:center;}
            .card span{font-size:2rem;font-weight:700;display:block;}
            .card h3{margin:10px 0 0;font-size:1.1rem;font-weight:600;}
            .chart-container{background:#fff;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,.1);padding:20px;margin-top:40px;}
            .charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;}
        </style>
    </head>
    <body>
        <div class='wrapper'>
            <h2>Dashboard del Cliente (Métricas)</h2>
            <div class='grid'>
                <div class='card'><span>{{ total_balance_fmt }} COP</span><h3>Monto total en la cuenta</h3></div>
                <div class='card'><span>{{ invested_amount_fmt }} COP</span><h3>Monto invertido</h3></div>
                <div class='card'><span>{{ impacted }}</span><h3>Emprendimientos impactados</h3></div>
                <div class='card'><span>{{ mature }}</span><h3>Emprendimientos maduros</h3></div>
                <div class='card'><span>{{ participation_pct_fmt }}%</span><h3>Participación en el fondo</h3></div>
                <div class='card'><span>{{ econ_impact_fmt }}%</span><h3>Impacto econ. global</h3></div>
                <div class='card'><span>{{ crime_red_fmt }}%</span><h3>Reducción delincuencia</h3></div>
            </div>
            <br/>
            <div class='charts'>
                <div id='pie'></div>
                <div id='bar'></div>
                <div id='gauge'></div>
                <div id='balance-bar'></div>
            </div>
        </div>

        <script>
        const labels = {{ status_labels | tojson }};
        const counts = {{ status_counts | tojson }};
        // 1. Pie chart
        Plotly.newPlot('pie',[{labels:labels,values:counts,type:'pie',textinfo:'label+percent'}],{title:'Distribución de estados'});
        // 2. Bar chart
        Plotly.newPlot('bar',[{x:labels,y:counts,type:'bar'}],{title:'Conteo de emprendimientos',yaxis:{title:'Cantidad'}});
        // 3. Gauge de participación
        Plotly.newPlot('gauge',[{
            type:'indicator',mode:'gauge+number',value:{{ participation_pct }},
            gauge:{axis:{range:[0,100]},bar:{color:'#17a2b8'}},title:{text:'% Participación'}
        }]);
        // 4. Bar horizontal balance vs invertido
        Plotly.newPlot('balance-bar',[{
            y:['Monto invertido','Saldo total'],
            x:[{{ invested_amount }},{{ total_balance }}],
            type:'bar',orientation:'h'
        }],{title:'Comparativo saldo / inversión',xaxis:{title:'COP'}});
        </script>
    </body>
    </html>
    """
    return render_template_string(html, **m)

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)

