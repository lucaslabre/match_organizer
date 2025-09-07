import os
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import db, User, Tournament, Player, Match
from forms import LoginForm, RegisterForm, NewTournamentForm, EditMatchForm
from tournament_logic import generate_bracket_with_byes, propagate_winner_up
from bracket_image import render_bracket_image

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'tennis.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('my_tournaments'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('my_tournaments'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.lower().strip()).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                return redirect(url_for('my_tournaments'))
            flash('E-mail ou senha inválidos', 'danger')
        return render_template('login.html', form=form)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('my_tournaments'))
        form = RegisterForm()
        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data.lower().strip()).first():
                flash('E-mail já cadastrado.', 'warning')
                return redirect(url_for('register'))
            user = User(
                name=form.name.data.strip(),
                email=form.email.data.lower().strip(),
                password_hash=generate_password_hash(form.password.data)
            )
            db.session.add(user)
            db.session.commit()
            flash('Conta criada com sucesso! Faça o login.', 'success')
            return redirect(url_for('login'))
        return render_template('register.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/my-tournaments')
    @login_required
    def my_tournaments():
        tournaments = Tournament.query.filter_by(user_id=current_user.id).order_by(Tournament.created_at.desc()).all()
        return render_template('my_tournaments.html', tournaments=tournaments)

    @app.route('/new_tournament', methods=['GET', 'POST'])
    @login_required
    def new_tournament():
        form = NewTournamentForm()
        if form.validate_on_submit():
            name = form.name.data.strip()
            stage = form.stage.data.strip()
            size = int(form.size.data)

            # Coletar jogadores a partir de inputs HTML (não WTForms)
            input_players = []
            for i in range(size):
                raw = request.form.get(f'player_{i+1}', '').strip()
                if raw:
                    input_players.append(raw)

            # Completar com BYE
            while len(input_players) < size:
                input_players.append('BYE')

            # NOVO: ler início e intervalo
            start_dt = None
            if form.start_datetime.data:
                try:
                    # datetime-local envia "YYYY-MM-DDTHH:MM"
                    start_dt = datetime.fromisoformat(form.start_datetime.data)
                except Exception:
                    start_dt = None

            interval_minutes = form.interval_minutes.data if form.interval_minutes.data is not None else None
            if interval_minutes is not None and interval_minutes < 0:
                interval_minutes = 0

            # Criar o torneio
            t = Tournament(
                user_id=current_user.id,
                name=name,
                stage=stage,
                size=size,
                is_random=form.randomize.data
            )
            db.session.add(t)
            db.session.flush()

            # Criar players
            player_objs = []
            for p in input_players:
                player = Player(tournament_id=t.id, name=p)
                db.session.add(player)
                player_objs.append(player)
            db.session.flush()

            # Gerar chaveamento
            generate_bracket_with_byes(db, t, player_objs, randomize=form.randomize.data)

            # NOVO: definir horários da primeira rodada
            if start_dt:
                # obter 1ª rodada (round_number = 1) ordenada
                first_round_matches = Match.query.filter_by(tournament_id=t.id, round_number=1)\
                                                .order_by(Match.position_in_round.asc()).all()
                current_time = start_dt
                for idx, m in enumerate(first_round_matches):
                    # Definir date_time do match
                    m.date_time = current_time
                    db.session.add(m)
                    # Avançar o relógio
                    if interval_minutes and interval_minutes > 0:
                        current_time = current_time + timedelta(minutes=interval_minutes)

            db.session.commit()
            flash('Torneio criado com sucesso!', 'success')
            return redirect(url_for('tournament_detail', tournament_id=t.id))

        return render_template('new_tournament.html', form=form)
    
    @app.route('/tournament/<int:tournament_id>', methods=['GET', 'POST'])
    @login_required
    def tournament_detail(tournament_id):
        t = Tournament.query.filter_by(id=tournament_id, user_id=current_user.id).first_or_404()

        # Atualização inline de nomes de jogadores e horários
        if request.method == 'POST':
            # Atualizar nomes dos jogadores
            for p in t.players:
                new_name = request.form.get(f'player_{p.id}')
                if new_name is not None and new_name.strip():
                    p.name = new_name.strip()

            # Atualizar horários dos jogos (cada match tem date_time string)
            for m in t.matches:
                dt_str = request.form.get(f'match_dt_{m.id}')
                if dt_str is not None:
                    dt_str = dt_str.strip()
                    if dt_str:
                        try:
                            # formato: 2025-09-01T18:30 (input type="datetime-local")
                            m.date_time = datetime.fromisoformat(dt_str)
                        except Exception:
                            pass
                    else:
                        m.date_time = None

            db.session.commit()
            flash('Jogadores e horários atualizados!', 'success')
            return redirect(url_for('tournament_detail', tournament_id=t.id))

        # Organizar matches por round e posição
        rounds = {}
        for m in t.matches:
            rounds.setdefault(m.round_number, []).append(m)
        for r in rounds:
            rounds[r].sort(key=lambda x: x.position_in_round)

        return render_template('tournament_detail.html', tournament=t, rounds=rounds)

    @app.route('/match/<int:match_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_match(match_id):
        m = Match.query.get_or_404(match_id)
        t = m.tournament
        if t.user_id != current_user.id:
            flash('Não autorizado.', 'danger')
            return redirect(url_for('my_tournaments'))

        form = EditMatchForm()

        # Nomes dos slots (podem ser BYE)
        p1 = Player.query.get(m.player1_id) if m.player1_id else None
        p2 = Player.query.get(m.player2_id) if m.player2_id else None
        name1 = p1.name if p1 else (m.player1_placeholder or '')
        name2 = p2.name if p2 else (m.player2_placeholder or '')

        if form.validate_on_submit():
            # Validar formato de placar: ex "6-4 4-6 7-5"
            score = form.score.data.strip()
            if score:
                # Validação simples: sets "x-y" separados por espaço
                valid = True
                sets = score.split()
                for s in sets:
                    if '-' not in s:
                        valid = False
                        break
                    a, b = s.split('-', 1)
                    if not (a.isdigit() and b.isdigit()):
                        valid = False
                        break
                if not valid:
                    flash('Formato de placar inválido. Use algo como: 6-4 4-6 7-5', 'warning')
                    return render_template('edit_match.html', form=form, match=m, name1=name1, name2=name2, tournament=t)

                m.score = score

            # Vencedor escolhido
            winner_choice = form.winner.data
            if winner_choice == '1' and name1:
                m.winner_player_id = p1.id if p1 else None
                m.winner_name = name1
            elif winner_choice == '2' and name2:
                m.winner_player_id = p2.id if p2 else None
                m.winner_name = name2
            else:
                # limpar vencedor se não definido
                m.winner_player_id = None
                m.winner_name = None

            db.session.commit()

            # Propagar vencedor no chaveamento
            if m.winner_name:
                propagate_winner_up(db, m)

            db.session.commit()
            flash('Resultado atualizado!', 'success')
            return redirect(url_for('tournament_detail', tournament_id=t.id))

        # Pré-preenche o formulário
        if request.method == 'GET':
            form.score.data = m.score or ''
            if m.winner_name:
                if m.winner_player_id == (p1.id if p1 else None) or m.winner_name == name1:
                    form.winner.data = '1'
                elif m.winner_player_id == (p2.id if p2 else None) or m.winner_name == name2:
                    form.winner.data = '2'

        return render_template('edit_match.html', form=form, match=m, name1=name1, name2=name2, tournament=t)

    @app.route('/tournament/<int:tournament_id>/image')
    @login_required
    def tournament_image(tournament_id):
        t = Tournament.query.filter_by(id=tournament_id, user_id=current_user.id).first_or_404()
        img_path = os.path.join(BASE_DIR, f'tournament_{t.id}.png')
        render_bracket_image(t, img_path, width=1920, height=1080)  # 16:9 (Instagram landscape)
        return send_file(img_path, mimetype='image/png', as_attachment=True, download_name=f'{t.name}.png')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)