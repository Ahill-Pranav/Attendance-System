from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db():
    from app import app
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///attendance.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
