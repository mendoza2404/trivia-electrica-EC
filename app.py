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
QUESTIONS_JSON = "questions.json"  # opcional: si existe, se usa como base grande

# =========================
# Model
# =========================
@dataclass
class Question:
    category: str
    prompt: str
    options: Dict[str, str]  # A/B/C/D
    answer: str              # "A"/"B"/"C"/"D"

# =========================
# Persistence
# =========================
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

# =========================
# Rooms
# =========================
def new_room_code(n=6):
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def ensure_room(room_code: str):
    rooms = _load_json(ROOMS_FILE, {})
    if room_code not in rooms:
        rooms[room_code] = {
            "created_at": int(time.time()),
            "seed": random.randint(1, 10**9),
            "players": {},        # name -> {"answers": {idx: "A"}, "done": bool}
            "result_saved": False # para no duplicar ranking
        }
        _save_json(ROOMS_FILE, rooms)

def get_room(room_code: str):
    rooms = _load_json(ROOMS_FILE, {})
    return rooms.get(room_code)

def upsert_room(room_code: str, room_data: dict):
    rooms = _load_json(ROOMS_FILE, {})
    rooms[room_code] = room_data
    _save_json(ROOMS_FILE, rooms)

# =========================
# Stats
# =========================
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

# =========================
# Questions
# =========================
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
    external = _load_json(QUESTIONS_JSON, None)
    bank: List[Question] = []
    if isinstance(external, list) and external:
        for item in external:
            if isinstance(item, dict):
                q = normalize_question_dict(item)
                if q:
                    bank.append(q)
        if len(bank) >= 50:
            return bank
    return EMBEDDED_BANK.copy()

def safe_pick_balanced(bank: List[Question], seed: int, n_total: int = 10) -> List[Question]:
    """
    Balance típico para mezcla:
      4 Eléctrica
      3 Electrónica
      3 General
    Determinístico por seed de la sala.
    """
    rng = random.Random(seed)
    by_cat = {"Eléctrica": [], "Electrónica": [], "General": []}
    others = []
    for q in bank:
        if q.category in by_cat:
            by_cat[q.category].append(q)
        else:
            others.append(q)

    for k in by_cat:
        rng.shuffle(by_cat[k])
    rng.shuffle(others)

    want = {"Eléctrica": 4, "Electrónica": 3, "General": 3}
    picked: List[Question] = []
    for cat, cnt in want.items():
        picked.extend(by_cat[cat][:cnt])

    if len(picked) < n_total:
        remaining = []
        for cat, cnt in want.items():
            remaining.extend(by_cat[cat][cnt:])
        remaining.extend(others)
        rng.shuffle(remaining)
        picked.extend(remaining[: (n_total - len(picked))])

    rng.shuffle(picked)
    return picked[:n_total]

def compute_score(questions: List[Question], answers: Dict[str, str]) -> int:
    score = 0
    for i, q in enumerate(questions):
        a = (answers.get(str(i)) or "").strip().upper()
        if a == q.answer:
            score += 1
    return score

# =========================
# Embedded bank (mixto)
# Puedes ampliarlo; ideal: usar questions.json para 1000+
# =========================
EMBEDDED_BANK: List[Question] = []

def add_q(cat, prompt, A, B, C, D, ans):
    EMBEDDED_BANK.append(Question(cat, prompt, {"A": A, "B": B, "C": C, "D": D}, ans))

# Eléctrica
add_q("Eléctrica", "¿Unidad de la resistencia eléctrica?", "Ohm (Ω)", "Volt (V)", "Ampere (A)", "Watt (W)", "A")
add_q("Eléctrica", "En AC senoidal, potencia activa:", "P=V·I", "P=V·I·cosφ", "P=I²·X", "P=V²·R", "B")
add_q("Eléctrica", "¿Qué protege un interruptor termomagnético?", "Sobretensión", "Fuga a tierra", "Sobrecarga y cortocircuito", "Armónicos", "C")
add_q("Eléctrica", "En paralelo, ¿qué es igual en todas las ramas?", "Corriente", "Voltaje", "Resistencia", "Potencia", "B")
add_q("Eléctrica", "¿Instrumento para medir corriente?", "Voltímetro", "Amperímetro", "Ohmímetro", "Wattímetro", "B")
add_q("Eléctrica", "¿Qué mide Hz?", "Frecuencia", "Energía", "Resistencia", "Potencia", "A")
add_q("Eléctrica", "Potencia trifásica (balanceada) usando magnitudes de línea:", "P=V_L·I_L", "P=3·V_F·I_F", "P=√3·V_L·I_L·cosφ", "P=√3·V_F·I_F", "C")
add_q("Eléctrica", "¿Qué protege un diferencial (RCD)?", "Sobrecarga", "Cortocircuito", "Fuga a tierra", "Sobretensión", "C")
add_q("Eléctrica", "En serie, la corriente:", "Se divide", "Es igual en todos los elementos", "Es cero", "Depende solo del voltaje", "B")
add_q("Eléctrica", "1 kW equivale a:", "100 W", "1000 W", "10,000 W", "1 W", "B")

