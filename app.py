import streamlit as st
import json
import os
import time
import random
import string
from dataclasses import dataclass, asdict
from typing import Dict, List

ROOMS_FILE = "rooms.json"
STATS_FILE = "stats.json"

# ---------- Data model ----------
@dataclass
class Question:
    category: str
    prompt: str
    options: Dict[str, str]
    answer: str

QUESTION_BANK: List[Question] = [
    # ELÉCTRICA
    Question("Eléctrica", "¿Unidad de la resistencia eléctrica?", {"A":"Ohm (Ω)","B":"Volt (V)","C":"Ampere (A)","D":"Watt (W)"}, "A"),
    Question("Eléctrica", "En AC senoidal, la potencia activa se calcula como:", {"A":"P = V·I","B":"P = V·I·cosφ","C":"P = I²·X","D":"P = V²·R"}, "B"),
    Question("Eléctrica", "¿Qué protege principalmente un interruptor termomagnético?", {"A":"Sobretensión","B":"Fuga a tierra","C":"Sobrecarga y cortocircuito","D":"Armónicos"}, "C"),
    Question("Eléctrica", "En un sistema trifásico balanceado, potencia activa total:", {"A":"P = V_L·I_L","B":"P = 3·V_F·I_F","C":"P = √3·V_L·I_L·cosφ","D":"P = √3·V_F·I_F·cosφ"}, "C"),
    Question("Eléctrica", "En resistencias en paralelo, ¿qué magnitud es igual en todas?", {"A":"La corriente","B":"El voltaje","C":"La potencia","D":"La resistencia equivalente"}, "B"),
    Question("Eléctrica", "¿Qué instrumento mide corriente?", {"A":"Voltímetro","B":"Amperímetro","C":"Ohmímetro","D":"Wattímetro"}, "B"),
    Question("Eléctrica", "¿Qué magnitud mide Hz?", {"A":"Resistencia","B":"Frecuencia","C":"Voltaje","D":"Energía"}, "B"),

    # ELECTRÓNICA
    Question("Electrónica", "¿Qué componente almacena energía en un campo eléctrico?", {"A":"Inductor (bobina)","B":"Resistencia","C":"Capacitor","D":"Diodo"}, "C"),
    Question("Electrónica", "Un diodo ideal conduce:", {"A":"En ambos sentidos","B":"Solo en un sentido","C":"Solo AC","D":"Solo señales digitales"}, "B"),
    Question("Electrónica", "¿Qué dispositivo se usa típicamente para amplificar señales?", {"A":"Fusible","B":"Transistor","C":"Resistencia","D":"Conmutador"}, "B"),
    Question("Electrónica", "¿Qué hace un regulador de voltaje?", {"A":"Aumenta la corriente","B":"Mantiene voltaje estable","C":"Convierte AC a DC siempre","D":"Elimina ruido por completo"}, "B"),
    Question("Electrónica", "En electrónica, “GND” normalmente se refiere a:", {"A":"Fase","B":"Neutro","C":"Tierra / referencia","D":"Potencia reactiva"}, "C"),

    # GENERAL
    Question("General", "¿Quién es famoso por sus aportes clave al electromagnetismo experimental?", {"A":"Darwin","B":"Faraday","C":"Galileo","D":"Bohr"}, "B"),
    Question("General", "¿Qué planeta tiene el campo magnético más fuerte del sistema solar?", {"A":"Marte","B":"Tierra","C":"Júpiter","D":"Venus"}, "C"),
    Question("General", "¿Cuántos bits tiene 1 byte?", {"A":"4","B":"8","C":"16","D":"32"}, "B"),
    Question("General", "¿Cuál es el símbolo químico del cobre (muy usado en conductores)?", {"A":"Co","B":"Cu","C":"Cr","D":"Cb"}, "B"),
]

# ---------- Helpers ----------
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

def new_room_code(n=6):
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def pick_10_questions(seed: int) -> List[Question]:
    rng = random.Random(seed)
    qs = QUESTION_BANK.copy()
    rng.shuffle(qs)
    return qs[:10]

def ensure_room(room_code: str):
    rooms = _load_json(ROOMS_FILE, {})
    if room_code not in rooms:
        rooms[room_code] = {
            "created_at": int(time.time()),
            "seed": random.randint(1, 10**9),
            "players": {},  # name -> {"answers": {idx: "A"}, "score": int, "done": bool}
            "finished": False,
        }
        _save_json(ROOMS_FILE, rooms)

def get_room(room_code: str):
    rooms = _load_json(ROOMS_FILE, {})
    return rooms.get(room_code)

def upsert_room(room_code: str, room_data: dict):
    rooms = _load_json(ROOMS_FILE, {})
    rooms[room_code] = room_data
    _save_json(ROOMS_FILE, rooms)

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

def leaderboard_table():
    stats = _load_json(STATS_FILE, {})
    rows = []
    for name, s in stats.items():
        rows.append((name, s["wins"], s["losses"], s["ties"], s["games"]))
    rows.sort(key=lambda x: (x[1], -x[2], x[4]), reverse=True)  # wins desc, losses asc-ish, games desc
    return rows

# ---------- UI ----------
st.set_page_config(page_title="Trivia 2 jugadores ⚡", page_icon="⚡", layout="centered")

st.title("⚡ Trivia a distancia (2 jugadores)")
st.caption("Misma sala = mismas 10 preguntas. Al final: ganador, apuesta y ranking de victorias/derrotas 😄")

