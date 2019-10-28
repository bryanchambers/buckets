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
    pod_id   = db.Column(db.Integer, db.ForeignKey('pod.id'))
    username = db.Column(db.String(100))
    password = db.Column(db.String(100))


class Pod(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(50))
    users   = db.relationship('User', backref='pod')
    buckets = db.relationship('Bucket', backref='pod')
    refill  = db.Column(db.DateTime)


class Bucket(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    pod_id    = db.Column(db.Integer, db.ForeignKey('pod.id'))
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





@app.before_request
def check_auth():
    valid  = False
    login  = request.endpoint == 'login'
    static = request.endpoint == 'static'

    if 'user' in session and not login:
        if 'id' in session['user'] and 'username' in session['user']:
            id   = int(session['user']['id'])
            user = User.query.get(id)

            if user and user.username == session['user']['username']:
                id  = int(session['user']['group']['id'])
                pod = Pod.query.get(id)

                if pod and pod.name == session['user']['group']['name']:
                    valid = True

    if not valid and not login and not static:
        return redirect('/login')





@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'submit' in request.form:
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.password and user.pod:
            if hash.pbkdf2_sha256.verify(password, user.password):

                group = { 'id': user.pod.id, 'name': user.pod.name }
                session['user'] = { 'id': user.id, 'username': user.username, 'group': group }

                session.permanent = True
                return redirect('/')

    session.permanent = False
    if 'user' in session: session.pop('user')
    return render_template('login.html', title='Login')





@app.route('/logout')
def logout():
    session.pop('user')
    session.permanent = False
    return redirect('/login')





@app.route('/password', methods=['GET', 'POST'])
def change_password():
    if 'submit' in request.form:
        current_pw = request.form['current']
        new_pw     = request.form['new']

        user = User.query.get(int(session['user']['id']))

        if user and user.password and current_pw and new_pw:
            if hash.pbkdf2_sha256.verify(current_pw, user.password):
                user.password = hash.pbkdf2_sha256.hash(new_pw)
                db.session.commit()
                return redirect('/')

    return render_template('password.html', title='Change Password')





@app.route('/username', methods=['GET', 'POST'])
def change_username():
    user = User.query.get(int(session['user']['id']))

    if 'submit' in request.form:
        username = request.form['name']

        if user and username:
            user.username = username
            db.session.commit()

            session['user']['username'] = username
            return redirect('/')

    return render_template('name.html', title='Edit Username', name=user.username)





@app.route('/group', methods=['GET', 'POST'])
def change_group_name():
    user = User.query.get(int(session['user']['id']))

    if 'submit' in request.form:
        group_name = request.form['name']

        if user and group_name:
            user.pod.name = group_name
            db.session.commit()

            session['user']['group']['name'] = group_name
            return redirect('/')

    return render_template('name.html', title='Edit Group Name', name=user.pod.name)





@app.route('/')
def home():
    pod_id  = int(session['user']['group']['id'])
    results = Bucket.query.filter_by(pod_id=pod_id).all()
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

        pod_id = int(session['user']['group']['id'])
        bucket = Bucket(pod_id=pod_id, name=name, balance=balance, refill=refill, size=size)

        db.session.add(bucket)
        db.session.commit()
        return redirect('/')

    return render_template('edit-bucket.html', title='New Bucket')





@app.route('/buckets/refill')
def refill():
    pod_id = int(session['user']['group']['id'])
    pod = Pod.query.get(pod_id)

    next = pod.refill + timedelta(days=7) if pod.refill else None

    buckets = Bucket.query.filter_by(pod_id=pod_id).all()

    if not next or next < datetime.utcnow():
        if not next: next = datetime.utcnow()

        day   = next.weekday()
        shift = day - 4 if day > 3 else day + 3

        synced = next - timedelta(days=shift)
        synced = synced.replace(hour=18, minute=0, second=0, microsecond=0)

        pod.refill = synced

        for bucket in buckets:
            refill = bucket.refill if bucket.refill else 0
            bucket.balance = bucket.balance + refill

        db.session.commit()
        return redirect('/')

    else:
        left    = next - datetime.utcnow()
        hours   = left.seconds // 3600
        minutes = (left.seconds - (hours * 3600)) // 60
        return render_template('refill.html', title='Next Refill', days=left.days, hours=hours, minutes=minutes)





@app.route('/purchases', methods=['GET', 'POST'])
def purchases():
    if request.form:
        if 'tz-offset' in request.form:
            pod_id    = int(session['user']['group']['id'])
            purchases = Purchase.query.filter(Purchase.bucket.has(pod_id=pod_id)).order_by(Purchase.date.desc()).limit(100)
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

    buckets = Bucket.query.filter_by(pod_id=int(session['user']['group']['id'])).all()
    return render_template('transfer.html', buckets=buckets, title='Transfer')





if __name__ == '__main__':
    app.run()
