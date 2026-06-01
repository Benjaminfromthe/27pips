from flask import Blueprint, jsonify
education_bp = Blueprint('education', __name__)

# Sample lesson data — replace with DB later
LESSONS = [
    {'id': 1, 'title': 'What is Forex?',         'module': 'Pre-School', 'completed': False},
    {'id': 2, 'title': 'Currency Pairs Explained','module': 'Pre-School', 'completed': False},
    {'id': 3, 'title': 'How to Read a Chart',     'module': 'Pre-School', 'completed': False},
    {'id': 4, 'title': 'Pips and Lots',           'module': 'Pre-School', 'completed': False},
    {'id': 5, 'title': 'Bid, Ask and Spread',     'module': 'Pre-School', 'completed': False},
    {'id': 6, 'title': 'Support and Resistance',  'module': 'Elementary',  'completed': False},
    {'id': 7, 'title': 'Trend Lines',             'module': 'Elementary',  'completed': False},
    {'id': 8, 'title': 'Candlestick Patterns',    'module': 'Elementary',  'completed': False},
]

@education_bp.route('/lessons')
def get_lessons():
    return jsonify(LESSONS)
