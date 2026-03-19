"""
FoodIQ - Complete Backend (single file, no imports from subfolders)
Run with: python app.py
"""

import os, sys, random, math
from datetime import datetime, date, timedelta

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# ─────────────────────────────────────────────────────────────────────────────
#  APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Auto-detect frontend folder: checks sibling 'frontend/' first, then same folder
def find_frontend():
    # Option 1: frontend/ is next to backend/ folder  (Foodiq 2.0/frontend)
    sibling = os.path.join(BASE_DIR, '..', 'frontend')
    if os.path.isdir(sibling) and os.path.exists(os.path.join(sibling, 'login.html')):
        return os.path.abspath(sibling)
    # Option 2: HTML files are in the same folder as app.py
    if os.path.exists(os.path.join(BASE_DIR, 'login.html')):
        return BASE_DIR
    # Option 3: frontend/ is inside backend/ folder
    inner = os.path.join(BASE_DIR, 'frontend')
    if os.path.isdir(inner):
        return inner
    # Fallback: use BASE_DIR and print a warning
    print("WARNING: Could not find frontend folder. Put HTML files next to app.py or in ../frontend/")
    return BASE_DIR

FRONTEND_DIR = find_frontend()
print(f"Serving frontend from: {FRONTEND_DIR}")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'foodiq.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'foodiq-secret-key-2024'

db = SQLAlchemy(app)


# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE MODELS
# ─────────────────────────────────────────────────────────────────────────────

class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    price      = db.Column(db.Float, nullable=False)
    category   = db.Column(db.String(50), nullable=False)
    type       = db.Column(db.String(50), nullable=False)
    cost       = db.Column(db.Float, default=0.0)
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "price": self.price,
                "category": self.category, "type": self.type, "cost": self.cost}


class Order(db.Model):
    __tablename__ = 'orders'
    id             = db.Column(db.Integer, primary_key=True)
    order_date     = db.Column(db.Date, default=date.today)
    order_time     = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount   = db.Column(db.Float, default=0.0)
    payment_method = db.Column(db.String(30), default='cash')
    status         = db.Column(db.String(20), default='completed')
    customer_name  = db.Column(db.String(100), default='Walk-in')
    items          = db.relationship('OrderItem', backref='order', lazy=True,
                                     cascade='all, delete-orphan')

    def to_dict(self):
        return {"id": self.id, "order_date": str(self.order_date),
                "total_amount": self.total_amount, "payment_method": self.payment_method,
                "status": self.status, "customer_name": self.customer_name,
                "items": [i.to_dict() for i in self.items]}


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id           = db.Column(db.Integer, primary_key=True)
    order_id     = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'))
    name         = db.Column(db.String(100))
    price        = db.Column(db.Float)
    cost         = db.Column(db.Float, default=0.0)
    quantity     = db.Column(db.Integer, default=1)

    def to_dict(self):
        return {"menu_item_id": self.menu_item_id, "name": self.name,
                "price": self.price, "quantity": self.quantity}


class WastageRecord(db.Model):
    __tablename__ = 'wastage_records'
    id                = db.Column(db.Integer, primary_key=True)
    item_name         = db.Column(db.String(100), nullable=False)
    quantity_prepared = db.Column(db.Float, default=0)
    quantity_consumed = db.Column(db.Float, default=0)
    quantity_wasted   = db.Column(db.Float, default=0)
    date              = db.Column(db.Date, default=date.today)
    broadcast_to_ngo  = db.Column(db.Boolean, default=False)
    lat               = db.Column(db.Float, default=19.1)
    lng               = db.Column(db.Float, default=72.8)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        prep = self.quantity_prepared or 0
        wasted = self.quantity_wasted or 0
        return {
            "id": self.id, "item_name": self.item_name, "dish_name": self.item_name,
            "quantity_prepared": round(prep, 2),
            "quantity_consumed": round(self.quantity_consumed or 0, 2),
            "surplus": round(wasted, 2), "date": str(self.date),
            "broadcast_to_ngo": self.broadcast_to_ngo,
            "waste_rate_percent": round((wasted / prep * 100) if prep else 0, 2),
        }


class AutomationRule(db.Model):
    __tablename__ = 'automation_rules'
    id         = db.Column(db.Integer, primary_key=True)
    item_name  = db.Column(db.String(100), nullable=False)
    limit_kg   = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "item": self.item_name, "limit_kg": self.limit_kg}


