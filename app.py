from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.debug = True

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/www/html/buckets/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)





class Bucket(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(100))
	balance = db.Column(db.Float)
	size = db.Column(db.Integer)











@app.route('/')
def home():
	envelopes = [
		{'name': 'Groceries',     'amount': 30},
		{'name': 'Restaurants',   'amount': 0},
		{'name': 'Fun Stuff',     'amount': 20},
		{'name': 'Boring Things', 'amount': 10},
		{'name': 'Reyn',          'amount': 50},
		{'name': 'Bryan',         'amount': 75},
		{'name': 'Adventures',    'amount': 90},
		{'name': 'Apartment',     'amount': 100},
	]
	envelopes = Bucket.query.all()
	return render_template('home.html', envelopes=envelopes, title='Buckets')






@app.route('/buckets/<int:id>', methods=['GET', 'POST'])
def bucket(id):
	bucket = Bucket.query.get(id)
	if 'submit' in request.form:
		amount = request.form['amount']
		if amount != '':
			bucket.balance = bucket.balance - float(amount)
			db.session.commit()
			return redirect('/')
	return render_template('bucket.html', bucket=bucket, title=bucket.name)




@app.route('/buckets/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
	bucket = Bucket.query.get(id)
	if 'submit' in request.form:
		name = request.form['name']
		size = int(request.form['size'])
		bucket.name = name
		bucket.size = size
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
		size = int(request.form['size'])
		bucket = Bucket(name=name, balance=50, size=size)
		db.session.add(bucket)
		db.session.commit()
		return redirect('/')
	return render_template('edit-bucket.html', title='New Bucket')



if __name__ == '__main__':
	app.run()

