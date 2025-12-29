import streamlit as st
import json
import os
import time
import random
import string
from dataclasses import dataclass
from typing import Dict, List, Optional

ROOMS_FILE = "rooms.json"
STATS_FILE = "stats.json"
QUESTIONS_JSON = "questions.json"  # tu banco grande (600+)

GAME_TOTAL_SECONDS = 300   # 5 minutos
QUESTION_SECONDS = 30      # 30s por pregunta
N_QUESTIONS = 10

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
            "started_at": None,     # cuando entra el primer jugador
            "locked": False,        # se bloquea al terminar el tiempo o por cierre
            "ended_reason": None,   # "time" o "manual"
            "players": {},          # name -> {"answers":{}, "done":bool, "idx":int, "q_started_at":int}
            "result_saved": False
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

def pick_questions_for_room(bank: List[Question], seed: int, n_total: int = N_QUESTIONS) -> List[Question]:
    rng = random.Random(seed)
    if len(bank) < n_total:
        return bank[:]
    idxs = rng.sample(range(len(bank)), n_total)  # sin repetición
    return [bank[i] for i in idxs]

def compute_score(questions: List[Question], answers: Dict[str, str]) -> int:
    score = 0
    for i, q in enumerate(questions):
        a = (answers.get(str(i)) or "").strip().upper()
        if a == q.answer:
            score += 1
    return score

# -------------------------
# UI helpers
# -------------------------
def fmt_mmss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"

st.set_page_config(page_title="Trivia técnica (2 jugadores) ⚡", page_icon="⚡", layout="centered")