# Electrónica
add_q("Electrónica", "¿Qué componente almacena energía en un campo eléctrico?", "Inductor", "Resistencia", "Capacitor", "Diodo", "C")
add_q("Electrónica", "Un diodo ideal conduce:", "En ambos sentidos", "Solo en un sentido", "Solo AC", "Solo digital", "B")
add_q("Electrónica", "¿Qué dispositivo amplifica señales típicamente?", "Fusible", "Transistor", "Capacitor", "Bobina", "B")
add_q("Electrónica", "¿Qué hace un rectificador?", "Convierte AC a DC", "Convierte DC a AC", "Eleva tensión", "Aísla", "A")
add_q("Electrónica", "GND normalmente es:", "Fase", "Neutro", "Referencia/tierra del circuito", "Protección SPD", "C")
add_q("Electrónica", "Un capacitor ideal en DC (estado estable) se comporta como:", "Corto", "Abierto", "Resistencia", "Fuente", "B")
add_q("Electrónica", "Una bobina ideal en DC (estado estable) se comporta como:", "Abierto", "Corto", "Diodo", "Transformador", "B")
add_q("Electrónica", "PWM significa:", "Modulación de ancho de pulso", "Medición de potencia media", "Protección sobrecorriente", "Transformación de voltaje", "A")
add_q("Electrónica", "ADC convierte:", "Analógico a digital", "Digital a analógico", "AC a DC", "DC a AC", "A")
add_q("Electrónica", "LED significa:", "Light Emitting Diode", "Low Energy Device", "Linear Electronic Driver", "Logic Enabled Diode", "A")

# General
add_q("General", "¿Cuántos bits tiene 1 byte?", "4", "8", "16", "32", "B")
add_q("General", "¿Símbolo químico del cobre?", "Co", "Cu", "Cr", "Cb", "B")
add_q("General", "¿Qué planeta tiene el campo magnético más fuerte del sistema solar?", "Marte", "Tierra", "Júpiter", "Venus", "C")
add_q("General", "¿Quién fue clave en electromagnetismo experimental?", "Darwin", "Faraday", "Galileo", "Bohr", "B")
add_q("General", "¿Cuál es la capital de Ecuador?", "Guayaquil", "Quito", "Cuenca", "Manta", "B")
add_q("General", "¿Qué significa CPU?", "Central Processing Unit", "Control Power Unit", "Core Program Utility", "Circuit Protection Unit", "A")
add_q("General", "¿Qué significa GPS?", "Global Positioning System", "General Power Supply", "Graphical Position Sensor", "Ground Pressure System", "A")
add_q("General", "¿Cuál es el océano más grande?", "Atlántico", "Índico", "Pacífico", "Ártico", "C")
add_q("General", "¿Qué instrumento mide temperatura?", "Barómetro", "Termómetro", "Higrómetro", "Anemómetro", "B")
add_q("General", "¿Qué es IoT?", "Internet of Things", "Input of Time", "Interface of Tools", "Internal of Tech", "A")

