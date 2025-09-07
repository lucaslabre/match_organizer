from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

# Fonte padrão do sistema; opcionalmente, troque por um .ttf local
def try_font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()

def get_match_label(m, players_by_id):
    def name_for(pid, placeholder):
        if pid:
            return players_by_id.get(pid, 'Desconhecido')
        return placeholder or ''
    p1 = name_for(m.player1_id, m.player1_placeholder)
    p2 = name_for(m.player2_id, m.player2_placeholder)
    dt = m.date_time.strftime('%d/%m %H:%M') if m.date_time else ''
    score = m.score or ''
    return p1, p2, dt, score

def layout_bracket(rounds_sorted, width, height, left_margin=80, right_margin=80, top_margin=160, bottom_margin=60):
    total_rounds = max(rounds_sorted.keys()) if rounds_sorted else 1
    col_width = (width - left_margin - right_margin) // max(1, total_rounds)
    box_width = int(col_width * 0.80)
    box_height = 90
    min_v_spacing = 22

    round_x = {r: left_margin + (r - 1) * col_width for r in range(1, total_rounds + 1)}
    positions = {}

    # Round 1: distribuir uniformemente
    r1 = 1
    if r1 in rounds_sorted:
        matches_r1 = rounds_sorted[r1]
        count = max(1, len(matches_r1))
        avail_height = height - top_margin - bottom_margin
        step = max(box_height + min_v_spacing, avail_height // count)
        y = top_margin + max(0, (avail_height - step * count) // 2)
        x = round_x[r1]
        for m in matches_r1:
            positions[m.id] = {'x': x, 'y': y, 'w': box_width, 'h': box_height}
            y += step

    # Rounds seguintes: centralizar entre pares do round anterior
    for r in range(2, total_rounds + 1):
        if r not in rounds_sorted:
            continue
        prev_round = r - 1
        prev_matches = rounds_sorted.get(prev_round, [])
        curr_matches = rounds_sorted[r]
        x = round_x[r]

        prev_centers = []
        for pm in prev_matches:
            pos = positions.get(pm.id)
            prev_centers.append(None if not pos else (pos['y'] + pos['h'] / 2))

        for i, m in enumerate(curr_matches):
            idx_a = 2 * i
            idx_b = 2 * i + 1
            if (idx_a < len(prev_centers) and idx_b < len(prev_centers)
                and prev_centers[idx_a] is not None and prev_centers[idx_b] is not None):
                target_center = (prev_centers[idx_a] + prev_centers[idx_b]) / 2.0
                y = target_center - box_height / 2.0
            else:
                if i == 0:
                    first_valid = next((c for c in prev_centers if c is not None), top_margin + i*(box_height+min_v_spacing))
                    y = first_valid - box_height/2
                else:
                    prev_m = curr_matches[i-1]
                    prev_pos = positions.get(prev_m.id)
                    y = (prev_pos['y'] + prev_pos['h'] + min_v_spacing) if prev_pos else (top_margin + i * (box_height + min_v_spacing))

            positions[m.id] = {'x': x, 'y': y, 'w': box_width, 'h': box_height}

    # Anchors para conectores
    for r, matches in rounds_sorted.items():
        for m in matches:
            pos = positions[m.id]
            x = pos['x']; y = pos['y']; w = pos['w']; h = pos['h']
            pos['anchors'] = {
                'src_center': (x + w, y + h / 2),
                'dst_slot1': (x, y + h * 0.30),
                'dst_slot2': (x, y + h * 0.70),
            }

    return positions, col_width, box_width, box_height

def render_bracket_image(tournament, out_path, width=1920, height=1080):
    players_by_id = {p.id: p.name for p in tournament.players}
    rounds = {}
    for m in tournament.matches:
        rounds.setdefault(m.round_number, []).append(m)

    rounds_sorted = {r: sorted(ms, key=lambda x: x.position_in_round) for r, ms in rounds.items()}
    if not rounds_sorted:
        img = Image.new('RGB', (width, height), (245, 245, 245))
        draw = ImageDraw.Draw(img)
        title_font = try_font(52)
        subtitle_font = try_font(28)
        draw.text((40, 30), tournament.name, fill=(20,20,20), font=title_font)
        if tournament.stage:
            draw.text((40, 100), f"Etapa: {tournament.stage}", fill=(60,60,60), font=subtitle_font)
        img.save(out_path, 'PNG')
        return

    img = Image.new('RGB', (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    title_font = try_font(52)
    subtitle_font = try_font(28)
    match_font = try_font(22)
    small_font = try_font(18)

    # Título
    draw.text((40, 30), tournament.name, fill=(20,20,20), font=title_font)
    if tournament.stage:
        draw.text((40, 100), f"Etapa: {tournament.stage}", fill=(60,60,60), font=subtitle_font)

    # Layout centralizado
    positions, col_width, box_width, box_height = layout_bracket(
        rounds_sorted, width, height, left_margin=80, right_margin=80, top_margin=190, bottom_margin=60
    )

    # Conectores
    for r, matches in rounds_sorted.items():
        for m in matches:
            if m.next_match_id:
                src = positions.get(m.id, {}).get('anchors', {}).get('src_center')
                child_pos = positions.get(m.next_match_id)
                if src and child_pos:
                    dst = child_pos['anchors']['dst_slot1'] if m.next_match_slot == 1 else child_pos['anchors']['dst_slot2']
                    mid_x = (src[0] + dst[0]) / 2
                    draw.line([(src[0], src[1]), (mid_x, src[1])], fill=(160,160,160), width=2)
                    draw.line([(mid_x, min(src[1], dst[1])), (mid_x, max(src[1], dst[1]))], fill=(160,160,160), width=2)
                    draw.line([(mid_x, dst[1]), (dst[0], dst[1])], fill=(160,160,160), width=2)

    # Cores
    COLOR_TEXT = (0, 0, 0)
    COLOR_WIN = (16, 122, 72)     # verde
    COLOR_LOSE = (192, 28, 28)    # vermelho
    COLOR_BYE = (120, 120, 120)   # cinza
    COLOR_META = (80, 80, 80)
    COLOR_SCORE = (0, 120, 0)

    # Desenhar boxes e nomes com cores conforme vencedor/perdedor
    for r in sorted(rounds_sorted.keys()):
        matches = rounds_sorted[r]
        # Label da rodada
        col_x = positions[matches[0].id]['x'] if matches else 80 + (r-1)*col_width
        draw.text((col_x, 150), f"Rodada {r}", fill=(30,30,120), font=subtitle_font)

        for m in matches:
            pos = positions[m.id]
            x, y, w, h = pos['x'], pos['y'], pos['w'], pos['h']
            # Caixa
            draw.rounded_rectangle([x, y, x+w, y+h], radius=10, fill=(255,255,255), outline=(200,200,200), width=2)

            # Labels e cores
            p1, p2, dt, score = get_match_label(m, players_by_id)

            # Determinar vencedor/perdedor
            winner_name = None
            winner_id = None
            if m.winner_player_id:
                winner_id = m.winner_player_id
                winner_name = players_by_id.get(winner_id, None)
            elif m.winner_name:
                winner_name = m.winner_name

            # Flags BYE
            p1_is_bye = (not m.player1_id) and (p1.upper() == 'BYE')
            p2_is_bye = (not m.player2_id) and (p2.upper() == 'BYE')

            # Cores default
            c1 = COLOR_TEXT
            c2 = COLOR_TEXT

            if winner_name or winner_id:
                # Comparar por id quando possível; caso contrário por nome
                p1_is_winner = (winner_id is not None and m.player1_id == winner_id) or (winner_id is None and winner_name and p1 and p1 == winner_name)
                p2_is_winner = (winner_id is not None and m.player2_id == winner_id) or (winner_id is None and winner_name and p2 and p2 == winner_name)

                if p1_is_winner:
                    c1 = COLOR_WIN
                    c2 = COLOR_LOSE if not p2_is_bye else COLOR_BYE
                elif p2_is_winner:
                    c2 = COLOR_WIN
                    c1 = COLOR_LOSE if not p1_is_bye else COLOR_BYE
                else:
                    # Caso raro: vencedor não bate com nenhum (nomes alterados), mantenha neutro
                    c1 = COLOR_TEXT if not p1_is_bye else COLOR_BYE
                    c2 = COLOR_TEXT if not p2_is_bye else COLOR_BYE
            else:
                # Sem vencedor ainda
                if p1_is_bye: c1 = COLOR_BYE
                if p2_is_bye: c2 = COLOR_BYE

            # Desenhar nomes
            draw.text((x+10, y+10), p1 or '—', fill=c1, font=match_font)
            draw.text((x+10, y+46), p2 or '—', fill=c2, font=match_font)

            # Metadados (direita do box)
            if dt:
                draw.text((x+w-180, y+10), dt, fill=COLOR_META, font=small_font)
            if score:
                draw.text((x+w-180, y+46), score, fill=COLOR_SCORE, font=small_font)

    # Rodapé
    ts = datetime.now().strftime('%d/%m/%Y %H:%M')
    draw.text((width-340, height-40), f"Geração: {ts}", fill=(120,120,120), font=small_font)

    img.save(out_path, 'PNG')