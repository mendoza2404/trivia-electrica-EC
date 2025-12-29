import streamlit as st
import json
import os
import time
import random
import string
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

ROOMS_FILE = "rooms.json"
STATS_FILE = "stats.json"
QUESTIONS_JSON = "questions.json"  # contiene el banco grande

# -------------------------
# Model
# -------------------------
@dataclass
class Question:
    category: str
    prompt: str
    options: Dict[str, str]
    answer: str

# -------------------------
# Persistence helpers
# -------------------------
def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# -------------------------
# Rooms
# -------------------------
def new_room_code(n=6):
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def ensure_room(room_code: str):
    rooms = _load_json(ROOMS_FILE, {})
    if room_code not in rooms:
        rooms[room_code] = {
            "created_at": int(time.time()),
            "seed": random.randint(1, 10**9),
            "players": {},          # name -> {"answers": {idx:"A"}, "done": bool}
            "locked": False,        # true cuando alguien termina primero
            "winner": None,         # nombre de quien terminó primero
            "ended_at": None,       # timestamp
            "result_saved": False,  # para ranking (una sola vez)
        }
        _save_json(ROOMS_FILE, rooms)

def get_room(room_code: str):
    rooms = _load_json(ROOMS_FILE, {})
    return rooms.get(room_code)

def upsert_room(room_code: str, room_data: dict):
    rooms = _load_json(ROOMS_FILE, {})
    rooms[room_code] = room_data
    _save_json(ROOMS_FILE, rooms)

# -------------------------
# Stats
# -------------------------
def update_stats(winner: str, loser: str, tie: bool = False):
    stats = _load_json(STATS_FILE, {})
    for name in {winner, loser}:
        if not name:
            continue
        stats.setdefault(name, {"wins": 0, "losses": 0, "ties": 0, "games": 0})

    if tie:
        stats[winner]["ties"] += 1
        stats[loser]["ties"] += 1
        stats[winner]["games"] += 1
        stats[loser]["games"] += 1
    else:
        stats[winner]["wins"] += 1
        stats[loser]["losses"] += 1
        stats[winner]["games"] += 1
        stats[loser]["games"] += 1

    _save_json(STATS_FILE, stats)

def leaderboard_rows():
    stats = _load_json(STATS_FILE, {})
    rows = []
    for name, s in stats.items():
        rows.append((name, s["wins"], s["losses"], s["ties"], s["games"]))
    rows.sort(key=lambda x: (x[1], -x[2], x[4]), reverse=True)
    return rows

# -------------------------
# Questions
# -------------------------
def normalize_question_dict(q: dict) -> Optional[Question]:
    try:
        category = str(q["category"]).strip()
        prompt = str(q["prompt"]).strip()
        options = q["options"]
        answer = str(q["answer"]).strip().upper()
        if not isinstance(options, dict):
            return None
        for k in ["A", "B", "C", "D"]:
            if k not in options:
                return None
        if answer not in ["A", "B", "C", "D"]:
            return None
        return Question(
            category=category,
            prompt=prompt,
            options={k: str(options[k]) for k in ["A", "B", "C", "D"]},
            answer=answer
        )
    except Exception:
        return None

def load_question_bank() -> List[Question]:
    raw = _load_json(QUESTIONS_JSON, [])
    bank = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                q = normalize_question_dict(item)
                if q:
                    bank.append(q)
    return bank

def pick_questions_for_room(bank: List[Question], seed: int, n_total: int = 10) -> List[Question]:
    # determinístico por sala, sin repetición
    rng = random.Random(seed)
    if len(bank) < n_total:
        return bank[:]
    idxs = rng.sample(range(len(bank)), n_total)
    return [bank[i] for i in idxs]

def compute_score(questions: List[Question], answers: Dict[str, str]) -> int:
    score = 0
    for i, q in enumerate(questions):
        a = (answers.get(str(i)) or "").strip().upper()
        if a == q.answer:
            score += 1
    return score

# -------------------------
# Fun: gender-ish teasing (heuristic + neutral fallback)
# -------------------------
def gender_guess(name: str) -> str:
    """
    Heurística simple:
    - termina en 'a' -> fem
    - termina en 'o' -> masc
    - nombres comunes -> m/f
    - fallback -> neutral
    """
    n = (name or "").strip().lower()
    first = re.split(r"\s+", n)[0] if n else ""
    female_names = {"elizabeth","andrea","maria","carla","paola","diana","laura","sofia","camila","ana","gabriela","valentina","lucia","isabel"}
    male_names = {"carlos","alberto","juan","jose","pedro","miguel","diego","javier","marco","luis","andres","ricardo","fernando","manuel"}
    if first in female_names:
        return "f"
    if first in male_names:
        return "m"
    if first.endswith("a"):
        return "f"
    if first.endswith("o"):
        return "m"
    return "n"