# =========================
# UI
# =========================
st.set_page_config(page_title="Trivia 2 jugadores ⚡", page_icon="⚡", layout="centered")
st.title("⚡ Trivia a distancia (2 jugadores)")
st.caption("Misma sala = mismas 10 preguntas. ✅ Respuestas ocultas hasta el final 😄")

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

    player_name = st.text_input("Tu nombre (el que quieras)", value=st.session_state.get("player_name", "")).strip()
    st.session_state["player_name"] = player_name
    if not player_name:
        st.warning("Escribe tu nombre para empezar.")
        st.stop()

    # init player
    room["players"].setdefault(player_name, {"answers": {}, "done": False})
    upsert_room(room_code, room)

    bank = load_question_bank()
    if len(bank) < 20:
        st.error("Banco de preguntas muy pequeño. Agrega más (ideal 200+ o usa questions.json).")
        st.stop()

    questions = safe_pick_balanced(bank, seed=room["seed"], n_total=10)

    # gameplay
    room = get_room(room_code) or room
    my = room["players"].get(player_name) or {"answers": {}, "done": False}

    if my.get("done"):
        st.success("✅ Ya terminaste tus 10 preguntas. Esperando al otro jugador…")
    else:
        st.info("🕵️ Modo competencia: **NO se muestran respuestas** hasta el final.")

        for idx, q in enumerate(questions):
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
                horizontal=False
            )
            chosen_key = choice_label.split(")")[0].strip().upper()

            if st.button("✅ Confirmar respuesta", key=f"confirm_{idx}_{player_name}_{room_code}"):
                room = get_room(room_code) or room
                room["players"].setdefault(player_name, {"answers": {}, "done": False})
                my = room["players"][player_name]

                my["answers"][str(idx)] = chosen_key
                if len(my["answers"]) >= 10:
                    my["done"] = True

                room["players"][player_name] = my
                upsert_room(room_code, room)
                st.rerun()

            # 👇 IMPORTANTÍSIMO: NO mostramos la respuesta correcta aquí
            st.divider()

    # status
    room = get_room(room_code) or room
    players = room.get("players", {})

    st.subheader("📣 Estado de la sala")
    if players:
        for pname, pdata in players.items():
            status = "✅ listo" if pdata.get("done") else "⌛ jugando"
            score = compute_score(questions, pdata.get("answers", {}))
            st.write(f"- **{pname}** — {status} — Puntaje: **{score}/10**")
    else:
        st.write("Aún no hay jugadores.")

    # final (only when 2 done)
    done_players = [(pname, pdata) for pname, pdata in players.items() if pdata.get("done")]
    if len(done_players) >= 2:
        p1, d1 = done_players[0]
        p2, d2 = done_players[1]

        s1 = compute_score(questions, d1.get("answers", {}))
        s2 = compute_score(questions, d2.get("answers", {}))

        st.subheader("🏁 Resultado final")
        st.write(f"**{p1}**: {s1}/10")
        st.write(f"**{p2}**: {s2}/10")

        if s1 > s2:
            winner, loser, tie = p1, p2, False
            st.success(f"🏆 Ganador: **{winner}** — 💸 **{loser}** paga la apuesta 😄")
        elif s2 > s1:
            winner, loser, tie = p2, p1, False
            st.success(f"🏆 Ganador: **{winner}** — 💸 **{loser}** paga la apuesta 😄")
        else:
            winner, loser, tie = p1, p2, True
            st.info("🤝 Empate — ambos pagan o hacen desempate 😄")

        # save result ONCE
        if not room.get("result_saved", False):
            update_stats(winner=winner, loser=loser, tie=tie)
            room["result_saved"] = True
            upsert_room(room_code, room)
            st.toast("✅ Ranking actualizado automáticamente", icon="🏆")

        # ✅ REVELAR RESPUESTAS SOLO AQUÍ (AL FINAL)
        st.subheader("🧾 Revisión final (ahora sí se muestran respuestas)")
        for i, q in enumerate(questions):
            a1 = (d1.get("answers", {}).get(str(i)) or "-").upper()
            a2 = (d2.get("answers", {}).get(str(i)) or "-").upper()
            correct = q.answer

            st.markdown(f"**{i+1}. {q.prompt}**  \n_Categoría: {q.category}_")
            st.write(f"✅ Correcta: **{correct}) {q.options[correct]}**")
            st.write(f"👤 {p1}: **{a1}**" + (" ✅" if a1 == correct else " ❌"))
            st.write(f"👤 {p2}: **{a2}**" + (" ✅" if a2 == correct else " ❌"))
            st.divider()

with tab2:
    st.subheader("📌 Cómo mandarle la invitación por WhatsApp")
    st.write("1) Comparte el link.\n2) Crea sala y envía el Room Code.\n3) Ambos entran con el mismo Room Code.")
    st.code(
        "Amor ❤️, entremos a la trivia ⚡\n"
        "Link: (pega aquí el link)\n"
        "Room Code: ABC123\n"
        "Regla: 10 preguntas, el que pierde paga 😄",
        language="text"
    )

    st.subheader("📚 Base grande (1000+)")
    st.write("Si subes un archivo `questions.json` al repo, la app lo usará automáticamente.")
    st.code(
        """[
  {
    "category": "Eléctrica",
    "prompt": "¿Qué protege un diferencial (RCD)?",
    "options": {"A":"Sobrecarga","B":"Cortocircuito","C":"Fuga a tierra","D":"Sobretensión"},
    "answer": "C"
  }
]""",
        language="json"
    )
