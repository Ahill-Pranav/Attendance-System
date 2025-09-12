from models import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10))  # "faculty" or "student"
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # hashed
    name = db.Column(db.String(100), nullable=False)
    roll_no = db.Column(db.String(20), nullable=True)  # only for students
