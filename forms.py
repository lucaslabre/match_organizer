from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange

class LoginForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')

class RegisterForm(FlaskForm):
    name = StringField('Nome', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Criar conta')

class NewTournamentForm(FlaskForm):
    name = StringField('Nome do Torneio', validators=[DataRequired(), Length(max=200)])
    stage = StringField('Etapa', validators=[Optional(), Length(max=200)])
    size = SelectField('Quantidade de Jogadores', choices=[('4', '4'), ('8', '8'), ('16', '16')], validators=[DataRequired()])
    start_datetime = StringField('Início do Torneio (data e hora)', validators=[Optional()])  # receberá ISO de datetime-local
    interval_minutes = IntegerField('Intervalo entre jogos (min)', validators=[Optional(), NumberRange(min=0, max=1440)])
    randomize = BooleanField('Gerar jogos aleatoriamente?')
    submit = SubmitField('Gerar Torneio')

    # Campos dinâmicos de jogadores serão adicionados no template via loop

class EditMatchForm(FlaskForm):
    score = StringField('Resultado (ex: 6-4 4-6 7-5)', validators=[Optional(), Length(max=120)])
    winner = SelectField('Vencedor', choices=[('','Selecione'), ('1', 'Jogador 1'), ('2', 'Jogador 2')], validators=[Optional()])
    submit = SubmitField('Salvar')