with st.sidebar:
    st.subheader("🏆 Ranking burrit@ (histórico)")
    rows = leaderboard_table()
    if rows:
        for i, (name, w, l, t, g) in enumerate(rows[:20], start=1):
            st.write(f"**{i}. {name}** — ✅ {w} | ❌ {l} | 🤝 {t} | 🎮 {g}")
        # burrit@ por derrotas
        worst = sorted(rows, key=lambda x: (x[2], x[4]), reverse=True)[0]
        st.info(f"🐴 Burrit@ oficial (más derrotas): **{worst[0]}** (❌ {worst[2]})")
    else:
        st.write("Aún no hay partidas registradas.")

st.divider()

tab1, tab2 = st.tabs(["🎮 Jugar", "📌 Instrucciones WhatsApp"])

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

    name = st.text_input("Tu nombre (el que quieras)", value=st.session_state.get("player_name", "")).strip()
    st.session_state["player_name"] = name

    if not name:
        st.warning("Escribe tu nombre para empezar.")
        st.stop()

    # init player
    room["players"].setdefault(name, {"answers": {}, "score": 0, "done": False})
    upsert_room(room_code, room)

    questions = pick_10_questions(room["seed"])
    q_dicts = [asdict(q) for q in questions]

    st.write("📌 **Reglas:** 1 punto por acierto. Se muestra la respuesta correcta al responder.")

    # quiz UI
    my = room["players"][name]
    if my.get("done"):
        st.success("✅ Ya terminaste tus 10 preguntas. Esperando al otro jugador…")
    else:
        for idx, q in enumerate(q_dicts):
            st.markdown(f"### Pregunta {idx+1}/10 — _{q['category']}_")
            st.write(q["prompt"])

            options_labels = [f"{k}) {v}" for k, v in q["options"].items()]
            key_map = list(q["options"].keys())

            prev = my["answers"].get(str(idx))
            default_index = key_map.index(prev) if prev in key_map else 0

            choice_label = st.radio(
                "Elige una opción",
                options_labels,
                index=default_index,
                key=f"q_{idx}_{name}_{room_code}",
                horizontal=False
            )

            chosen_key = choice_label.split(")")[0]
            if st.button("✅ Confirmar respuesta", key=f"confirm_{idx}_{name}_{room_code}"):
                # lock-ish: reload room each confirm
                room = get_room(room_code) or room
                room["players"].setdefault(name, {"answers": {}, "score": 0, "done": False})
                my = room["players"][name]

                # save answer
                my["answers"][str(idx)] = chosen_key

                correct = q["answer"]
                if chosen_key == correct:
                    st.success("✅ Correcto")
                else:
                    st.error(f"❌ Incorrecto — correcta: {correct}) {q['options'][correct]}")

                # recompute score
                score = 0
                for j, qq in enumerate(q_dicts):
                    a = my["answers"].get(str(j))
                    if a == qq["answer"]:
                        score += 1
                my["score"] = score

                # done?
                if len(my["answers"]) >= 10:
                    my["done"] = True

                room["players"][name] = my
                upsert_room(room_code, room)
                st.rerun()

            st.caption(f"Respuesta correcta: **{q['answer']}) {q['options'][q['answer']]}**")
            st.divider()

    # Show room status
    room = get_room(room_code) or room
    players = room.get("players", {})
    st.subheader("📣 Estado de la sala")
    if players:
        for pname, pdata in players.items():
            status = "✅ listo" if pdata.get("done") else "⌛ jugando"
            st.write(f"- **{pname}** — {status} — Puntaje: **{pdata.get('score', 0)}/10**")
    else:
        st.write("Aún no hay jugadores.")

    # Finalize when 2+ players done
    done_players = [(pname, pdata.get("score", 0)) for pname, pdata in players.items() if pdata.get("done")]
    if len(done_players) >= 2:
        # pick top two by join order? We'll take first two done by score display:
        # to keep simple: take two highest scores among done
        done_players.sort(key=lambda x: x[1], reverse=True)
        pA, sA = done_players[0]
        pB, sB = done_players[1]

        st.subheader("🏁 Resultado final (top 2)")
        st.write(f"**{pA}**: {sA}/10")
        st.write(f"**{pB}**: {sB}/10")

        if sA > sB:
            st.success(f"🏆 Ganador: **{pA}** — 💸 **{pB}** paga la apuesta 😄")
            if st.button("📌 Registrar resultado en ranking", key=f"save_{room_code}"):
                update_stats(winner=pA, loser=pB, tie=False)
                st.success("Ranking actualizado ✅ (recarga el sidebar)")
        elif sB > sA:
            st.success(f"🏆 Ganador: **{pB}** — 💸 **{pA}** paga la apuesta 😄")
            if st.button("📌 Registrar resultado en ranking", key=f"save2_{room_code}"):
                update_stats(winner=pB, loser=pA, tie=False)
                st.success("Ranking actualizado ✅ (recarga el sidebar)")
        else:
            st.info("🤝 Empate — ambos pagan o hay desempate 😄")
            if st.button("📌 Registrar empate en ranking", key=f"saveT_{room_code}"):
                update_stats(winner=pA, loser=pB, tie=True)
                st.success("Ranking actualizado ✅ (recarga el sidebar)")

with tab2:
    st.subheader("📌 Cómo mandarle la invitación por WhatsApp")
    st.write(
        "1) Despliega esta app y obtén el link público.\n"
        "2) Crea una sala (Room Code).\n"
        "3) Envíale a Elizabeth un mensaje como este:"
    )
    st.code(
        "Amor, entremos a la trivia ⚡\n"
        "Link: <pega aquí el link>\n"
        "Room Code: ABC123\n"
        "Regla: 10 preguntas, el que pierde paga 😄",
        language="text"
    )
    st.write("Cuando ambos terminen, registra el resultado para que cuente en el ranking.")