class NGOAlert(db.Model):
    __tablename__ = 'ngo_alerts'
    id          = db.Column(db.Integer, primary_key=True)
    item_name   = db.Column(db.String(100))
    quantity_kg = db.Column(db.Float)
    lat         = db.Column(db.Float)
    lng         = db.Column(db.Float)
    status      = db.Column(db.String(20), default='pending')
    ngo_name    = db.Column(db.String(150))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "item_name": self.item_name, "quantity_kg": self.quantity_kg,
                "status": self.status, "ngo_name": self.ngo_name,
                "lat": self.lat, "lng": self.lng, "created_at": str(self.created_at)}


# ─────────────────────────────────────────────────────────────────────────────
#  SEED DATA
# ─────────────────────────────────────────────────────────────────────────────

MENU_SEED = [
    {"name": "Veg Biryani",     "price": 80,  "cost": 35, "type": "food"},
    {"name": "Chicken Biryani", "price": 110, "cost": 55, "type": "food"},
    {"name": "Dal Rice",        "price": 60,  "cost": 20, "type": "food"},
    {"name": "Paneer Curry",    "price": 90,  "cost": 40, "type": "food"},
    {"name": "Chole Bhature",   "price": 70,  "cost": 28, "type": "food"},
    {"name": "Dosa",            "price": 50,  "cost": 18, "type": "food"},
    {"name": "Idli Sambar",     "price": 40,  "cost": 14, "type": "food"},
    {"name": "Aloo Paratha",    "price": 45,  "cost": 16, "type": "food"},
    {"name": "Chai",            "price": 15,  "cost": 4,  "type": "beverages"},
    {"name": "Coffee",          "price": 20,  "cost": 6,  "type": "beverages"},
    {"name": "Lassi",           "price": 30,  "cost": 10, "type": "beverages"},
    {"name": "Lime Water",      "price": 20,  "cost": 5,  "type": "beverages"},
    {"name": "Cold Coffee",     "price": 45,  "cost": 15, "type": "beverages"},
    {"name": "Samosa",          "price": 15,  "cost": 5,  "type": "snacks"},
    {"name": "Vada Pav",        "price": 20,  "cost": 7,  "type": "snacks"},
    {"name": "Bread Omelette",  "price": 35,  "cost": 12, "type": "snacks"},
    {"name": "Poha",            "price": 30,  "cost": 9,  "type": "snacks"},
    {"name": "Upma",            "price": 30,  "cost": 8,  "type": "snacks"},
]

DISHES_FOR_WASTAGE = [
    "Veg Biryani", "Dal Rice", "Dosa", "Idli Sambar",
    "Chole Bhature", "Poha", "Upma", "Bread Omelette"
]

CUSTOMERS = ['Walk-in','Rahul S.','Priya M.','Amit K.',
             'Sneha P.','Vijay R.','Anita D.','Ravi T.']


def seed_db():
    if MenuItem.query.count() > 0:
        return
    print("Seeding database with demo data...")
    for m in MENU_SEED:
        db.session.add(MenuItem(name=m["name"], price=m["price"],
                                cost=m["cost"], category=m["type"], type=m["type"]))
    db.session.commit()

    menu_items = MenuItem.query.all()
    today = date.today()

    for days_back in range(90, 0, -1):
        day = today - timedelta(days=days_back)
        for dish in DISHES_FOR_WASTAGE:
            prepared = random.randint(50, 200)
            consumed = int(prepared * random.uniform(0.70, 0.95))
            wasted   = prepared - consumed
            db.session.add(WastageRecord(
                item_name=dish, quantity_prepared=prepared,
                quantity_consumed=consumed, quantity_wasted=wasted,
                date=day, broadcast_to_ngo=(wasted > 30)
            ))
        for _ in range(random.randint(15, 40)):
            chosen = random.choices(menu_items, k=random.randint(1, 4))
            total  = sum(i.price for i in chosen)
            order  = Order(
                order_date=day,
                order_time=datetime(day.year, day.month, day.day,
                                    random.randint(8, 20), random.randint(0, 59)),
                total_amount=total,
                payment_method=random.choice(['cash', 'upi', 'card']),
                customer_name=random.choice(CUSTOMERS),
            )
            db.session.add(order)
            db.session.flush()
            for mi in chosen:
                db.session.add(OrderItem(order_id=order.id, menu_item_id=mi.id,
                                         name=mi.name, price=mi.price, cost=mi.cost))
    db.session.commit()
    print("Database seeded successfully!")


