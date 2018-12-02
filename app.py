from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone


app = Flask(__name__)
app.debug = True

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/www/buckets/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)





class Bucket(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(50))
	balance = db.Column(db.Integer)
	refill = db.Column(db.Integer)
	last_refill = db.Column(db.DateTime)
	size = db.Column(db.Integer)
	purchases = db.relationship('Purchase', backref='bucket')


class Purchase(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	bucket_id = db.Column(db.Integer, db.ForeignKey('bucket.id'))
	desc = db.Column(db.String(150))
	amount = db.Column(db.Integer)
	date = db.Column(db.DateTime)






@app.route('/')
def home():
    results = Bucket.query.all()
    buckets = []

    for bucket in results:
        buckets.append({
            'id':      bucket.id,
            'name':    bucket.name,
            'balance': bucket.balance,
            'refill':  bucket.refill,
            'size':    bucket.size,
            'outlook': bucket.balance + bucket.refill,
            'width':   int((bucket.balance / bucket.size) * 100) if bucket.balance > 0 else 0
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
			if time == 'now':
				timestamp = False
			else:
				timestamp = datetime.strptime(day + '_' + time, '%Y-%m-%d_%H:%M') + timedelta(minutes=offset)

		if timestamp:
			bucket.balance = bucket.balance - amount
			
			purchase  = Purchase(desc=desc, amount=amount, bucket=bucket, date=timestamp)
			
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
		name = request.form['name']
		size = request.form['size']
		size = int(size) if size != '' else 100
		
		refill = request.form['refill']
		refill = int(refill) if refill != '' else 0

		bucket.name = name
		bucket.size = size
		bucket.refill = refill
		db.session.commit()
		return redirect('/buckets/' + str(bucket.id))
	return render_template('edit-bucket.html', bucket=bucket, title='Edit Bucket')



@app.route('/buckets/<int:id>/delete')
def delete(id):
	bucket = Bucket.query.get(id)
	db.session.delete(bucket)
	db.session.commit()
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

		bucket = Bucket(name=name, balance=refill, refill=refill, size=size)
		db.session.add(bucket)
		db.session.commit()
		return redirect('/')
	return render_template('edit-bucket.html', title='New Bucket')



@app.route('/buckets/refill')
def refill():
    buckets = Bucket.query.all()
    
    last = None
    for bucket in buckets:
        last_refill = bucket.last_refill if bucket.last_refill else datetime.utcnow() - timedelta(days=30)

        if last: 
            if last_refill > last: last = last_refill
        else:
            last = last_refill

    next_refill = last + timedelta(days=7)

    if not last or next_refill < datetime.today():		
        refill_date = next_refill if last else datetime.today()

        day   = refill_date.weekday()
        shift = day - 4 if day >= 4 else day + 3

        refill_date = refill_date - timedelta(days=shift)
        refill_date = refill_date.replace(hour=18, minute=0, second=0, microsecond=0)

        for bucket in buckets:
            refill = bucket.refill if bucket.refill else 0
            bucket.balance = bucket.balance + refill
            bucket.last_refill = refill_date

        db.session.commit()
        return redirect('/')

    else:
        return render_template('refill.html', title='Next Refill', next=next_refill)





@app.route('/purchases', methods=['GET', 'POST'])
def purchases():
	if request.form:
		if 'tz-offset' in request.form:
			purchases = Purchase.query.order_by(Purchase.date.desc()).limit(100)
			offset    = int(round(float(request.form['tz-offset']) / 60, 0)) * -1
		
			for purchase in purchases:
				purchase.date = purchase.date + timedelta(hours=offset)
		
			return render_template('purchases.html', purchases=purchases, title='Purchases')
		else:
			return redirect('/')
	else:
		return render_template('timezone.html', url='/purchases')



@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
	if 'submit' in request.form:
		from_bucket = Bucket.query.get(int(request.form['from']))
		to_bucket   = Bucket.query.get(int(request.form['to']))
		amount      = int(request.form['amount'])

		from_bucket.balance = from_bucket.balance - amount
		to_bucket.balance = to_bucket.balance + amount
		db.session.commit()
		return redirect('/')
	buckets = Bucket.query.all()
	return render_template('transfer.html', buckets=buckets, title='Transfer')



if __name__ == '__main__':
	app.run()

