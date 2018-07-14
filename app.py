from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


app = Flask(__name__)
app.debug = True

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/www/buckets/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)





class Bucket(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(50))
	balance = db.Column(db.Float)
	refill = db.Column(db.Integer)
	size = db.Column(db.Integer)


class Purchase(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	desc = db.Column(db.String(150))
	amount = db.Column(db.Float)
	date = db.Column(db.DateTime)









@app.route('/')
def home():
	envelopes = Bucket.query.all()
	return render_template('home.html', envelopes=envelopes, title='Buckets')






@app.route('/buckets/<int:id>', methods=['GET', 'POST'])
def bucket(id):
	bucket = Bucket.query.get(id)
	if 'submit' in request.form:
		amount = request.form['amount']
		desc = request.form['desc']
		if amount != '':
			amount = float(amount)
			bucket.balance = bucket.balance - amount

			purchase = Purchase(desc=desc, amount=amount, date=datetime.now())
			db.session.add(purchase)
			db.session.commit()
			return redirect('/')
	return render_template('bucket.html', bucket=bucket, title=bucket.name)




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
    for bucket in Bucket.query.all():
        refill = bucket.refill if bucket.refill else 0
        bucket.balance = bucket.balance + refill
    db.session.commit()
    return redirect('/')




@app.route('/purchases')
def purchases():
	purchases = Purchase.query.all()
	return render_template('purchases.html', purchases=purchases, title='Purchases')



if __name__ == '__main__':
	app.run()