# CSS: tarjeta marcada cuando ya respondió
st.markdown("""
<style>
.box { border: 1px solid rgba(0,0,0,0.12); padding: 14px 14px 6px 14px; border-radius: 16px; margin: 10px 0 14px 0; }
.answered { border: 2px solid #2e7d32 !important; background: rgba(46,125,50,0.10); }
.locked { border: 2px solid #b71c1c !important; background: rgba(183,28,28,0.06); }
.timer { font-size: 1.05rem; font-weight: 700; }
.small { font-size: 0.9rem; opacity: 0.85; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ Trivia a distancia (2 jugadores)")
st.caption("10 preguntas por partida. 30s por pregunta. 5 minutos total. Sin confirmar: solo selecciona.")

# Sidebar ranking
with st.sidebar:
    st.subheader("🏆 Ranking (histórico)")
    rows = leaderboard_rows()
    if rows:
        for i, (name, w, l, t, g) in enumerate(rows[:25], start=1):
            st.write(f"**{i}. {name}** — ✅ {w} | ❌ {l} | 🤝 {t} | 🎮 {g}")
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

    # Si es primer jugador, inicia el reloj global
    now = int(time.time())
    if room.get("started_at") is None:
        room["started_at"] = now
        upsert_room(room_code, room)
        room = get_room(room_code)

    # Cargar banco grande
    bank = load_question_bank()
    if len(bank) < 100:
        st.error("No encuentro un banco grande. Sube `questions.json` al repo (mínimo 100).")
        st.stop()

    questions = pick_questions_for_room(bank, seed=room["seed"], n_total=N_QUESTIONS)

    # Inicializar jugador
    room["players"].setdefault(player_name, {"answers": {}, "done": False, "idx": 0, "q_started_at": now})
    upsert_room(room_code, room)
    room = get_room(room_code)

    # Auto-refresh para timers
    st.autorefresh(interval=1000, key=f"tick_{room_code}")

    started_at = int(room.get("started_at") or now)
    elapsed = now - started_at
    remaining_total = GAME_TOTAL_SECONDS - elapsed

    # Bloqueo por tiempo global
    if remaining_total <= 0 and not room.get("locked", False):
        room["locked"] = True
        room["ended_reason"] = "time"
        upsert_room(room_code, room)
        room = get_room(room_code)

    locked = bool(room.get("locked", False))
    my = room["players"].get(player_name)

    # Banner timers
    st.markdown(f"<div class='timer'>⏱️ Tiempo total restante: {fmt_mmss(remaining_total)}</div>", unsafe_allow_html=True)

    # Si está bloqueado, no deja responder
    if locked:
        reason = room.get("ended_reason")
        if reason == "time":
            st.warning("⛔ Tiempo terminado (5 minutos). Nadie puede responder más.")
        else:
            st.warning("⛔ Juego finalizado.")

    # ---- Lógica por pregunta (secuencial) ----
    # Si no bloqueado y no terminó, controla timeout 30s
    if not locked and not my.get("done", False):
        idx = int(my.get("idx", 0))
        idx = max(0, min(idx, N_QUESTIONS - 1))

        q_started_at = int(my.get("q_started_at") or now)
        q_elapsed = now - q_started_at
        q_remaining = QUESTION_SECONDS - q_elapsed

        # Si se acabó el tiempo de la pregunta, avanza sin respuesta
        if q_remaining <= 0:
            # avanzar a siguiente pregunta
            if idx < N_QUESTIONS - 1:
                my["idx"] = idx + 1
                my["q_started_at"] = now
            else:
                # llegó a la última y se acabó el tiempo: marca fin
                my["done"] = True
            room["players"][player_name] = my
            upsert_room(room_code, room)
            st.rerun()

        st.markdown(f"<div class='timer'>⏳ Tiempo de esta pregunta: {fmt_mmss(q_remaining)}</div>", unsafe_allow_html=True)

        q = questions[idx]
        answered = str(idx) in (my.get("answers") or {})
        box_class = "box answered" if answered else "box"
        st.markdown(f"<div class='{box_class}'>", unsafe_allow_html=True)
        st.markdown(f"### Pregunta {idx+1}/{N_QUESTIONS} — _{q.category}_")
        st.write(q.prompt)

        labels = [f"{k}) {q.options[k]}" for k in ["A", "B", "C", "D"]]

        # radio sin selección por default
        key = f"sel_{room_code}_{player_name}_{idx}"
        choice = st.radio("Selecciona una opción", labels, index=None, key=key)

        # Si selecciona, se guarda inmediatamente y avanza a la siguiente
        if choice is not None:
            chosen_key = choice.split(")")[0].strip().upper()
            my["answers"][str(idx)] = chosen_key

            if idx < N_QUESTIONS - 1:
                my["idx"] = idx + 1
                my["q_started_at"] = now
            else:
                # última pregunta: NO auto-termina, debe presionar botón
                pass

            room["players"][player_name] = my
            upsert_room(room_code, room)
            st.rerun()

        st.markdown("<div class='small'>✅ Se guarda al seleccionar. No existe botón Confirmar.</div>", unsafe_allow_html=True)

        # Botón solo en la última pregunta
        if idx == N_QUESTIONS - 1:
            st.markdown("---")
            if st.button("🏁 Terminé el juego"):
                my["done"] = True
                room["players"][player_name] = my
                upsert_room(room_code, room)
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Estado de sala ----
    st.subheader("📣 Estado de la sala")
    players = room.get("players", {})
    for pname, pdata in players.items():
        status = "✅ terminó" if pdata.get("done") else f"⌛ en pregunta {int(pdata.get('idx',0))+1}"
        score = compute_score(questions, pdata.get("answers", {}))
        st.write(f"- **{pname}** — {status} — Puntaje: **{score}/{N_QUESTIONS}**")

    # ---- Final: si el tiempo terminó O ambos terminaron, mostrar correcciones ----
    done_players = [p for p, d in players.items() if d.get("done")]
    show_final = locked or (len(done_players) >= 2)

    if show_final:
        # tomar hasta 2 jugadores
        pnames = list(players.keys())[:2]
        if len(pnames) < 2:
            st.info("Aún falta el segundo jugador para mostrar comparativa completa.")
        else:
            p1, p2 = pnames[0], pnames[1]
            a1 = players[p1].get("answers", {})
            a2 = players[p2].get("answers", {})

            s1 = compute_score(questions, a1)
            s2 = compute_score(questions, a2)

            st.subheader("🏁 Resultado final")
            st.write(f"**{p1}**: {s1}/{N_QUESTIONS}")
            st.write(f"**{p2}**: {s2}/{N_QUESTIONS}")

            # guardar ranking 1 sola vez
            if not room.get("result_saved", False):
                if s1 > s2:
                    update_stats(winner=p1, loser=p2, tie=False)
                    st.success(f"🏆 Ganador: **{p1}** — 💸 **{p2}** paga la apuesta 😄")
                elif s2 > s1:
                    update_stats(winner=p2, loser=p1, tie=False)
                    st.success(f"🏆 Ganador: **{p2}** — 💸 **{p1}** paga la apuesta 😄")
                else:
                    update_stats(winner=p1, loser=p2, tie=True)
                    st.info("🤝 Empate — ambos pagan o hacen desempate 😄")

                room["result_saved"] = True
                upsert_room(room_code, room)
                st.toast("✅ Ranking actualizado", icon="🏆")

            # Correcciones: correcta + lo que puso cada uno + correcto/incorrecto
            st.subheader("🧾 Correcciones (respuestas reveladas al final)")
            for i, q in enumerate(questions):
                correct = q.answer
                p1_ans = (a1.get(str(i)) or "-").upper()
                p2_ans = (a2.get(str(i)) or "-").upper()

                def mark(ans):
                    if ans == "-":
                        return "⏹️ sin responder"
                    return "✅ correcto" if ans == correct else "❌ incorrecto"

                st.markdown(f"**{i+1}. {q.prompt}**  \n_Categoría: {q.category}_")
                st.write(f"✅ Correcta: **{correct}) {q.options[correct]}**")
                st.write(f"👤 {p1}: **{p1_ans}** — {mark(p1_ans)}")
                st.write(f"👤 {p2}: **{p2_ans}** — {mark(p2_ans)}")
                st.divider()

with tab2:
    st.subheader("📌 Mensaje WhatsApp")
    st.code(
        "Amor 😄⚡ te reto a la trivia\n"
        "Link: (pega aquí el link)\n"
        "Room Code: (te lo paso)\n"
        "Reglas: 10 preguntas, 30s cada una, 5 min total.\n",
        language="text"
    )