# ─────────────────────────────────────────────────────────────────────────────
#  SERVE FRONTEND PAGES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return send_from_directory(FRONTEND_DIR, 'login.html')

@app.route('/billing')
def billing():
    return send_from_directory(FRONTEND_DIR, 'Billing.html')

@app.route('/map')
def map_page():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/stats')
def stats_page():
    return send_from_directory(FRONTEND_DIR, 'Statistics_UI.html')

@app.route('/business')
def business_page():
    for name in ['businessdashboard.html', 'business_dashboard.html', 'BusinessDashboard.html']:
        if os.path.exists(os.path.join(FRONTEND_DIR, name)):
            return send_from_directory(FRONTEND_DIR, name)
    return 'Business dashboard not found', 404

@app.route('/wastage')
def wastage_page():
    for name in ['Wastage.html', 'waste stats.html']:
        if os.path.exists(os.path.join(FRONTEND_DIR, name)):
            return send_from_directory(FRONTEND_DIR, name)
    return 'Wastage page not found', 404

@app.route('/ngo')
def ngo_page():
    return send_from_directory(FRONTEND_DIR, 'NGOportal.html')

@app.route('/about')
def about_page():
    return send_from_directory(FRONTEND_DIR, 'aboutus.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)

@app.route('/api/health')
def health():
    return jsonify({"status": "FoodIQ API is running!", "version": "1.0"})


# ─────────────────────────────────────────────────────────────────────────────
#  MENU ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/menu', methods=['GET'])
def get_menu():
    item_type = request.args.get('type')
    query = MenuItem.query.filter_by(is_active=True)
    if item_type:
        query = query.filter_by(type=item_type)
    return jsonify([i.to_dict() for i in query.order_by(MenuItem.type, MenuItem.name).all()])


@app.route('/api/menu', methods=['POST'])
def add_menu_item():
    data = request.json or {}
    if not data.get('name') or not data.get('price'):
        return jsonify({"error": "name and price required"}), 400
    item = MenuItem(name=data['name'], price=float(data['price']),
                    cost=float(data.get('cost', 0)),
                    category=data.get('type', 'food'), type=data.get('type', 'food'))
    db.session.add(item)
    db.session.commit()
    return jsonify({"success": True, "item": item.to_dict()}), 201


@app.route('/api/menu/<int:item_id>', methods=['PUT'])
def update_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    data = request.json or {}
    if 'name'  in data: item.name  = data['name']
    if 'price' in data: item.price = float(data['price'])
    if 'cost'  in data: item.cost  = float(data['cost'])
    if 'type'  in data: item.type  = data['type']
    db.session.commit()
    return jsonify({"success": True, "item": item.to_dict()})


@app.route('/api/menu/<int:item_id>', methods=['DELETE'])
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.is_active = False
    db.session.commit()
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
#  ORDER ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/orders', methods=['POST'])
def place_order():
    data = request.json or {}
    items_data = data.get('items', [])
    if not items_data:
        return jsonify({"error": "No items in order"}), 400

    order = Order(order_date=date.today(), order_time=datetime.utcnow(),
                  payment_method=data.get('payment_method', 'cash'),
                  customer_name=data.get('customer_name', 'Walk-in'))
    db.session.add(order)
    db.session.flush()

    total = 0
    for entry in items_data:
        mi = MenuItem.query.get(entry.get('menu_item_id'))
        # Fallback: look up by name if ID not found (handles hardcoded menu items)
        if not mi and entry.get('name'):
            mi = MenuItem.query.filter(
                MenuItem.name.ilike(entry['name'].strip())
            ).first()
        # Last resort: create a snapshot item from the cart data
        if not mi:
            name  = entry.get('name', 'Unknown Item')
            price = float(entry.get('price', 0))
            qty   = int(entry.get('quantity', 1))
            total += price * qty
            db.session.add(OrderItem(
                order_id=order.id, menu_item_id=None,
                name=name, price=price, cost=0, quantity=qty
            ))
            continue
        qty    = int(entry.get('quantity', 1))
        total += mi.price * qty
        db.session.add(OrderItem(
            order_id=order.id, menu_item_id=mi.id,
            name=mi.name, price=mi.price, cost=mi.cost, quantity=qty
        ))
    order.total_amount = total
    db.session.commit()
    return jsonify({"success": True, "order_id": order.id, "total_amount": total}), 201


@app.route('/api/orders', methods=['GET'])
def get_orders():
    limit = int(request.args.get('limit', 100))
    filter_date = request.args.get('date')
    query = Order.query.order_by(Order.order_time.desc())
    if filter_date:
        d = datetime.strptime(filter_date, '%Y-%m-%d').date()
        query = query.filter(Order.order_date == d)
    return jsonify([o.to_dict() for o in query.limit(limit).all()])


@app.route('/api/orders/summary', methods=['GET'])
def orders_summary():
    rows = (db.session.query(Order.order_date,
                func.count(Order.id).label('order_count'),
                func.sum(Order.total_amount).label('daily_revenue'))
            .group_by(Order.order_date).order_by(Order.order_date.asc()).all())
    return jsonify([{"date": str(r.order_date), "order_count": r.order_count,
                     "daily_revenue": round(r.daily_revenue or 0, 2)} for r in rows])


# ─────────────────────────────────────────────────────────────────────────────
#  WASTAGE ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/wastage', methods=['POST'])
def report_wastage():
    data = request.json or {}
    item = data.get('item', '').strip()
    qty  = float(data.get('qty', 0))
    lat  = float(data.get('lat', 19.1))
    lng  = float(data.get('lng', 72.8))

    if not item or qty <= 0:
        return jsonify({"error": "item and qty > 0 required"}), 400

    rule = AutomationRule.query.filter_by(item_name=item).first()
    broadcast = bool(rule and qty > rule.limit_kg)

    db.session.add(WastageRecord(
        item_name=item, quantity_prepared=qty * 1.2,
        quantity_consumed=qty * 0.2, quantity_wasted=qty,
        date=date.today(), broadcast_to_ngo=broadcast, lat=lat, lng=lng
    ))

    if broadcast:
        db.session.add(NGOAlert(item_name=item, quantity_kg=qty, lat=lat, lng=lng))
        message = f"URGENT: {qty} kg of {item} surplus — NGOs alerted!"
        decision = 'BROADCAST'
    else:
        message = f"{qty} kg of {item} recorded. Below threshold."
        decision = 'HOLD'

    db.session.commit()
    return jsonify({"decision": decision, "message": message})


@app.route('/api/wastage', methods=['GET'])
def get_wastage():
    records = WastageRecord.query.order_by(WastageRecord.date.desc()).all()
    return jsonify([r.to_dict() for r in records])


@app.route('/api/thresholds', methods=['POST'])
def set_threshold():
    data  = request.json or {}
    item  = data.get('item', '').strip()
    limit = float(data.get('limit', 0))
    if not item or limit <= 0:
        return jsonify({"error": "item and limit > 0 required"}), 400
    rule = AutomationRule.query.filter_by(item_name=item).first()
    if rule:
        rule.limit_kg = limit
    else:
        rule = AutomationRule(item_name=item, limit_kg=limit)
        db.session.add(rule)
    db.session.commit()
    return jsonify({"success": True, "rule": rule.to_dict()})


@app.route('/api/thresholds', methods=['GET'])
def get_thresholds():
    return jsonify([r.to_dict() for r in AutomationRule.query.all()])


# ─────────────────────────────────────────────────────────────────────────────
#  STATISTICS ROUTES  (used by Statistics_UI.html)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/overall', methods=['GET'])
def overall():
    rows = WastageRecord.query.all()
    if not rows:
        return jsonify({"total_prepared": 0, "total_consumed": 0,
                        "total_wasted": 0, "waste_percent": 0,
                        "total_produced": 0, "total_served": 0,
                        "kg_saved": 0, "potential_savings": "0"})
    prep    = sum(r.quantity_prepared for r in rows)
    wasted  = sum(r.quantity_wasted   for r in rows)
    consumed= sum(r.quantity_consumed for r in rows)
    return jsonify({
        "total_prepared":   round(prep, 2),
        "total_consumed":   round(consumed, 2),
        "total_wasted":     round(wasted, 2),
        "waste_percent":    round((wasted / prep * 100) if prep else 0, 2),
        "total_produced":   int(prep),
        "total_served":     int(consumed),
        "kg_saved":         round(sum(r.quantity_wasted for r in rows if r.broadcast_to_ngo), 2),
        "potential_savings": f"Rs. {int(wasted * 15):,}",
    })


@app.route('/api/daily', methods=['GET'])
def daily():
    rows = (db.session.query(
                WastageRecord.date,
                func.sum(WastageRecord.quantity_prepared).label('prepared'),
                func.sum(WastageRecord.quantity_consumed).label('consumed'),
                func.sum(WastageRecord.quantity_wasted).label('wasted'))
            .group_by(WastageRecord.date)
            .order_by(WastageRecord.date.asc()).all())
    result = []
    for r in rows:
        prep   = r.prepared or 0
        wasted = r.wasted   or 0
        result.append({
            "date": str(r.date),
            "quantity_prepared":  round(prep, 2),
            "quantity_consumed":  round(r.consumed or 0, 2),
            "surplus":            round(wasted, 2),
            "waste_rate_percent": round((wasted / prep * 100) if prep else 0, 2),
        })
    return jsonify(result)


@app.route('/api/dishes', methods=['GET'])
def dishes():
    top_n = int(request.args.get('top', 8))
    rows  = (db.session.query(
                 WastageRecord.item_name,
                 func.sum(WastageRecord.quantity_prepared).label('prepared'),
                 func.sum(WastageRecord.quantity_wasted).label('wasted'))
             .group_by(WastageRecord.item_name).all())
    result = []
    for r in rows:
        prep   = r.prepared or 0
        wasted = r.wasted   or 0
        result.append({
            "dish_name": r.item_name,
            "quantity_prepared": round(prep, 2),
            "surplus": round(wasted, 2),
            "waste_rate_percent": round((wasted / prep * 100) if prep else 0, 2),
        })
    result.sort(key=lambda x: x['waste_rate_percent'], reverse=True)
    return jsonify(result[:top_n])


@app.route('/api/threshold', methods=['GET'])
def threshold():
    filter_date = request.args.get('date')
    threshold   = float(request.args.get('threshold', 0))
    if not filter_date:
        return jsonify({"error": "date required (YYYY-MM-DD)"}), 400
    d = datetime.strptime(filter_date, '%Y-%m-%d').date()
    records = WastageRecord.query.filter(
        WastageRecord.date == d,
        WastageRecord.quantity_wasted > threshold
    ).all()
    return jsonify([r.to_dict() for r in records])


# ─────────────────────────────────────────────────────────────────────────────
#  BUSINESS DASHBOARD ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/business_stats', methods=['GET'])
def business_stats():
    rev_row  = db.session.query(func.sum(Order.total_amount)).scalar() or 0
    cost_row = db.session.query(func.sum(OrderItem.cost * OrderItem.quantity)).scalar() or 0
    net_profit    = round(rev_row - cost_row, 2)
    profit_margin = round((net_profit / rev_row * 100) if rev_row else 0, 2)
    order_count   = Order.query.count() or 1
    avg_order_val = round(rev_row / order_count, 2)

    today      = date.today()
    thirty_ago = today - timedelta(days=30)
    daily_rows = (db.session.query(Order.order_date,
                      func.sum(Order.total_amount).label('rev'))
                  .filter(Order.order_date >= thirty_ago)
                  .group_by(Order.order_date)
                  .order_by(Order.order_date.asc()).all())

    cat_rows = (db.session.query(MenuItem.category,
                    func.sum(OrderItem.price * OrderItem.quantity).label('rev'))
                .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
                .group_by(MenuItem.category).all())

    prod_rows = (db.session.query(
                     OrderItem.name,
                     func.sum(OrderItem.price * OrderItem.quantity).label('revenue'),
                     func.sum((OrderItem.price - OrderItem.cost) * OrderItem.quantity).label('profit'))
                 .group_by(OrderItem.name)
                 .order_by(func.sum((OrderItem.price - OrderItem.cost) * OrderItem.quantity).desc())
                 .limit(10).all())

    cust_rows = (db.session.query(Order.customer_name,
                     func.sum(Order.total_amount).label('spend'))
                 .group_by(Order.customer_name)
                 .order_by(func.sum(Order.total_amount).desc())
                 .limit(10).all())

    top_products = []
    for p in prod_rows:
        rev = p.revenue or 0
        profit = p.profit or 0
        top_products.append({"name": p.name, "revenue": round(rev, 2),
                              "profit": round(profit, 2),
                              "margin": round((profit / rev * 100) if rev else 0, 2)})

    return jsonify({
        "total_revenue":       round(rev_row, 2),
        "total_expenses":      round(cost_row, 2),
        "net_profit":          net_profit,
        "profit_margin":       profit_margin,
        "avg_order_value":     avg_order_val,
        "period_labels":       [str(r.order_date) for r in daily_rows],
        "period_values":       [round(r.rev or 0, 2) for r in daily_rows],
        "revenue_by_category": {r.category: round(r.rev or 0, 2) for r in cat_rows},
        "top_products":        top_products,
        "top_customers":       [{"name": r.customer_name, "spend": round(r.spend or 0, 2)}
                                 for r in cust_rows],
    })


# ─────────────────────────────────────────────────────────────────────────────
#  NGO ROUTES
# ─────────────────────────────────────────────────────────────────────────────

NGOS = [
    {"id": 1, "name": "Khana Ghar Foundation",     "lat": 18.9818, "lng": 73.1117,
     "address": "Panvel City", "needs": "Prepared Meals, Bulk Dry Goods",
     "contact": "+91 98765 43210", "capacity_kg": 200},
    {"id": 2, "name": "Rural Food Aid Dharmasachi", "lat": 18.9105, "lng": 73.2201,
     "address": "Dharmasachi, Panvel", "needs": "Fresh Produce, Pulses",
     "contact": "+91 98765 43211", "capacity_kg": 150},
    {"id": 3, "name": "Navjeevan Food Bank",        "lat": 18.9400, "lng": 73.1450,
     "address": "Patalganga, Raigad", "needs": "Any non-expired food",
     "contact": "+91 98765 43212", "capacity_kg": 300},
    {"id": 4, "name": "Rasayani Community Kitchen", "lat": 18.8800, "lng": 73.1850,
     "address": "Rasayani, Maharashtra", "needs": "Dairy, Baked Goods",
     "contact": "+91 98765 43213", "capacity_kg": 100},
    {"id": 5, "name": "Uran Seva Samaj",            "lat": 18.8870, "lng": 72.9330,
     "address": "Uran, Raigad", "needs": "Rice, Dal, Vegetables",
     "contact": "+91 98765 43214", "capacity_kg": 180},
]


def _haversine(lat1, lng1, lat2, lng2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@app.route('/api/ngos', methods=['GET'])
def list_ngos():
    return jsonify(NGOS)


@app.route('/api/ngos/nearby', methods=['GET'])
def nearby_ngos():
    lat    = float(request.args.get('lat', 18.895))
    lng    = float(request.args.get('lng', 73.181))
    radius = float(request.args.get('radius', 20))
    result = []
    for ngo in NGOS:
        dist = _haversine(lat, lng, ngo['lat'], ngo['lng'])
        if dist <= radius:
            result.append({**ngo, "distance_km": round(dist, 2)})
    result.sort(key=lambda x: x['distance_km'])
    return jsonify(result)


@app.route('/api/ngo_alerts', methods=['GET'])
def get_ngo_alerts():
    status = request.args.get('status', 'pending')
    alerts = NGOAlert.query.filter_by(status=status)\
                           .order_by(NGOAlert.created_at.desc()).limit(50).all()
    return jsonify([a.to_dict() for a in alerts])


@app.route('/api/ngo_alerts/<int:alert_id>/accept', methods=['POST'])
def accept_alert(alert_id):
    alert = NGOAlert.query.get_or_404(alert_id)
    data  = request.json or {}
    alert.status   = 'accepted'
    alert.ngo_name = data.get('ngo_name', 'NGO Partner')
    db.session.commit()
    return jsonify({"success": True, "alert": alert.to_dict()})


# ─────────────────────────────────────────────────────────────────────────────
#  START
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_db()
    app.run(debug=True, port=5000)
