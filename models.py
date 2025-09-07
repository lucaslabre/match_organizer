from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    tournaments = db.relationship('Tournament', backref='user', lazy=True)

class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    stage = db.Column(db.String(200), nullable=True)
    size = db.Column(db.Integer, nullable=False)  # 4, 8, 16
    is_random = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    players = db.relationship('Player', backref='tournament', cascade='all, delete-orphan', lazy=True)
    matches = db.relationship('Match', backref='tournament', cascade='all, delete-orphan', lazy=True)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)  # 1 = Quartas/Primeira fase, etc
    position_in_round = db.Column(db.Integer, nullable=False)  # index do duelo nesse round
    player1_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)
    player2_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)
    player1_placeholder = db.Column(db.String(120), nullable=True)  # ex: "BYE" ou "Vencedor M3"
    player2_placeholder = db.Column(db.String(120), nullable=True)
    winner_player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)
    winner_name = db.Column(db.String(120), nullable=True)
    score = db.Column(db.String(120), nullable=True)  # "6-4 4-6 7-5"
    date_time = db.Column(db.DateTime, nullable=True)

    next_match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=True)
    next_match_slot = db.Column(db.Integer, nullable=True)  # 1 ou 2

    # referência reversa manual (não ORM) para next_match é resolvida via query