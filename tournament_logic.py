import random
from datetime import datetime
from models import Tournament, Player, Match, db

def pair_players_no_double_bye(players):
    """
    Recebe lista de Player (ou strings "BYE" via Player.name)
    Cria pares sem permitir BYE x BYE.
    Estratégia: se existirem vários BYEs, intercalar com jogadores válidos.
    """
    # Separar BYEs e jogadores
    byes = [p for p in players if p.name.upper() == 'BYE']
    real = [p for p in players if p.name.upper() != 'BYE']

    # Se randomizar, embaralhar real e byes de forma previsível a evitar BYE x BYE
    random.shuffle(real)
    random.shuffle(byes)

    pairs = []
    # Primeiro, parear cada BYE com um real, enquanto possível
    while byes and real:
        pairs.append((real.pop(), byes.pop()))
    # Se sobraram reais, parear entre si
    while len(real) >= 2:
        a = real.pop()
        b = real.pop()
        pairs.append((a, b))
    # Se sobrou 1 real e 1 bye, parear
    if real and byes:
        pairs.append((real.pop(), byes.pop()))
    # Se ainda sobraram BYEs, eles irão ganhar automaticamente uma rodada (mas não devemos criar BYE x BYE)
    # Estratégia: se sobrar BYE sozinho, criamos um "match" com slot vazio que será tratado como avanço automático no gerador.
    leftover = []
    while byes:
        leftover.append(byes.pop())
    if real:
        leftover.extend(real)
    return pairs, leftover

def generate_bracket_with_byes(db, tournament: Tournament, players, randomize=True):
    """
    Gera o chaveamento completo. Cria Matchs por rounds.
    Regras:
    - Sem BYE vs BYE.
    - Quem enfrenta BYE avança automaticamente.
    - Conecta matches com next_match_id e next_match_slot.
    """
    size = tournament.size
    if randomize:
        random.shuffle(players)

    # Primeira rodada: criar duelos
    # Usaremos uma abordagem simples: tentar evitar BYE x BYE via pair_players_no_double_bye
    pairs, leftover = pair_players_no_double_bye(players)

    # Se sobraram jogadores fora dos pares, eles avançam automaticamente (como se tivessem BYE)
    # Vamos considerar que leftover pode conter BYEs e/ou jogador real solto (em chaves não par)
    # Porém, sizes são potências de 2 (4, 8, 16), então leftovers só devem ocorrer quando muitos BYEs existem.
    round_number = 1
    matches = []
    position = 1

    # Criar matches da primeira rodada
    created = []
    for a, b in pairs:
        m = Match(
            tournament_id=tournament.id,
            round_number=round_number,
            position_in_round=position,
            player1_id=a.id if a.name.upper() != 'BYE' else None,
            player2_id=b.id if b.name.upper() != 'BYE' else None,
            player1_placeholder='BYE' if a.name.upper() == 'BYE' else None,
            player2_placeholder='BYE' if b.name.upper() == 'BYE' else None
        )
        db.session.add(m)
        db.session.flush()
        created.append(m)
        position += 1

    # Se leftover tiver algum jogador real, criamos matches "fantasma" para marcar avanço automático
    # Melhor: criar um match em que o outro slot é BYE
    for p in leftover:
        m = Match(
            tournament_id=tournament.id,
            round_number=round_number,
            position_in_round=position,
            player1_id=p.id if p.name.upper() != 'BYE' else None,
            player1_placeholder='BYE' if p.name.upper() == 'BYE' else None,
            player2_id=None,
            player2_placeholder='BYE'
        )
        db.session.add(m)
        db.session.flush()
        created.append(m)
        position += 1

    # Agora, conectamos rounds seguintes
    current_round_matches = created
    total_rounds = {
        4: 2,   # semi + final
        8: 3,   # quartas + semi + final
        16: 4,  # oitavas + quartas + semi + final
    }[size]

    for r in range(2, total_rounds + 1):
        next_round = []
        position = 1
        for i in range(0, len(current_round_matches), 2):
            m_parent1 = current_round_matches[i]
            m_parent2 = current_round_matches[i+1] if i+1 < len(current_round_matches) else None
            child = Match(
                tournament_id=tournament.id,
                round_number=r,
                position_in_round=position
            )
            db.session.add(child)
            db.session.flush()
            # Link dos pais
            m_parent1.next_match_id = child.id
            m_parent1.next_match_slot = 1
            db.session.add(m_parent1)

            if m_parent2:
                m_parent2.next_match_id = child.id
                m_parent2.next_match_slot = 2
                db.session.add(m_parent2)
            else:
                # Se não há m_parent2, o slot 2 fica aguardando
                pass

            next_round.append(child)
            position += 1
        current_round_matches = next_round

    db.session.flush()

    # Propagar automaticamente vencedores de BYE imediatamente
    all_matches = Match.query.filter_by(tournament_id=tournament.id).all()
    for m in all_matches:
        # Caso jogador contra BYE
        p1_is_bye = (m.player1_id is None and (m.player1_placeholder or '').upper() == 'BYE')
        p2_is_bye = (m.player2_id is None and (m.player2_placeholder or '').upper() == 'BYE')
        if p1_is_bye and not p2_is_bye and m.player2_id:
            m.winner_player_id = m.player2_id
            m.winner_name = None
        elif p2_is_bye and not p1_is_bye and m.player1_id:
            m.winner_player_id = m.player1_id
            m.winner_name = None
        # BYE x BYE não deve existir; se ocorrer, ignore.
        if m.winner_player_id or m.winner_name:
            db.session.add(m)
            db.session.flush()
            propagate_winner_up(db, m)

    return all_matches

def propagate_winner_up(db, match: Match):
    """
    Recebe um match com winner definido. Move o vencedor para o próximo match no slot adequado.
    """
    if not match.next_match_id or not (match.winner_player_id or match.winner_name):
        return

    next_m = Match.query.get(match.next_match_id)
    if not next_m:
        return

    # Obter nome do vencedor
    winner_name = match.winner_name
    winner_player_id = match.winner_player_id

    # Preenche slot
    if match.next_match_slot == 1:
        if winner_player_id:
            next_m.player1_id = winner_player_id
            next_m.player1_placeholder = None
        else:
            next_m.player1_id = None
            next_m.player1_placeholder = winner_name or 'Vencedor'
    elif match.next_match_slot == 2:
        if winner_player_id:
            next_m.player2_id = winner_player_id
            next_m.player2_placeholder = None
        else:
            next_m.player2_id = None
            next_m.player2_placeholder = winner_name or 'Vencedor'

    db.session.add(next_m)
    db.session.flush()