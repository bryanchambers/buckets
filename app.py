from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
from passlib import hash
import json
import os

app = Flask(__name__)
app.secret_key = 'XnD8dR0fwqSprw1BbU4MOyISBuen3fEK3Jc2'

app.debug = True

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/www/buckets/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)





class User(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    password = db.Column(db.String(100))


class Bucket(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(50))
    balance   = db.Column(db.Integer)
    refill    = db.Column(db.Integer)
    size      = db.Column(db.Integer)
    purchases = db.relationship('Purchase', backref='bucket')


class Purchase(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    bucket_id = db.Column(db.Integer, db.ForeignKey('bucket.id'))
    desc      = db.Column(db.String(150))
    amount    = db.Column(db.Integer)
    date      = db.Column(db.DateTime)





@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'submit' in request.form:
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.password:
            if hash.pbkdf2_sha256.verify(password, user.password):
                session['user'] = { 'id': user.id, 'username': user.username }
                return redirect('/')

    return render_template('login.html', title='Login')





@app.route('/')
def home():
    results = Bucket.query.all()
    buckets = []

    for bucket in results:
        available = min(int((bucket.balance / bucket.size) * 100), 100) if bucket.balance > 0 else 0

        buckets.append({
            'id':      bucket.id,
            'name':    bucket.name,
            'balance': bucket.balance,
            'refill':  bucket.refill,
            'size':    bucket.size,
            'outlook': bucket.balance + bucket.refill,
            'width':   available,
            'hue':     int(available * 2.2)
        })

    backup()
    return render_template('home.html', buckets=buckets, title='Buckets')





@app.route('/timezone')
def get_timezone():
    return render_template('timezone.html')





@app.route('/buckets/<int:id>', methods=['GET', 'POST'])
def bucket(id):
    bucket = Bucket.query.get(id)

    if 'submit' in request.form:
        amount = int(request.form['amount'])
        desc   = str(request.form['desc'])
        day    = str(request.form['day'])
        time   = str(request.form['time'])
        offset = int(request.form['tz-offset'])

        if day == 'today':
            if time == 'now':
                timestamp = datetime.utcnow()

            else:
                today     = datetime.strftime(datetime.utcnow() - timedelta(minutes=offset), '%Y-%m-%d')
                timestamp = datetime.strptime(today + '_' + time, '%Y-%m-%d_%H:%M') + timedelta(minutes=offset)

        else:
            if time == 'now': timestamp = False
            else: timestamp = datetime.strptime(day + '_' + time, '%Y-%m-%d_%H:%M') + timedelta(minutes=offset)

        if timestamp:
            bucket.balance = bucket.balance - amount
            purchase = Purchase(desc=desc, amount=amount, bucket=bucket, date=timestamp)

            db.session.add(purchase)
            db.session.commit()
            return redirect('/')

    times = [{'display': 'Now', 'value': 'now'}]

    for h in range(9, 22):
        hour   = str(h) if h <= 12 else str(h - 12)
        period =   'am' if h <  12 else 'pm'

        times.append({
            'display': hour + period,
            'value':   str(h).zfill(2) + ':00'
        })

    return render_template('bucket.html', bucket=bucket, title=bucket.name, times=times)





@app.route('/buckets/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    bucket = Bucket.query.get(id)

    if 'submit' in request.form:
        name    = request.form['name']
        size    = request.form['size']
        refill  = request.form['refill']
        balance = request.form['bal']

        bucket.name   = name
        bucket.size   = int(size) if size != '' else 100
        bucket.refill = int(refill) if refill != '' else 0
        if balance != '': bucket.balance = int(balance)

        db.session.commit()
        return redirect('/buckets/' + str(bucket.id))

    return render_template('edit-bucket.html', bucket=bucket, title='Edit Bucket')





@app.route('/buckets/<int:id>/delete')
def delete(id):
    #backup()
    #bucket = Bucket.query.get(id)

    #db.session.delete(bucket)
    #db.session.commit()
    return redirect('/')





@app.route('/buckets/new', methods=['GET', 'POST'])
def new_bucket():
    if 'submit' in request.form:
        name = request.form['name']
        name = name if name != '' else 'Bucket'

        size = request.form['size']
        size = int(size) if size != '' else 100

        refill = request.form['refill']
        refill = int(refill) if refill != '' else 0

        balance = request.form['bal']
        balance = int(balance) if balance != '' else 0

        bucket = Bucket(name=name, balance=balance, refill=refill, size=size)

        db.session.add(bucket)
        db.session.commit()
        return redirect('/')

    return render_template('edit-bucket.html', title='New Bucket')





@app.route('/buckets/refill')
def refill():
    dir  = os.path.dirname(os.path.abspath(__file__))
    path = dir + '/refill.txt'

    try:
        with open(path, 'r') as file:
            data = file.read().strip()
            file.close()

    except FileNotFoundError as e:
        error = 'Oh no! Could not find last refill date. Aborting refill. Details: ' + str(e)
        return render_template('refill.html', title='Next Refill', error=error)

    format = '%Y-%m-%d %H:%M:%S'

    try: last = datetime.strptime(data, format)

    except ValueError as e:
        error = 'Oh no! Error reading refill date. Aborting refill. Details: ' + str(e)
        return render_template('refill.html', title='Next Refill', error=error)

    buckets = Bucket.query.all()

    next = last + timedelta(days=7)
    left = next - datetime.utcnow()

    if next < datetime.utcnow():
        day   = next.weekday()
        shift = day - 4 if day >= 4 else day + 3

        refill_date = next - timedelta(days=shift)
        refill_date = refill_date.replace(hour=18, minute=0, second=0, microsecond=0)

        with open(path, 'w') as file:
            file.write(datetime.strftime(refill_date, format))
            file.close()

        for bucket in buckets:
            refill = bucket.refill if bucket.refill else 0
            bucket.balance = bucket.balance + refill

        db.session.commit()
        return redirect('/')

    else:
        h = left.seconds // 3600
        m = (left.seconds - (h * 3600)) // 60
        return render_template('refill.html', title='Next Refill', days=left.days, hours=h, minutes=m)





@app.route('/purchases', methods=['GET', 'POST'])
def purchases():
    if request.form:
        if 'tz-offset' in request.form:
            purchases = Purchase.query.order_by(Purchase.date.desc()).limit(100)
            offset    = int(round(float(request.form['tz-offset']) / 60, 0)) * -1

            for purchase in purchases:
                purchase.date = purchase.date + timedelta(hours=offset)

            return render_template('purchases.html', purchases=purchases, title='Purchases')

        else: return redirect('/')

    else: return render_template('timezone.html', url='/purchases')





@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'submit' in request.form:
        from_bucket = Bucket.query.get(int(request.form['from']))
        to_bucket   = Bucket.query.get(int(request.form['to']))
        amount      = int(request.form['amount'])

        from_bucket.balance = from_bucket.balance - amount
        to_bucket.balance   = to_bucket.balance   + amount

        db.session.commit()
        return redirect('/')

    buckets = Bucket.query.all()
    return render_template('transfer.html', buckets=buckets, title='Transfer')





def backup():
    dir  = os.path.dirname(os.path.abspath(__file__))
    path = dir + '/backup.json'

    try:
        with open(path, 'r') as file:
            data = json.load(file)
            file.close()

    except (FileNotFoundError, ValueError): data = {}

    for bucket_name in data:
        data[bucket_name]['updated'] = False

    for bucket in Bucket.query.all():
        if not bucket.name in data: data[bucket.name] = {}

        data[bucket.name]['balance'] = bucket.balance
        data[bucket.name]['refill']  = bucket.refill
        data[bucket.name]['size']    = bucket.size
        data[bucket.name]['updated'] = True

    for bucket_name in data:
        data[bucket_name]['deleted'] = not data[bucket_name]['updated']
        del data[bucket_name]['updated']

    with open(path, 'w') as file:
        json.dump(data, file)
        file.close()





if __name__ == '__main__':
    app.run()