def taunt(winner: str, loser: str) -> str:
    g = gender_guess(loser)
    # Evitar insultos fuertes: solo picante/juguetón.
    if g == "f":
        variants = [
            f"🏆 {winner} ganó. {loser}, hoy te tocó modo *novata* 😄",
            f"⚡ Victoria de {winner}. {loser}, la próxima vienes con más voltaje 😉",
            f"😂 {winner} se lleva la corona. {loser}, hoy la electrónica te hizo ghosting."
        ]
    elif g == "m":
        variants = [
            f"🏆 {winner} ganó. {loser}, hoy quedaste como *burrito* oficial 😄",
            f"⚡ Victoria de {winner}. {loser}, te faltó amperaje para aguantar el ritmo 😉",
            f"😂 {winner} se la llevó. {loser}, hoy te dispararon las protecciones."
        ]
    else:
        variants = [
            f"🏆 {winner} ganó. {loser}, hoy tocó modo *burrit@* 😄",
            f"⚡ Victoria de {winner}. {loser}, la próxima con más potencia 😉",
            f"😂 {winner} se la llevó. {loser}, hoy te faltó chispa."
        ]
    return random.choice(variants)

# -------------------------
# UI
# -------------------------
st.set_page_config(page_title="Trivia técnica (2 jugadores) ⚡", page_icon="⚡", layout="centered")

