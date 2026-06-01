from flask import Blueprint, jsonify
signals_bp = Blueprint('signals', __name__)

# Sample signals — replace with live feed later
SIGNALS = [
    {'id':1,'asset':'EUR/USD','action':'BUY', 'entry':'1.0850','sl':'1.0800','tp1':'1.0900','tp2':'1.0950','status':'ACTIVE'},
    {'id':2,'asset':'GBP/USD','action':'SELL','entry':'1.2700','sl':'1.2750','tp1':'1.2650','tp2':'1.2600','status':'ACTIVE'},
    {'id':3,'asset':'XAU/USD','action':'BUY', 'entry':'2320.00','sl':'2300.00','tp1':'2350.00','tp2':'2380.00','status':'HIT TP1'},
    {'id':4,'asset':'USD/JPY','action':'SELL','entry':'154.50','sl':'155.00','tp1':'154.00','tp2':'153.50','status':'CLOSED'},
    {'id':5,'asset':'NAS100', 'action':'BUY', 'entry':'18200','sl':'18000','tp1':'18500','tp2':'18800','status':'ACTIVE'},
]

@signals_bp.route('/')
def get_signals():
    return jsonify(SIGNALS)