# CSS for "answered" highlight
st.markdown("""
<style>
.answer-box {
  border: 1px solid rgba(0,0,0,0.1);
  padding: 14px 14px 6px 14px;
  border-radius: 14px;
  margin-bottom: 12px;
}
.answered {
  border: 2px solid #2e7d32 !important;
  background: rgba(46,125,50,0.08);
}
.locked {
  border: 2px solid #b71c1c !important;
  background: rgba(183,28,28,0.06);
}
.smallnote { font-size: 0.9rem; opacity: 0.8; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ Trivia técnica a distancia (2 jugadores)")
st.caption("Banco grande (600). 10 preguntas por partida. Respuestas ocultas hasta el final.")

with st.sidebar:
    st.subheader("🏆 Ranking burrit@ (histórico)")
    rows = leaderboard_rows()
    if rows:
        for i, (name, w, l, t, g) in enumerate(rows[:25], start=1):
            st.write(f"**{i}. {name}** — ✅ {w} | ❌ {l} | 🤝 {t} | 🎮 {g}")
        worst = sorted(rows, key=lambda x: (x[2], x[4]), reverse=True)[0]
        st.info(f"🐴 Burrit@ oficial (más derrotas): **{worst[0]}** (❌ {worst[2]})")
    else:
        st.write("Aún no hay partidas registradas.")

st.divider()

tab1, tab2 = st.tabs(["🎮 Jugar", "📌 WhatsApp"])

with tab1:
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Crear sala")
        if st.button("➕ Crear nueva sala"):
            room = new_room_code()
            ensure_room(room)
            st.session_state["room_code"] = room
            st.success(f"Sala creada: **{room}**")

    with colB:
        st.subheader("Unirse a sala")
        join_code = st.text_input("Room Code", value=st.session_state.get("room_code", ""), max_chars=10).strip().upper()
        if st.button("🔗 Cargar sala"):
            if not join_code:
                st.warning("Ingresa un Room Code.")
            else:
                ensure_room(join_code)
                st.session_state["room_code"] = join_code
                st.success(f"Listo. Sala: **{join_code}**")

    room_code = st.session_state.get("room_code")
    if not room_code:
        st.info("Crea una sala o únete a una usando el Room Code.")
        st.stop()

    room = get_room(room_code)
    if not room:
        st.error("No pude cargar la sala. Intenta recargar.")
        st.stop()

    st.subheader(f"🧩 Sala: {room_code}")
    st.write("Comparte este **Room Code** con tu rival por WhatsApp.")

    player_name = st.text_input("Tu nombre (el que quieras)", value=st.session_state.get("player_name", "")).strip()
    st.session_state["player_name"] = player_name
    if not player_name:
        st.warning("Escribe tu nombre para empezar.")
        st.stop()

    # Load bank
    bank = load_question_bank()
    if len(bank) < 100:
        st.error("No encuentro un banco grande. Asegúrate de tener `questions.json` en el repo.")
        st.stop()

    # Deterministic questions per room
    questions = pick_questions_for_room(bank, seed=room["seed"], n_total=10)

    # init player
    room["players"].setdefault(player_name, {"answers": {}, "done": False})
    upsert_room(room_code, room)

    # Reload
    room = get_room(room_code) or room
    my = room["players"].get(player_name) or {"answers": {}, "done": False}

    # If room locked by someone else, prevent answering
    locked = bool(room.get("locked", False))
    winner = room.get("winner")

    if locked and winner and winner != player_name:
        st.warning(f"⛔ Juego terminado: **{winner}** terminó primero y cerró la partida. Ya no puedes responder más.")
    elif my.get("done"):
        st.success("✅ Terminaste tus 10 preguntas. (Si el otro no terminó antes, la partida queda cerrada al completarlas).")
    else:
        st.info("🕵️ Modo competencia: **NO se muestran respuestas** hasta el final. Cada confirmación marca tu respuesta.")

        for idx, q in enumerate(questions):
            answered = str(idx) in (my.get("answers") or {})
            box_class = "answer-box answered" if answered else "answer-box"
            st.markdown(f'<div class="{box_class}">', unsafe_allow_html=True)

            st.markdown(f"### Pregunta {idx+1}/10 — _{q.category}_")
            st.write(q.prompt)

            labels = [f"{k}) {q.options[k]}" for k in ["A", "B", "C", "D"]]
            prev = (my["answers"].get(str(idx)) or "A").upper()
            default_index = ["A", "B", "C", "D"].index(prev) if prev in ["A", "B", "C", "D"] else 0

            choice_label = st.radio(
                "Elige una opción",
                labels,
                index=default_index,
                key=f"q_{idx}_{player_name}_{room_code}",
                horizontal=False,
                disabled=locked
            )
            chosen_key = choice_label.split(")")[0].strip().upper()

            # confirm
            btn_label = "✅ Confirmada" if answered else "✅ Confirmar respuesta"
            if st.button(btn_label, key=f"confirm_{idx}_{player_name}_{room_code}", disabled=locked):
                # reload state
                room = get_room(room_code) or room
                if room.get("locked", False):
                    st.rerun()

                room["players"].setdefault(player_name, {"answers": {}, "done": False})
                my = room["players"][player_name]
                my["answers"][str(idx)] = chosen_key

                # if completed 10 -> lock room immediately
                if len(my["answers"]) >= 10:
                    my["done"] = True
                    room["locked"] = True
                    room["winner"] = player_name
                    room["ended_at"] = int(time.time())

                room["players"][player_name] = my
                upsert_room(room_code, room)
                st.rerun()

            st.markdown('<div class="smallnote">Al confirmar, la tarjeta queda marcada en verde.</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # Status section (always visible)
    room = get_room(room_code) or room
    players = room.get("players", {})

    st.subheader("📣 Estado de la sala")
    for pname, pdata in players.items():
        status = "✅ listo" if pdata.get("done") else "⌛ jugando"
        score = compute_score(questions, pdata.get("answers", {}))
        st.write(f"- **{pname}** — {status} — Puntaje: **{score}/10**")

    # End-game logic: if locked OR at least one done triggers end
    if room.get("locked", False) and room.get("winner"):
        # Determine top two players: winner and whoever else joined (if any)
        win = room["winner"]
        others = [p for p in players.keys() if p != win]
        opp = others[0] if others else None

        win_answers = players.get(win, {}).get("answers", {})
        win_score = compute_score(questions, win_answers)

        if opp:
            opp_answers = players.get(opp, {}).get("answers", {})
            opp_score = compute_score(questions, opp_answers)
        else:
            opp_answers = {}
            opp_score = 0

        st.subheader("🏁 Resultado final")
        st.write(f"**{win}**: {win_score}/10  ✅ (terminó primero)")
        if opp:
            st.write(f"**{opp}**: {opp_score}/10")
        else:
            st.write("⚠️ Aún no hay oponente en la sala (invita a alguien para que el duelo tenga sentido 😄).")

        # Save ranking once (only if there is an opponent)
        if opp and not room.get("result_saved", False):
            if win_score > opp_score:
                update_stats(winner=win, loser=opp, tie=False)
                st.success(taunt(win, opp))
            elif opp_score > win_score:
                update_stats(winner=opp, loser=win, tie=False)
                st.success(taunt(opp, win))
            else:
                update_stats(winner=win, loser=opp, tie=True)
                st.info("🤝 Empate técnico: ambos pagan o van a desempate 😄")

            room["result_saved"] = True
            upsert_room(room_code, room)
            st.toast("✅ Ranking actualizado automáticamente", icon="🏆")

        # Corrections / review: show correct + both answers + correctness
        if opp:
            st.subheader("🧾 Correcciones (respuestas reveladas al finalizar)")
            for i, q in enumerate(questions):
                correct = q.answer
                a_w = (win_answers.get(str(i)) or "-").upper()
                a_o = (opp_answers.get(str(i)) or "-").upper()

                def mark(ans):
                    if ans == "-":
                        return "⏹️ sin responder"
                    return "✅ correcto" if ans == correct else "❌ incorrecto"

                st.markdown(f"**{i+1}. {q.prompt}**  \n_Categoría: {q.category}_")
                st.write(f"✅ Correcta: **{correct}) {q.options[correct]}**")
                st.write(f"👤 {win}: **{a_w}** — {mark(a_w)}")
                st.write(f"👤 {opp}: **{a_o}** — {mark(a_o)}")
                st.divider()

with tab2:
    st.subheader("📌 Mensaje WhatsApp (cópialo)")
    st.code(
        "Amor ❤️😄 te reto a la trivia ⚡\n"
        "Link: (pega aquí el link de Streamlit)\n"
        "Room Code: (te lo paso)\n"
        "Regla: 10 preguntas. El que pierde paga ☕🍕\n",
        language="text"
    )
    st.write("💡 Nota: el juego se cierra cuando alguien termina primero las 10 preguntas.")
